# Changelog

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
