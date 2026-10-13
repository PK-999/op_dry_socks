# Readiness assessment

Verified on **12 October 2026**. Dry Socks is ready to run locally and demonstrate
from a fresh checkout. It is a personal local application, not a deployed
multi-user service. The offline demo is complete without provider credentials.

## Evidence

| Area | Result |
| --- | --- |
| Fresh setup | Pinned runtime/development dependencies installed in a new temporary Python 3.14 environment; `pip check` passed |
| Python | 85 offline tests passed, including configuration validation, isolated app instances, demo persistence and complete-forecast smoke checks |
| JavaScript | 10 Node tests passed for theme, HTTP errors/cancellation, Bengaluru time, reduced motion and scenery preview recovery |
| Static checks | Ruff lint and formatting, Python compilation, JS syntax and installer shell syntax passed |
| Google adapter browser tests | Missing key, script failure and working map fixtures passed; autocomplete sessions, keyboard selection, stale details, overlay cleanup and late callbacks covered |
| Full demo browser flow | 1440px desktop and 390px mobile passed through real Flask endpoints: alternatives, save/reload, mode, swap, search and forecast failure/recovery; no external requests or JavaScript errors |
| Actual server startup | Clean-environment `server.py --demo --port 5112` served the page, configuration, alternatives and complete forecast over real local HTTP |
| Live route/weather | Three Bengaluru sample commutes returned complete assessments with the pinned dependency environment; no saved-config writes, telemetry, state changes or notifications |
| Live place search | Google autocomplete returned five predictions and selected-place details resolved coordinates; no configuration writes |
| CI | Workflow added for Python 3.10/3.14 and Node 22; the corresponding local commands passed, but hosted GitHub Actions has not run in this session |

The live samples were Koramangala → Indiranagar, Whitefield → Silk Board and
Bellandur → Marathahalli. All returned `CLEAR` for those checks. This is evidence
of route and forecast availability at that time, not a prediction of future
weather or a guarantee that any commute stays dry.

## What changed

- Extracted the Flask app factory, endpoint blueprint and shared validation.
- Shared the weather/advice response builder between dashboard and monitor.
- Added redacted configuration errors and defaults for omitted optional settings.
- Added explicit offline demo adapters, isolated in-memory saves and persistent UI labeling.
- Extracted cancellable HTTP and map controllers; cleared stale route/weather
  overlays and prevented failed map loads from being revived by late callbacks.
- Restricted live Google content to Google Maps. The demo uses tile-free Leaflet.
- Organized CSS by component base, theme and responsive rules; preserved the
  existing local UI design and scenery, with a clearer mobile header.
- Corrected ambient time to Asia/Kolkata, respected reduced motion and restored
  the latest forecast after preview mode.
- Fixed final-review edge cases: pending map idle callbacks after authorization
  failure and very large JSON integers bypassing normal validation.
- Pinned direct dependencies, separated optional browser support, standardized
  Python formatting and added Make/CI commands.
- Replaced setup-dependent README text with a demo screenshot, fresh-checkout
  instructions, module map and current architecture/provider documentation.

## Remaining verification and scope

The dedicated Google Maps browser key is not configured on this checkout, so the
real map library was not exercised; live text search works, and browser tests use
map fixtures. Live X access was not exercised and demo X is explicitly disabled.
The live smoke test skips social sources. Native notification delivery and the
login LaunchAgent were not activated; their logic/shell syntax were checked
without sending notifications or modifying the user's installation.

Python 3.10 and Linux execution are configured in CI but were not run locally;
local verification used macOS/Python 3.14. Direct dependencies are pinned;
transitive dependencies remain governed by their package requirements.

Public hosting would need authentication, multi-user persistence, secret
management and a production deployment design. Provider-specific usage and
entitlements still apply. No repository-wide license has been chosen for the
original code/scenery; the bundled Leaflet license is included.

Forecast resolution, approximate checkpoint ETAs and unclassified public reports
remain product limitations described in the README. IMD observations, structured
traffic incidents and measured forecast calibration remain future work, rather
than prerequisites for the current local demo.

## Reproduce

```sh
make check
make browser
make live   # opt-in real provider requests; requires configured credentials
```

See [setup](SETUP.md) and [contributing](../CONTRIBUTING.md) for prerequisites.
The source configuration, existing telemetry and notification state were preserved.

An independent read-only review found no architectural or major functional gaps
in the agreed local/demo scope. Its two edge-case findings were reproduced with
failing regressions, fixed and reverified.
