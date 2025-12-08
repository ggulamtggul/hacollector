# Changelog

## 0.89
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
