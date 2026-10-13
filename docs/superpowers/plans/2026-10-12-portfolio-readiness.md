# Portfolio readiness implementation plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan
> task by task. Preserve the initial uncommitted UI work. Finish with an independent review.

**Goal:** Make the existing commute app understandable and reproducible from a fresh checkout.

**Architecture:** Small Flask app factory and endpoint blueprint, shared commute
services, explicit in-memory demo, and focused browser map/HTTP modules.

**Tech stack:** Python 3.10+, Flask, requests, polyline, plain JS/CSS, pytest,
Node's built-in test runner, Playwright for optional X and browser tests.

**Spec:** `docs/superpowers/specs/2026-10-12-portfolio-readiness-design.md`

## Global constraints

- Preserve the local UI changes, `config.json`, telemetry and notification state.
- Keep live provider failures distinct from synthetic demo data.
- Keep loopback-only HTTP access and private credentials server-side.
- No publication, commits, monitor installation or notifications.

## Review focus

App instances must not share saved config or demo state. Invalid config must not
leak credentials. Map outages and late callbacks must recover without stale
overlays. Reduced motion and non-India host time must behave correctly. Demo must
make no external requests or disk writes.

### Task 1: Backend boundaries and configuration

Files: `server.py`, `services/dashboard.py`, `services/validation.py`,
`services/commute.py`, `services/configuration.py`, `main.py`, `tests/test_server.py`,
`tests/test_places.py`, `tests/test_configuration.py`.

Interfaces: `create_app(config_path=None, *, demo=False)` returns an isolated
Flask app; `weather_outlook(config, points, duration, origin_name, destination_name)`
builds the existing JSON contract; `assess_commute(config, reverse=False,
social=True, route_fetcher=None)` retains the runner result contract.

- [x] Add failing isolation, malformed configuration and missing explicit-path tests.
- [x] Run those tests and inspect the failures.
- [x] Extract validation/endpoints and share commute assessment; add safe config errors.
- [x] Run the complete Python suite; expect all tests to pass.

### Task 2: Explicit offline demo

Files: `services/demo.py`, `services/dashboard.py`, `server.py`, `tests/test_demo.py`.
Interfaces: demo config, autocomplete/details, routes and weather functions
return the existing browser contracts, with synthetic provenance. Demo config
saves update only the app's in-memory copy.

- [x] Write tests forbidding network calls/config reads/disk writes and exercising
  search → details → routes → weather → save → reload across separate apps.
- [x] Run to confirm missing-demo failures.
- [x] Implement `--demo` and the isolated adapters.
- [x] Run Python tests; expect all to pass.

### Task 3: Frontend boundaries and reliable maps/ambient

Files: `web/api.js`, `web/map.js`, `web/app.js`, `web/ambient.js`, `web/index.html`,
`web/styles/*`, `web/vendor/*`, `tests/test_api.js`, `tests/test_ambient.js`,
`tests/browser/google_places.py`, `tests/browser/dashboard.py`.

Interfaces: `DrySocksAPI.request(path, options)` keeps cancellation semantics;
`DrySocksMap.create(callbacks)` owns map lifecycle and overlays. Live maps are
Google-only; Leaflet is local and tile-free for the explicit demo.

- [x] Reproduce current browser failure and add map reset/late-load, ambient timezone,
  reduced-motion and API failure/cancellation regressions.
- [x] Extract HTTP and map controllers, split CSS without changing cascade order,
  and move third-party files into `vendor` with their license.
- [x] Run Node and desktop/mobile browser checks; expect no JS errors or overflow.

### Task 4: Reproducible setup and portfolio documentation

Files: requirements files, `Makefile`, `.github/workflows/ci.yml`, `.gitignore`,
`README.md`, `docs/ARCHITECTURE.md`, `docs/SETUP.md`, `docs/READINESS.md`,
`CONTRIBUTING.md`, `docs/images/dashboard.png`.

- [x] Pin direct dependencies, separate optional browser support, add check commands
  and CI, clarify installer scope and preserve script compatibility.
- [x] Verify setup in a new environment, generate and inspect a demo screenshot,
  and run the separate live-provider smoke check.
- [x] Write documentation from actual outcomes, independent-review the final changes,
  address significant findings and rerun the affected checks.
