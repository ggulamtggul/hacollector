# Changelog

All notable changes to this project will be documented in this file.

## [2.0.0] - 2026-06-12

### Added
- **Auto Discovery Mechanism:** Implemented 4-phase auto-scan sequence with Double-Check verification to detect valid RS485 aircon devices automatically and safely register them as temporary entities (e.g., `auto_room_0x0A`).
- **HA Official Multi-Arch Builds:** Fully migrated build infrastructure to support both `aarch64` and `amd64` using official `homeassistant` base images via modern GitHub composable actions.
- **Python Healthcheck:** Added internal Docker healthcheck to monitor the asyncio main loop via `/tmp/healthy`.
- Added customizable read socket timeouts (`rs485_timeout`) in config.

### Changed
- Refactored `Dockerfile` and startup sequence to use standard `s6-overlay` execution with `bashio`.
- Updated GitHub Actions CI to fix deprecation warnings (`home-assistant/builder@master` -> new modular actions strategy).
- Updated Paho MQTT integration to support v2 client API (`CallbackAPIVersion.VERSION1`).
- Changed initial discovery process to only perform targeted scans if `auto_scan` is disabled.

### Fixed
- Fixed bug causing ghost devices to be falsely registered during scans.
- Fixed socket buffer overflow logic that could crash the addon if the buffer got polluted.
- Fixed an MQTT payload parsing issue where incoming requests failed when targeting auto-discovered rooms.
- Improved TCPKeepAlive values and added connection stabilization sleep (`0.3s`) for RS485 Gateway (Elfin-EW11) compatibility.

## [1.0.0] - Legacy
- Initial Asyncio version for HA integration.
