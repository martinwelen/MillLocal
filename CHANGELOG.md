# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-02-16

### Added

- Climate entity with HEAT/OFF HVAC modes and preset modes (None, Weekly Program, Independent Device)
- Temperature control with 5-35 C range in 0.5 degree steps
- Sensors: current power (W), cumulative energy (kWh), control signal, raw temperature, calibration offset, firmware version
- Binary sensors: open window detection, cloud connected, heating active
- Switches: child lock, commercial lock, cloud communication, open window detection
- Number entities: calibration offset, hysteresis upper/lower, open window parameters
- Select entities: predictive heating type, display unit, controller type
- Custom services: set_vacation_mode, set_weekly_program, reboot
- Feature detection for Mill Max model (limited heating power, max heater power, PID parameters)
- Config flow with device validation and MAC-based unique ID
- Reconfigure flow for IP address changes
- English and Swedish translations
- HACS compatibility

[1.0.0]: https://github.com/martinwelen/MillLocal/releases/tag/v1.0.0
