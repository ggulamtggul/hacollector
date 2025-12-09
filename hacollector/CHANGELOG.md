# Changelog

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
