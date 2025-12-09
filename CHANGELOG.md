# Changelog

## 1.3.18
- **Hotfix**: Fixed critical `NameError: name 'asyncio' is not defined` crash on startup. Restored missing `import asyncio` in `hacollector.py` that was accidentally removed during logging refactor.

## 1.3.17
- **Refactor**: Replaced custom `ColorLog` with Python standard `logging` module across all classes for better compatibility and stability.
- **Fix**: Resolved persistent "Unknown" availability state on boot. The collector now explicitly publishes "Online" status and device state immediately upon discovery, without waiting for the first periodic scan or user action.

## 1.3.16
- **Fix**: Corrected the initial availability message logic during discovery. It now correctly iterates through enabled devices and sends "Online" to each room's specific availability topic, ensuring entities are immediately available on boot.

## 1.3.15
- **Fix**: Fixed the initial MQTT connection using the old `.../status` topic for "Online" messages. It now correctly uses `.../availability`.

## 1.3.14
- **Fix**: Resolved "Unknown" availability state for entities. Fixed mismatched MQTT topic between Discovery and Status Publisher (`.../status` vs `.../availability`).

## 1.3.13
- **Hotfix**: Fixed IndentationError in `mqtt.py` that prevented startup in v1.3.12.

## 1.3.12
- **Performance**: Improved startup speed by prioritizing configured rooms during discovery. Full range scan (0x00-0x0F) is now optional via `full_scan_on_boot: true`.
- **Feature**: Added `sensor.lg_aircon_..._temperature` entity for easier statistics tracking.
- **Feature**: Implemented per-device Availability. If a specific indoor unit stops responding, only that unit is marked `unavailable` in Home Assistant.

## 1.3.11
- **Fix**: Corrected RS485 Packet Hunting header from `0x80` to `0x10`. Log analysis confirmed that response packets start with `0x10`.
- **Cleanup**: Removed verbose debug logs (`RX Raw`) introduced in v1.3.10 now that the protocol is verified.

## 1.3.10
- **Debug**: Enhanced RS485 diagnostic logging. `RX Raw` log now shows incoming hexadecimal data to verify hardware communication.
- **Fix**: Improved EOF detection in `comm.py`. The collector now correctly identifies when the RS485 converter closes the connection (sending 0 bytes) and triggers a reset.
- **Stability**: Aggressive buffer clearing. If `0x80` header is not found in the received chunk, the buffer is immediately cleared to prevent garbage accumulation.

## 1.3.9
- **Stability**: Refactored RS485 communication to use Stream Buffer and Packet Hunting. This resolves "Packet size mismatch" and deadlock issues by correctly handling fragmented or coalesced packets from the RS485 converter.
- **Log**: Suppressed "Read From LGAC FAIL" warnings during Auto Discovery scanning. Non-existent devices are now logged at DEBUG level.

## 1.3.8
- **Rollback**: Reverted RS485 communication logic (`lgac485.py`, `comm.py`) exactly to **v1.1.2** state.
- **Removed**: "Persistent Connection", "Packet Hunting", and "Header Hunt Timeout" features are removed in this network layer to resolve specific hardware compatibility issues.
- **Retained**: Home Assistant features (Config Flow, Healthcheck, HA Statistics) are kept.

## 1.3.7
- **Improvement**: Added a 0.2s delay immediately after establishing a TCP connection. This mitigates issues where some RS485 converters drop data if sent too quickly after the connection handshake.
- **Note**: This delay applies to both persistent and non-persistent modes whenever a *new* connection is made.

## 1.3.6
- **Feature**: Added `persistent_connection` option (Default: `true`). Set this to `false` to revert to the legacy behavior of closing the TCP connection after every command (might be more stable for some RS485 converters).
- **Log**: Elevated "Writing X bytes..." log to `INFO` level to ensure outbound traffic is visible even at default log levels.

## 1.3.5
- **Debug**: Added logging to the Write path (`Writing X bytes...`) to confirm requests are actually being sent to the RS485 converter. This will help determine if the connection is silent or if writes are failing silently.

## 1.3.4
- **Diagnostic**: Modified Packet Hunting to attempt reading data even if the header (`0x80`) is not found within the timeout. This allows "Garbage" or "Malformed" packets to be logged, helping diagnosis of connection issues where the device might be sending unexpected data.
- **Log**: Elevated "Header Hunt Timeout" log from `DEBUG` to `WARN` to make it visible in standard logs.

## 1.3.3
- **Hotfix**: Fixed `IndentationError` in `appconf.py` that prevented startup.

## 1.3.2
- **Bugfix**: Fixed critical issue in Packet Hunting logic where the hunted header was ignored by the subsequent read operation, causing `Read From LGAC FAIL!` loops. Replaced `async_get_data_direct` (socket-only) with `async_get_data` (buffered) to correctly consume the found header.

## 1.3.1
- **Hotfix**: Increased default `rs485_timeout` from 0.5s to 2.0s. This resolves the `Read From LGAC FAIL!` recursion on slower devices/converters.
- **Debug**: Added detailed buffer dump logging when Packet Hunting times out, helping diagnose protocol header mismatches.

## 1.3.0
- **HA Integration**: Added `state_class: measurement` and `device_class: temperature` to MQTT discovery. Home Assistant now displays Statistics Graphs for temperature history.
- **Process Stability**: Removed internal restart loop. The collector now exits cleanly on critical errors (`exit 1`), allowing HA Supervisor to handle restarts and logging natively.
- **Healthcheck**: Implemented a "Smart" Healthcheck. The main loop touches `/tmp/healthy` every 30s. Docker now restarts the container if the application hangs (Deadlock), not just if the process disappears.
- **Configuration**: Added `rs485_timeout` option (default 0.5s) to `options.json` for tuning RS485 read sensitivity.

