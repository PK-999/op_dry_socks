# Setup and providers

## Local setup

Use Python 3.10+. These shell commands are for macOS/Linux:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python server.py --demo
```

Open **http://localhost:5111**. The demo includes six searchable Bengaluru places,
two sample corridors, synthetic rain forecasts and in-memory saves. All browser
assets are local. Installing Python packages initially requires network access;
running the installed demo does not. `--port 5112` selects another local port.

For live mode, copy `config.json.example` to `config.json` if it does not already
exist, configure providers below, then run `.venv/bin/python server.py`. The
example's `YOUR_...` values are treated as unconfigured. Missing optional sections
inherit example defaults. Invalid JSON/settings return a redacted configuration
error. `--config PATH` or `DRYSOCKS_CONFIG` selects another file; a missing explicit
path is an error.

On Windows, use `.venv\Scripts\python.exe` in place of `.venv/bin/python`.
macOS notifications and the login installer are platform-specific.

## Credentials

Environment values override file values in memory; saves never copy those
environment credentials into the file.

| File key | Environment variable | Use |
| --- | --- | --- |
| `google_maps_token` | `GOOGLE_MAPS_API_KEY` | Server-side Routes, Places (New) and Geocoding APIs |
| `google_maps_browser_key` | `GOOGLE_MAPS_BROWSER_KEY` | Separate public Maps JavaScript API key |
| `mapbox_token` | `MAPBOX_ACCESS_TOKEN` | Optional car routing fallback, without live traffic |
| `tomorrow_io_token` | `TOMORROW_IO_API_KEY` | Optional near-term rain corroboration |
| `twitter_auth_token` | `TWITTER_AUTH_TOKEN` | User-supplied existing X session cookie |
| `twitter_bearer_token` | `X_BEARER_TOKEN` | Developer API alternative if no session cookie is configured |

The live routing path needs Google Routes with billing enabled for car and
two-wheeler modes. Search needs Places API (New); naming map-picked points needs
Geocoding. Restrict the private key to those server APIs. Mapbox is a car-only
fallback and does not substitute for motorcycle routing. Open-Meteo does not
require a key for eligible noncommercial use. Tomorrow.io minute forecasts may
require an appropriate entitlement.

For the live interactive map, create a **separate browser key** restricted to
Maps JavaScript API, with referrers `http://localhost:5111/*` and
`http://127.0.0.1:5111/*` (adjust for a different port). It is deliberately public;
the server key is never its fallback. The map uses `DEMO_MAP_ID` for development.
Search and forecast results still work without the browser map key.
See [Google key setup](https://developers.google.com/maps/documentation/javascript/get-api-key)
and [Places display requirements](https://developers.google.com/maps/documentation/places/web-service/policies).

## Optional public X reports

```sh
.venv/bin/python -m pip install -r requirements-browser.txt
.venv/bin/python -m playwright install chromium
```

Supply your existing session cookie locally; the app does not discover cookies
from browser profiles. Cookie access is best effort and may expire. The developer
bearer API alternative does not need Chromium. `social.enabled: false` disables
X. Source errors and unchecked sources remain visible. Bengaluru-specific sources
are skipped when a route is outside their coverage. Reports never automatically
become verified incidents or quantitative traffic delays.

## Scheduled checks and notifications

```sh
.venv/bin/python main.py --dry-run --no-social
.venv/bin/python main.py --watch
```

Dry runs call real configured providers but send no notifications and write no
telemetry/state. `--reverse` swaps endpoints; `--config PATH` selects a file.
The monitor respects `polling.interval_minutes` and India-time active hours,
including windows crossing midnight. Closing the browser does not stop it.
Desktop notifications use macOS `osascript` and depend on OS notification settings.

`./install.sh` is an optional **macOS login monitor installer**: it installs
Python/browser dependencies and starts the LaunchAgent. It does not start the
web dashboard. Do not also run `main.py --watch` when the installed agent is active.
`./uninstall.sh` removes that agent. Its legacy identifier is `com.varuna.daemon`.

## Common failures

| Symptom | Check |
| --- | --- |
| Routes unavailable | Routes API enabled, valid server key, billing/quota, requested travel mode |
| Search unavailable | Places API (New) enabled and authorized; autocomplete session errors |
| Map unavailable | Separate browser key, Maps JavaScript API, localhost referrers and network |
| Forecast incomplete | Provider outage, missing checkpoint data or insufficient forecast horizon |
| X unavailable | Expired cookie, bearer entitlement, missing Chromium or source time budget |
| Port already in use | Run `server.py --port 5112` and update browser key referrers |

The demo is selected explicitly with `--demo`; live failures never switch to sample data.
