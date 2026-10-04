# Dry Socks

A locally running Bengaluru commute assistant. Choose your route, check rainfall
forecasts along it, and read recent citywide and relevant neighbourhood X reports.
The departure estimate includes a safety buffer and approximate arrival time at
each weather checkpoint.

## Run locally

Python 3.10+ is required. On a fresh checkout:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium
cp -n config.json.example config.json
python server.py
```

Open **http://localhost:5111**. On this existing checkout, dependencies and
configuration are already present: `.venv/bin/python server.py` is enough.

The dashboard checks on demand. Save a commute, then run the monitor separately:

```sh
.venv/bin/python main.py --watch
```

The monitor respects `polling.active_hours_start`, `active_hours_end`, and
`interval_minutes`. Times are **Asia/Kolkata**, including windows crossing midnight.
macOS desktop notifications use `osascript`. Keep the process running; closing
the browser does not stop a separately running monitor. Other operating systems
can use the dashboard and printed checks; native notifications are macOS-only.

For one check without notifications, telemetry, or state writes:

```sh
.venv/bin/python main.py --dry-run
```

`--reverse` checks the opposite direction; `--no-social` skips X;
`--config /path/to/config.json` uses another configuration. `--dry-run` still calls
the configured providers and may use their quota.

Optional macOS login startup: `./install.sh` creates the environment, installs
Chromium, and installs/reloads the LaunchAgent. It runs the monitor, not the web
server. Do not run `--watch` separately if the LaunchAgent is already active.
Use `./uninstall.sh` to remove it.

## Configure providers

Keep secrets in the ignored `config.json`, or use these environment variables:

| Config setting | Environment alternative | Purpose |
| --- | --- | --- |
| `google_maps_token` | `GOOGLE_MAPS_API_KEY` | Enable Google Routes API and billing for traffic-aware car / two-wheeler routes. Enable Places API (New) for search and Geocoding API for names of map-picked points. This key stays server-side. |
| `google_maps_browser_key` | `GOOGLE_MAPS_BROWSER_KEY` | Separate, public browser key restricted to Maps JavaScript API and localhost referrers. |
| `mapbox_token` | `MAPBOX_ACCESS_TOKEN` | Optional car routing fallback; explicitly labelled as not live traffic. Never substitutes for motorcycle routing. |
| `tomorrow_io_token` | `TOMORROW_IO_API_KEY` | Optional corroboration of near-term rain at up to three checkpoints. Minute forecast entitlement may be required. |
| `twitter_auth_token` | `TWITTER_AUTH_TOKEN` | Your existing X session cookie; this is the selected method for this project. |
| `twitter_bearer_token` | `X_BEARER_TOKEN` | Optional developer API alternative only when no session cookie is configured. |

Open-Meteo needs no key for eligible noncommercial use. Google Maps displays the
route; an internet connection is needed for live data and map assets. Search,
routing and forecasts work even without a browser map key.

### Google search and map setup

Search uses **Places Autocomplete (New)** with India as the country restriction,
no place-type filter, and a 30 km location bias around the map / other endpoint
(Bengaluru by default). Your input is sent unchanged: no forced city suffix.
Google supplies up to five predictions; refine the name or add a locality for
more relevant matches. Coverage and rankings are Google's, not an exhaustive
local directory. Each field has its own autocomplete session; Place Details is
requested only after selection. Predictions and details are not server-cached.
Provider errors are visible; search no longer silently falls back to Photon.

For the interactive map:

1. In your Google Cloud project, enable **Maps JavaScript API**.
2. Create a **separate browser API key**, restricted to that API. Use website
   restrictions allowing `http://localhost:5111/*` and `http://127.0.0.1:5111/*`.
3. Add `"google_maps_browser_key": "your-browser-key"` to your local `config.json`,
   or set `GOOGLE_MAPS_BROWSER_KEY` before starting the server. Reload the page.
   Keep the existing `google_maps_token` private; it is never used as a browser-key fallback.

The map uses Google's `DEMO_MAP_ID` for local development; use your own JavaScript
map ID before deploying. Map loading, authorization and network errors show a
fallback without disabling location search. Existing Places/Routes billing still
applies; the browser map is a separate Google API. See [Google's key setup](https://developers.google.com/maps/documentation/javascript/get-api-key)
and [Places policies](https://developers.google.com/maps/documentation/places/web-service/policies).

Routes and searches can extend beyond Bengaluru. X traffic/weather sources remain
Bengaluru-specific and are skipped when a route does not intersect its approximate
45 km coverage circle. The weather evaluator is intended for commutes of up to
six hours, not multi-day intercity journey planning.

Your existing X cookie is reused. The app does not extract cookies from your
browser profile. If login expires, update it locally; the UI shows the affected
sources as unavailable. A Playwright browser is only needed for cookie-based X
access. `social.enabled: false` disables X completely.

Route choices and travel mode save through the UI. The monitor fetches fresh
alternatives and selects the closest shape to the saved preference, using the new
ETA. Provider alternatives can change; the saved route is a preference, not a
guarantee of identical roads on the next check.

## How to read the outlook

- **No immediate rain signal:** the available forecast does not indicate rain
  overlap for a departure now. A future estimated departure deadline may appear.
- **Consider leaving soon:** the estimated window is narrow after allowing for
  checkpoint arrival times and your safety buffer.
- **Rain likely / overlap possible:** consider another time or protection.
- **Waterlogging possible:** recent model rainfall exceeds the configured
  threshold. This is susceptibility, not a confirmed flood report.
- **Forecast incomplete:** a route point or required forecast horizon is missing.
  No clear-weather recommendation is made.

Bengaluru's Open-Meteo 15-minute values are interpolated from hourly forecasts.
Multiple nearby checkpoints can represent the same model grid cell. Neither
their spacing nor a numerical countdown establishes street-level precision.
Checkpoint ETAs distribute the route duration by road distance; they do not know
exact junction delays. X reports are separate context and never become invented
rainfall, verified route incidents, or numerical traffic delays.

## Verification and project notes

```sh
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
node --check web/app.js
node --test tests/test_theme.js
# Browser regression with intercepted Google/API fixtures:
.venv/bin/python tests/browser/google_places.py
```

The offline suite covers route selection, source filtering, timestamp validity,
provider outages, departure timing, request validation, credential redaction and
notification side effects. `pytest.ini` excludes exploratory `scratch/` scripts.
Local credentials, generated `telemetry.csv`, scratch experiments, browser artifacts
and logs are ignored by Git. They are not needed in a fresh checkout.
An optional `.venv/bin/python e2e_test.py --live` calls real route/weather providers
without changing your commute or sending notifications; incomplete data fails it.

See [the code review and feature priorities](docs/REVIEW.md) and
[source research with integration recommendations](docs/SOURCES.md).

The browser regression covers keyboard selection, independent billing sessions,
delayed responses, provider errors, missing map keys and mobile layout. The actual
Google map needs one live visual check after the browser key is configured.
