# Dry Socks

**A weather-aware commute assistant for Bengaluru.** Compare routes, check when
rain may overlap your arrival at each checkpoint, and keep public traffic reports
as attributed local context.

A citywide forecast cannot tell you when rain will cross a moving commute. Dry
Socks combines fresh route duration, road-distance checkpoints and rainfall timing
to estimate a departure window with a safety buffer. It makes missing data visible
and avoids treating model estimates as street-level observations.

![Dry Socks dashboard running with clearly labeled synthetic demo data](docs/images/dashboard.png)

## Try the offline demo

Python 3.10+ is required. From a fresh checkout on macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py --demo
```

Open **http://localhost:5111**. Explore sample Bengaluru places, alternative
corridors, car/two-wheeler mode, forecast checkpoints, theme/scenery previews and
save/reload. Demo saves last until restart. The demo needs no credentials,
Chromium or network after installation. Its routes and forecasts are synthetic
and are labeled throughout the UI.

## What it does

- Compares fresh traffic-aware Google route alternatives for car and two-wheeler commutes.
- Estimates rain overlap using checkpoint arrival times and a configurable buffer.
- Saves a route preference while refreshing alternatives and travel time on later checks.
- Shows recent, relevant Bengaluru X reports with original links and source availability.
- Runs a separate scheduled monitor with notification deduplication and macOS desktop alerts.
- Handles incomplete forecasts, provider outages and stale browser responses explicitly.

The dashboard runs checks on demand. Background monitoring belongs to `main.py`.

## Run with live data

```sh
# Skip this copy if you already have a local configuration.
cp config.json.example config.json
# Configure provider keys in the file or environment; see the setup guide.
.venv/bin/python server.py
```

Google Routes enables both travel modes; Places API (New) enables search.
Open-Meteo supplies weather. The interactive Google map uses a separate,
referrer-restricted browser key. Mapbox car routing, Tomorrow.io corroboration
and X reports are optional. Playwright is needed only for cookie-based X access
and browser tests. See [provider setup and troubleshooting](docs/SETUP.md).

Check the saved commute without notifications or state/telemetry writes:

```sh
.venv/bin/python main.py --dry-run --no-social
```

For background monitoring, use `main.py --watch`. The active window is in
**Asia/Kolkata**, including overnight schedules. `--reverse` checks the other
direction and `--config PATH` selects another file. See the setup guide for the
optional macOS login installer. Provider checks may consume quota.

## How the repository fits together

| Path | Responsibility |
| --- | --- |
| `server.py` | Flask app factory, local HTTP protections and dashboard startup |
| `main.py` | One-shot/scheduled monitor and notification side effects |
| `services/dashboard.py`, `validation.py`, `configuration.py` | API boundary, input validation and private settings |
| `services/commute.py`, `evaluator.py` | Shared weather response, commute assessment and departure guidance |
| `services/routing.py`, `weather.py`, `tomorrow.py`, `places.py` | Provider adapters and route/forecast processing |
| `services/sources.py`, `twitter.py` | Geographic source selection and attributed public reports |
| `services/demo.py` | Explicit synthetic demo adapters; no provider calls or disk saves |
| `web/app.js`, `api.js`, `map.js` | Browser state/views, cancellable HTTP and map lifecycle |
| `web/theme.js`, `ambient.js`, `styles/` | Theme/scenery behavior and organized CSS |
| `tests/`, `.github/workflows/ci.yml` | Offline, browser and CI verification |

Read [architecture and API contracts](docs/ARCHITECTURE.md) for the data flow and
tradeoffs. The stack is Flask + Python services + plain HTML/CSS/JavaScript, with
no database, frontend build step or LLM dependency.

## Verify it

Node 22+ and the development requirements are needed for the complete checks:

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m playwright install chromium
make check
make browser
# Optional: real route/weather requests, no commute saves or notifications.
make live
```

The offline tests cover provider parsing/failure, route selection, forecast
coverage, departure timing, social freshness, request validation, secret redaction,
app isolation and notification side effects. Browser checks exercise desktop and
mobile flows, map failures, autocomplete sessions, cancellation, save/reload and
outage recovery. CI runs the offline checks on Python 3.10/3.14 and the browser
checks on 3.14. See [contributing](CONTRIBUTING.md) and [current readiness](docs/READINESS.md).

## Limits to understand

Rainfall is a model forecast. Bengaluru's 15-minute values can be interpolated
from hourly data, and nearby checkpoints can share a model grid cell. Arrival
times are distributed by road distance and do not know junction-specific delays.
A departure countdown cannot guarantee a dry trip. Recent accumulated rain is
waterlogging susceptibility, not a confirmed flood report.

X access is best effort and Bengaluru-specific; reports stay separate from
weather advice and confirmed incidents. Routes outside the city can still use
routing/weather. The evaluator targets commutes up to six hours. This is a local
personal application; public multi-user hosting requires additional design work.

Private configuration, telemetry, logs and experiments are ignored by Git.
Historical [review notes](docs/REVIEW.md) and [source research](docs/SOURCES.md)
record earlier decisions; current behavior is documented above.
