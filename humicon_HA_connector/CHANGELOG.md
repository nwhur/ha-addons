# Changelog

## [v1.1.4] - 2026-06-16
### Fixed
- **MQTT LWT (Last Will and Testament)**: Added MQTT Last Will. If the add-on is uninstalled, stops, or crashes without providing new info, the broker will automatically mark all entities as `Unavailable` instead of displaying stale retained values (like the bugged 5.5%).

## [v1.1.3] - 2026-06-16
### Fixed
- **Temperature Scaling Hotfix**: Reverted the `/ 10.0` scaling for Indoor and Outdoor Temperature sensors. Similar to humidity, the Humicon Modbus actually sends temperature as a raw integer (e.g., 28 = 28°C), not scaled by 10. This fixes the issue where 28°C was displaying as 2.8°C.

## [v1.1.2] - 2026-06-16
### Fixed
- **Humidity Scaling Hotfix**: Reverted the `/ 10.0` scaling for Indoor and Outdoor Humidity sensors. Humidity values from Modbus are already raw percentages (e.g., 55 = 55%), so dividing them by 10 caused them to display as 5.5%. Temperature sensors still correctly use the `/ 10.0` scaling.

## [v1.1.1] - 2026-06-16
### Fixed
- **TCP Fragmentation Bug**: Fixed a critical bug in the sniffer loop where fragmented TCP packets would cause the buffer pointer to skip, resulting in lost or ignored Modbus frames. The daemon now correctly waits for full frames.
- **Sensor Scaling Bug**: Fixed an issue where Indoor/Outdoor Temperature and Humidity sensor values were displayed exactly as raw Modbus integers (e.g., 239 °C) instead of properly dividing by 10.0 (e.g., 23.9 °C).
- **i18n Translation Bug**: Fixed an issue where commands sent from Home Assistant while the `language` was set to `en` were ignored because the daemon did not reverse-translate English payloads back to Korean before processing.
- **Icon Transparency**: Fixed the add-on icon to have a transparent background instead of white corners.

### Added
- **Requirements Specification**: Added `REQUIREMENTS_SPECIFICATION.md` to the repository, containing the full system architecture, Modbus payloads, and HA entity configuration details.

## [v1.1.0] - 2026-06-15
### Changed
- **Renamed Add-on**: The add-on has been officially renamed from `Humicon MQTT Daemon` to **Humicon HA Connector** for better user intuitiveness.
- **Internationalization (i18n)**: Added a new `language` option (ko / en) in the add-on configuration. Users can now choose to display all entities, modes, and states in English natively in Home Assistant.
- **Terminology Update**: Changed "환기 수동(bypass)" to "바이패스" (Bypass) for clarity.

## [v1.0.0] - 2026-06-15
### Added
- Initial Release!
- Fully features hybrid RS485 Sniffing + Polling architecture via Elfin EW11.
- Provides Fan control (preset modes, power, speed).
- Provides comprehensive environmental sensors (Temperature, Humidity, CO2, PM10, PM2.5).
- Provides Target Humidity selection (30~60% + Eco/Comfort/Dry presets).
- Built-in High-Availability (Availability payload) with auto-reconnection logic.
- Graceful shutdown and fail-safe configuration defaults.
