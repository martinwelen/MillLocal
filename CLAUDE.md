# Mill Local - Home Assistant Custom Integration

This file provides context for Claude Code to understand this project and enforce development standards.

## Development Workflow (MANDATORY)

### Git Branching Strategy
- **NEVER commit directly to `main`.** All changes must go through a Pull Request.
- Create a feature branch for every piece of work: `feature/{short-description}`
- Use `fix/{short-description}` for bug fixes, `docs/{short-description}` for documentation-only changes.
- Keep branches short-lived — merge within 1-2 sessions, don't let them drift.

### Pull Request Workflow
1. Create feature branch: `git checkout -b feature/{name}`
2. Make changes, commit frequently with descriptive messages
3. Push branch: `git push -u origin feature/{name}`
4. Create PR: `gh pr create --title "..." --body "..."`
5. CI must pass (GitHub Actions runs tests + build automatically)
6. Merge via PR (squash merge): `gh pr merge --squash`
7. Delete the branch after merge: `git branch -d feature/{name}`
8. Switch back to main and pull: `git checkout main && git pull`

### CI/CD
- GitHub Actions runs on every push and PR to `main` (`.github/workflows/ci.yml`)
- **Do NOT merge if CI is red.** Fix the failing tests first.
- Check CI status: `gh pr checks` or `gh run list`

### What Goes in a PR
- One logical change per PR (one feature, one bug fix, one refactor)
- PRs that touch multiple unrelated features are too large — split them up
- Always include a summary of what changed and why in the PR description

### Code Review
- When completing a major feature, use the `superpowers:requesting-code-review` skill
- Review your own diff before creating the PR: `git diff main...HEAD`

## Working Instructions

- **Start-of-session routine** - When the user greets you to start a session: (1) welcome them, (2) read project docs and git log to understand current state, (3) present a short list of suggested things to work on (pending tasks, backlog items, known issues, next features).
- **End-of-session routine** - When the user says goodbye or ends the session, automatically: (1) commit and push all code changes via PR if not already merged, (2) update documentation files with any changes, decisions, or progress made during the session.
- **Document key learnings** when discovering important technical insights or solutions.
- **Document architectural changes** when making or deciding on structural changes.
- **Keep documentation in sync** with code changes (README, CLAUDE.md, etc.).

## Project Overview

**Purpose:** Custom Home Assistant integration for Mill Gen 3 heaters via local REST API (no cloud). HACS-compatible.

**Tech Stack:** Python 3.12+, Home Assistant Core, aiohttp, pytest + pytest-asyncio + aioresponses, ruff

**Repository:** https://github.com/martinwelen/MillLocal

## Project Structure

```
MillLocal/
├── custom_components/
│   └── mill_local/
│       ├── __init__.py          # Integration setup, platform forwarding
│       ├── api.py               # REST API client for Mill heaters
│       ├── climate.py           # Climate entity (HEAT/OFF, presets, services)
│       ├── config_flow.py       # Config flow with device validation
│       ├── const.py             # Constants, feature flags, mappings
│       ├── coordinator.py       # DataUpdateCoordinator (polls /control-status)
│       ├── binary_sensor.py     # Open window, cloud, heating status
│       ├── sensor.py            # Power, temperature, energy, firmware
│       ├── switch.py            # Child lock, commercial lock, cloud, open window
│       ├── number.py            # Calibration, hysteresis, power limits
│       ├── select.py            # Predictive heating, display unit, controller type
│       ├── manifest.json        # HACS integration manifest
│       ├── services.yaml        # Service definitions
│       ├── strings.json         # English UI strings
│       └── translations/
│           ├── en.json          # English translations
│           └── sv.json          # Swedish translations
├── tests/
│   ├── conftest.py              # Shared fixtures and mock data
│   ├── test_api.py              # API client tests (28 tests)
│   ├── test_coordinator.py      # Coordinator tests (4 tests)
│   ├── test_config_flow.py      # Config flow tests (5 tests)
│   ├── test_climate.py          # Climate entity tests (13 tests)
│   ├── test_sensor.py           # Sensor tests (7 tests)
│   ├── test_binary_sensor.py    # Binary sensor tests (6 tests)
│   ├── test_switch.py           # Switch tests (5 tests)
│   ├── test_number.py           # Number tests (5 tests)
│   └── test_select.py          # Select tests (5 tests)
├── docs/
│   └── plans/                   # Design and implementation plans
├── .github/
│   └── workflows/
│       └── ci.yml               # CI pipeline (pytest + ruff)
├── pyproject.toml               # Project config (pytest, ruff)
├── requirements_test.txt        # Test dependencies
├── hacs.json                    # HACS metadata
├── CLAUDE.md                    # This file
└── README.md                    # Project README
```

