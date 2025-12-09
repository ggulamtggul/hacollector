# Changelog

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