## 1.2.0
- **Robustness (RS485)**: Implemented "Sliding Window" / "Packet Hunting" algorithm. The collector now intelligently searches for the packet header (`0x80`) in the data stream, discarding noise or shifted bytes. This prevents "Deadlock" situations caused by byte shifts and enables self-healing communication.

## 1.1.2
- **Bugfix**: Fixed `IndentationError` in `appconf.py` caused by incorrect refactoring of legacy config reading. Removed redundant loop to verify cleaner code structure.

## 1.1.1
- **Hotfix**: Resolved "Configuration is invalid!" startup crash caused by missing `hacollector.conf`. Configuration loading order is now corrected to prioritize `options.json` and treat legacy file as optional.

## 1.1.0
- **Stable Unique ID**: Bind Home Assistant Unique ID to RS485 Hardware ID (uid) instead of changeable Room Name. Prevents "Zombie entities" when renaming rooms.
- **Async MQTT Discovery**: Removed blocking `time.sleep` calls during discovery, preventing Event Loop lag.
- **Optimization**: Removed `run.sh` & `jq` dependency. Python now handles configuration directly, reducing Docker image size and complexity.
- **Refactor**: Improved standardized Logging across all modules.

## 1.0.0
- **Major Release**: Initial 1.0 release reflecting significant architectural stability and feature completeness.
- **Architecture**: Migrated to `asyncio.Queue` for handling commands. This eliminates the CPU-intensive polling loop and improves responsiveness using `await queue.get()`.
- **Configuration**: Implemented direct parsing of `/data/options.json`. The addon now reads configuration natively, robustly handling settings without relying on complex environment variable passing.
- **Feature**: Added `scan_interval` option (default 20s). Users can now adjust how frequently the addon polls device status.

## 0.9.15
- **Improvement**: Enabled persistent TCP connection. Previously, the add-on closed and re-opened the socket for every packet, causing excessive "Connecting..." logs. Now the connection is kept alive, significantly reducing log noise and overhead.

## 0.9.14
- **Improvement**: Optimized socket handling during Auto Discovery. Read timeouts for non-existent devices no longer trigger a socket reconnection, reducing log noise and overhead.

## 0.9.13
- **Fix**: Resolved `IndentationError` in `mqtt.py` introduced in v0.9.12 hotfix. Cleaned up malformed class definition.

## 0.9.12
- **Fix**: Critical startup crash resolved. Fixed a bug in `mqtt.py` where `enabled_device` was undefined during initialization.

## 0.9.11
- **Fix**: Resolved "Illegal discovery topic" error in Home Assistant by sanitizing spaces in room names for MQTT topics. Friendly names still retain spaces (e.g., "living room" -> topic: "living_room", name: "LG Aircon living room").

## 0.9.10
- **Fix**: Suppressed "Too many read errors" log and socket reconnection during Auto Discovery. Scanning non-existent devices no longer counts as a connection error.

## 0.9.9
- **Fix**: Resolved a race condition where Auto Discovery would skip devices that were being polled by the main loop. Implemented `asyncio.Lock` with timeout to safely serialize RS485 access.

## 0.9.8
- **Fix**: Startup blocking issue resolved. Auto-discovery scan now runs in the background, allowing the add-on to report "Online" immediately.
- **Feature**: Added `min_temp` and `max_temp` options to `config.yaml` (default: 18~30).
- **Improvement**: Optimized Dockerfile build speed by caching requirements.
- **Refactor**: Improved code quality by reducing dependency on global configuration variables.

## 0.9.7
- **Change**: Reverted Auto-Registration. Found devices are now **logged only** and not automatically added to Home Assistant.
- **Improvement**: Increased Auto Discovery scan interval (1.5s) to prevent RS485 timeouts and read errors.

## 0.9.6
- **Improvement**: Implemented "Double Check" verification for Auto Registration. Devices must respond consistently multiple times to be registered, eliminating ghost devices.

## 0.9.5
- **Improvement**: Enhanced Auto Registration reliability by verifying sensor data (Mode and Temperature) before adding a device. This prevents ghost devices caused by noise.

## 0.9.4
- **New Feature**: Auto Registration! Devices found during startup scan that are not in the config are now automatically added to Home Assistant (e.g., `LG Aircon auto_room_02`).

## 0.9.3
- **Hotfix**: Fixed configuration UI disappearing due to missing schema.

## 0.9.2
- **Breaking Change**: Configuration format for `rooms` changed to support explicit RS485 IDs (e.g., `id: 0`).
- **New Feature**: Auto Discovery at startup to scan and log available RS485 IDs.
- **Improvement**: Stable Unique IDs based on RS485 ID instead of room name.
- **Cleanup**: Removed test code and standardized logging.

## 0.91
- **New Feature**: "Force Refresh" discovery mode to clear zombie entities.
- **Fix**: Enabled MQTT QoS 1 to guarantee discovery message delivery.
- **Improvement**: Optimized MQTT delays for better stability.

## 0.88
- **New Feature**: Automatic handling of spaces in room names (e.g., `computer room` -> `computer_room`).
- **Fix**: Resolved "Crash loop" caused by invalid room mapping initialization.
- **Improvement**: Added safety delays (0.5s) to MQTT discovery to prevent missing devices on startup.
- **Improvement**: Stabilized initial MQTT connection.

## 0.87
- **Initial Release** as Home Assistant Add-on.