## Key Files

| File | Purpose |
|------|---------|
| `custom_components/mill_local/api.py` | REST client — all GET/POST endpoints, feature detection, error handling |
| `custom_components/mill_local/coordinator.py` | Polls `/control-status` every 15s, provides data to all entities |
| `custom_components/mill_local/climate.py` | Main thermostat entity with HVAC modes, presets, and custom services |
| `custom_components/mill_local/const.py` | All constants, feature flags, operation mode mappings |
| `tests/conftest.py` | Mock API responses matching real heater data, shared fixtures |

## Testing

**Run tests:** `pytest tests/ -v` (from venv: `.venv/bin/python -m pytest tests/ -v`)

**Lint:** `ruff check custom_components/ tests/`

**Test framework:** pytest + pytest-asyncio (async auto mode) + aioresponses for HTTP mocking

**Current coverage:** 78 tests across 10 test files

## Architecture

- **Entity pattern:** Config entities (switch, number, select) manage their own state — fetch initial value on `async_added_to_hass`, track writes locally, no coordinator dependency for their values.
- **Coordinator entities:** Climate, sensor, binary sensor read from coordinator data (polled every 15s).
- **Feature gating:** Optional entities (limited_heating_power, max_heater_power) are only created if the device supports them (detected at config flow time).
- **Lambda pattern:** Entity descriptions use `get_fn=lambda api: api.method()` instead of unbound method references for testability with AsyncMock.
- **Read-modify-write:** Hysteresis and open window settings use read-modify-write to preserve sibling fields.

## Conventions

- **Code style:** ruff with rules E, F, I, N, UP, B, SIM, line-length 100
- **Naming:** `CannotConnectError` (N818), snake_case for variables/functions, PascalCase for classes
- **Commit messages:** Conventional commits (`feat:`, `fix:`, `style:`, `chore:`, `docs:`)
- **Test organization:** One test file per source module, `TestClassName` grouping, `test_method_name` naming

## Key Learnings

- Mill heaters return 404 as either HTTP 404 or plain text "Nothing matches the given URI" — both must be handled
- `DataUpdateCoordinator.__init__` requires explicit `config_entry=entry` parameter in newer HA versions
- aioresponses stores request keys as `("METHOD", yarl.URL(...))`, not plain strings
- aiohttp JSON payloads are in `kwargs["json"]` not `kwargs["data"]`
- Entity `async_write_ha_state()` requires `self.hass` to be set — mock it in unit tests
- Lambda-based function references work with AsyncMock; unbound method references don't
- Both regular convector and Max model run firmware `0x250317`
- Max model supports extra endpoints: `/limited-heating-power`, `/pid-parameters`

## Backlog

- [ ] **PID parameter entities:** Add number entities for PID kp/ki/kd tuning on Max models
- [ ] **Service descriptions in strings.json:** Add translated descriptions for set_vacation_mode, set_weekly_program, reboot services
- [ ] **Test coverage:** Reconfigure flow, energy sensor restore, edge cases
- [ ] **Broader device support:** Expand feature detection to probe `/oil-heater-power` and `/additional-socket-mode` at setup. Add oil heater power number entity (40/60/100%) and socket mode select entity (0-4). Make integration fully device-type-agnostic — detect capabilities by probing, not by name matching. Panel heaters likely already work since they share endpoints with the Max convector. Needs community testing with real devices.
- [ ] **Auto-discovery (DHCP):** Investigate DHCP-based discovery using Espressif MAC prefixes (`10:06:1C`, `08:F9:E0`) in `manifest.json`
- [ ] **Auto-discovery (subnet scan):** Add a "Scan network" button in the config flow that scans HA's local subnet for Mill heaters
- [ ] **Auto-discovery (custom range scan):** Allow user to enter a subnet or IP range to scan for Mill heaters
