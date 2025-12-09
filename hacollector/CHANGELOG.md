# Changelog

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
- Initial Release as Home Assistant Add-on.
