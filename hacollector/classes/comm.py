from __future__ import annotations

import asyncio
import errno
import socket
import time
from typing import Optional

from classes.utils import Color, ColorLog


class TCPComm:
    """
    A small async TCP helper that is resilient to transient network outages.
    - Provides safe connect/close with TCP keepalive enabled
    - Retries reads/writes once after reconnecting if the socket broke
    - Avoids concurrent connect/close races via a lock
    """
    def __init__(self, server: str, port: int, buffer_size: int = 2048, interval: float = 0.0) -> None:
        self.server                     = server
        self.port                       = int(port)
        self.buffer_size                = buffer_size
        self.interval                   = interval
        self.last_accessed_time         = time.monotonic()
        self.read_buffer: bytes         = b''
        self.connection_reset: bool     = False
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        self._conn_lock: asyncio.Lock   = asyncio.Lock()
        self._closing: bool             = False

    @classmethod
    async def async_init(cls, server: str, port: int, buffer_size: int = 2048, interval: float = 0.0):
        return cls(server, port, buffer_size, interval)

    # ---------- connection management ----------
    async def _enable_keepalive(self, sock: socket.socket) -> None:
        try:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Platform-specific tuning; best-effort
            if hasattr(socket, "TCP_KEEPIDLE"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPIDLE, 30)
            if hasattr(socket, "TCP_KEEPINTVL"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, 10)
            if hasattr(socket, "TCP_KEEPCNT"):
                sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, 3)
        except Exception:
            # Keepalive is best-effort; do not fail
            pass

    async def connect_async_socket(self) -> None:
        """
        Ensure we have a connected reader/writer. This is safe to call often.
        """
        if self.writer is not None and not self.writer.is_closing():
            return

        async with self._conn_lock:
            if self.writer is not None and not self.writer.is_closing():
                return

            color_log = ColorLog()
            color_log.log(f"Connecting to {self.server}:{self.port} ...", Color.White, ColorLog.Level.INFO)

            # Try a couple of times before giving up to caller
            last_err: Optional[Exception] = None
            for attempt in range(1, 4):
                try:
                    reader, writer = await asyncio.open_connection(host=self.server, port=self.port)
                    # enable TCP keepalive
                    sock = writer.get_extra_info("socket")
                    if isinstance(sock, socket.socket):
                        await self._enable_keepalive(sock)
                        sock.settimeout(None)
                    self.reader, self.writer = reader, writer
                    self.connection_reset = False
                    color_log.log("Connected.", Color.Green, ColorLog.Level.INFO)
                    return
                except Exception as e:
                    last_err = e
                    color_log.log(f"Connect attempt {attempt} failed: {e}", Color.Yellow, ColorLog.Level.WARN)
                    await asyncio.sleep(min(1.0 * attempt, 3.0))

            # bubble up last error
            assert last_err is not None
            raise last_err

    async def close_async_socket(self) -> None:
        async with self._conn_lock:
            self._closing = True
            try:
                if self.writer is not None:
                    self.writer.close()
                    try:
                        await self.writer.wait_closed()
                    except Exception:
                        pass
            finally:
                self.reader = None
                self.writer = None
                self.read_buffer = b''
                self._closing = False

    async def wait_safe_communication(self) -> None:
        """
        Guarantee that connection is open before read/write.
        """
        await self.connect_async_socket()

    # ---------- write/read helpers ----------
    async def async_write_one_chunk(self, data: bytes) -> bool:
        """
        Write a single chunk. If the connection is broken, reconnect once and retry.
        """
        await self.wait_safe_communication()
        color_log = ColorLog()
        try:
            assert self.writer is not None
            self.writer.write(data)
            await self.writer.drain()
            self.last_accessed_time = time.monotonic()
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, TimeoutError, OSError) as e:
            color_log.log(f"Socket write error: {e}. Reconnecting...", Color.Yellow, ColorLog.Level.WARN)
            await self.close_async_socket()
            await self.connect_async_socket()
            try:
                assert self.writer is not None
                self.writer.write(data)
                await self.writer.drain()
                self.last_accessed_time = time.monotonic()
                return True
            except Exception as e2:
                color_log.log(f"Write failed again after reconnect: {e2}", Color.Red, ColorLog.Level.ERROR)
                return False

    async def async_get_data(self, length: int) -> bytes:
        """
        Read exactly `length` bytes, buffering as needed. Returns b'' on EOF.
        If the socket broke, set connection_reset and return b''.
        """
        await self.wait_safe_communication()
        color_log = ColorLog()
        try:
            while length > len(self.read_buffer):
                try:
                    assert self.reader is not None
                    buffer = await self.reader.read(self.buffer_size)
                    if buffer == b'':
                        # peer closed
                        self.connection_reset = True
                        break
                except IOError as e:
                    if e.errno == errno.ECONNRESET:
                        buffer = b''
                        self.connection_reset = True
                    else:
                        raise
                self.read_buffer += buffer

            ret = self.read_buffer[:length]
            self.read_buffer = self.read_buffer[length:]
            self.last_accessed_time = time.monotonic()

            if ret == b'' and self.connection_reset and not self._closing:
                # try one reconnect for next caller
                color_log.log("Read detected closed socket. Reconnecting...", Color.Yellow, ColorLog.Level.WARN)
                await self.close_async_socket()
                await self.connect_async_socket()

            return ret
        except Exception as e:
            color_log.log(f"Exception in socket READ: {e}", Color.Red, ColorLog.Level.CRITICAL)
            # Best-effort reset
            await self.close_async_socket()
            return b''

    async def async_get_data_direct(self, length: int) -> bytes:
        """
        Read up to `length` bytes directly from the socket with a small timeout.
        Returns b'' on timeout or EOF. Sets connection_reset on ECONNRESET.
        """
        await self.wait_safe_communication()
        try:
            assert self.reader is not None
            buffer = await asyncio.wait_for(self.reader.read(length), timeout=2.0)
        except asyncio.TimeoutError:
            color_log = ColorLog()
            color_log.log("Timeout waiting for data from socket.", Color.Yellow, ColorLog.Level.WARN)
            return b''
        except IOError as e:
            buffer = b''
            if e.errno == errno.ECONNRESET:
                self.connection_reset = True
        except Exception:
            buffer = b''
        if buffer == b'':
            # proactively reconnect for next operation
            await self.close_async_socket()
            try:
                await self.connect_async_socket()
            except Exception:
                pass
        return buffer
