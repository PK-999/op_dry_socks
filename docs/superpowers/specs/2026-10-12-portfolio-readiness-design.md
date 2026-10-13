# Portfolio readiness design

The goal is a clear, runnable portfolio repository for the existing Bengaluru
commute assistant. Preserve the local dashboard design, saved commute and
credentials. Keep Flask, plain browser JavaScript and the existing service
adapters; no frontend build tool, database or hosted deployment is needed.

## Boundaries

- `server.py`: app factory, local HTTP protections, CLI startup and errors.
- `services/dashboard.py`: HTTP endpoints, delegating input validation and domain work.
- `services/validation.py`: reusable coordinates, geometry and numeric validation.
- `services/commute.py`: shared weather outlook and monitor assessment.
- `services/demo.py`: synthetic places, corridors and forecasts, enabled only by
  `server.py --demo`. Demo saves stay in memory and never read local credentials.
- `web/api.js`: cancellable HTTP requests and actionable errors.
- `web/map.js`: Google map and demo-only Leaflet map lifecycle and overlays.
- `web/app.js`: application state, user events, search and result rendering.
- `web/styles/`: base components, theme overrides and responsive rules in cascade order.

## Expected behavior

Python 3.10+ remains supported. A checkout can run a fully labeled demo without
keys, network access or Chromium. Live mode keeps real providers and fails
explicitly when unavailable. Google Places/Routes content is never drawn on a
non-Google map. A missing map still permits the existing text search and outlook.
Demo mode uses local vendor assets and a tile-free synthetic corridor map.

Malformed configuration receives an actionable, redacted error instead of a
traceback. Each Flask app owns its config path and write lock. The existing
dashboard and runner use one weather/advice response builder. Missing forecast
data cannot produce a clear recommendation. Demo and live modes do not silently
switch into each other. Forecast visuals use India time and respect reduced motion.

## Portfolio presentation and verification

The README leads with the problem, screenshot, demo command, setup and repository
map. Separate architecture, provider setup and readiness notes describe the
tradeoffs and limits. Pin direct dependencies and add one-command checks plus CI
for Python, Node and browser regressions. Include the license for vendored Leaflet.
Do not assign a license to the user's original work or unknown-origin images.

Acceptance: existing tests remain green; new app isolation/configuration/demo
tests pass; desktop/mobile browser flows cover loading, editing, alternative
selection, mode, swap, save/reload, unavailable providers and stale responses.
Run a separate live route/weather check without saves or notifications and report
its actual result. No publication, commits, monitor installation or notifications
are part of this task.
