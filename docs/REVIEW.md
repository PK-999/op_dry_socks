# Codebase review and implemented improvements

Reviewed on 3 October 2026. The initial checkout already contained local edits,
an untracked Flask server/UI and exploratory scripts. Those files were improved
in place. Existing `config.json`, `scratch/`, and telemetry were not reset.

## Intent and architecture

The useful decision is whether a commuter should leave sooner because rain may
overlap their journey. A citywide rain forecast alone is insufficient: the route,
its duration, where rain is forecast, and when the commuter reaches that point
all matter. Traffic-police reports add local context and disruption evidence,
but a station's jurisdiction is not the same as an incident location.

The original system had two divergent applications. `main.py` used legacy routing,
per-point forecast calls and an evaluator; `server.py` duplicated weather logic
and offered a UI with independent risk rules and random advisory endpoints.
They could disagree about the same journey. A UI route choice was not persisted
to the notification runner.

The current flow is:

```text
Browser or scheduled runner
  → fresh route alternatives (shared routing.py)
  → selected road geometry + distance-based checkpoint ETAs
  → batch weather request (shared weather.py)
  → departure guidance (shared evaluator.py)

Selected road geometry
  → source selection before fetching (sources.py)
  → citywide + relevant local X timelines (twitter.py)
  → attributed, freshness-checked reports shown separately
```

Flask remains a small local service. The frontend uses ordinary HTML/CSS/JS
without a build tool. No hosted database, cloud deployment or LLM is required.

## Findings and changes

| Priority | Finding in original checkout | Result |
| --- | --- | --- |
| Critical to trust | Weather timeouts returned the same sentinel as a dry forecast. | Missing data is now explicit `None` / `UNKNOWN`; incomplete coverage cannot yield a clear recommendation. |
| Critical to trust | A Tomorrow.io failure or disagreement erased an Open-Meteo rain warning. | A second provider can strengthen a warning, never erase one. Intensity units are converted from mm/hour to the configured mm/15-minute threshold. |
| Critical to trust | `/api/btp` and `/api/waterlogging` returned random simulated events. Missing X credentials also fabricated recent posts. | Removed all production mock events. Flood endpoint retired; forecast susceptibility and original X reports are distinct. |
| High | UI weather rules ignored commute duration and differed from daemon rules. | Both use `departure_advice`; arrival time at each point and safety buffer determine the departure window. |
| High | Credential-filled config was served with unrestricted CORS; Flask listened on every interface with debug enabled. | Public config is redacted, writes are same-origin, requests are validated, writes atomic, and server binds to loopback without debug. |
| High | Backend hardcoded motorcycle mode; decimal Google durations could fail. | Requested mode is forwarded, durations accept decimal seconds and round up. |
| High | Save stored only endpoints; UI and daemon could monitor different routes/modes. | Save stores mode and preferred geometry; runner matches the preference to fresh alternatives and fresh travel time. |
| High | Sampling measured displacement from the last point and skipped bends. | Sampling uses cumulative road distance with interpolation and includes both endpoints. |
| High | X only checked one account; geocoding failure treated unrelated locations as relevant. | All requested accounts plus four researched additions are registered. Local accounts are selected before fetching using route-segment/area intersection. |
| High | Invalid/missing social timestamps were accepted; reports lacked stable provenance. | Reject missing, malformed, future, stale and wrong-author records; retain canonical original links and source status. |
| Medium | Heavy provider requests were repeated; one X browser was needed per profile. | Weather and X cache for two minutes; X shares one browser context. Optional Tomorrow calls are capped at three concurrent checks. |
| Medium | Global notification state suppressed an alert for a different commute, failed delivery was consumed, and clear-state cooldown could block urgency. | State includes commute identity; unsuccessful delivery is not recorded; escalation bypasses cooldown. |
| Medium | Active hours used host time and failed across midnight. Installer paths depended on the invoking directory. | India-time windows support midnight, monitor respects polling interval, installer works from its own directory. |
| High for developer safety | Top-level live test shallow-copied config, changed the user's saved route and could run on test discovery. | Offline discovery is scoped to `tests/`; explicit live checks use in-memory copies and reject incomplete provider data. |

The unused Gemini parser, OCR utility and their optional dependencies were removed
during cleanup. The parser had an unescaped JSON-template formatting bug and an
obsolete model identifier. Reintroducing incident extraction requires
a maintained provider, structured outputs, event-time validation and evidence of
location relevance. Raw source text and original images remain accessible through
the source links without an LLM.

## UI behavior

The responsive dashboard puts the departure outlook first, with car/two-wheeler
selection, search or map-picked endpoints, alternative routes, saved commute,
checkpoint rainfall and public source reports. Source status and forecast
freshness remain visible. Keyboard search and labelled controls are supported.
Changing endpoints, mode or route invalidates old results immediately; stale
network responses cannot replace the newly selected route. Browser monitoring is
explicitly on demand; the separate runner owns background notifications.

## Remaining limitations and suggested priorities

1. **Add IMD nowcasts and observations.** The current official IMD API reference
   documents district/station nowcasts and AWS/ARG observations. Add a separate
   adapter, reject expired warnings, and show warning validity alongside the
   existing model forecast. Confirm portal access and local station coverage.
   [Integration details](SOURCES.md#recommended-next-integrations).
2. **Measure forecast usefulness.** Let a commuter record “rain here now” and
   arrival time locally; compare predictions with outcomes to tune the safety
   buffer. Current rainfall thresholds are heuristics, not calibrated accuracy.
3. **Use better geographic evidence.** Replace approximate station circles with
   verified jurisdiction polygons where available. Extract an incident's location
   and event interval before allowing a post to affect automated advice. Keep
   Kannada text and image-only advisories available at the original source.
4. **Add structured traffic incidents.** TomTom provides a compatible REST option
   with India coverage. Filter incident geometry against the route and compare
   traffic ETA changes, keeping reported closures separate from forecast rain.
5. **Improve scheduling.** Add weekday/morning/evening profiles, arrive-by time,
   snooze and per-mode buffers. Surface actual monitor heartbeat in the dashboard
   before adding a button that claims to enable notifications.
6. **Improve precipitation timing.** The current evaluator conservatively treats
   the first rain signal before arrival as a conflict. Future logic should examine
   the complete wet interval and rain stopping time, with uncertainty bounds,
   before recommending a later departure.

The browser X reader is bounded and best effort: it may miss posts outside the
first rendered articles or leave sources unchecked when its time budget expires.
Historical identity evidence for added accounts does not prove present account
ownership. Automatic warnings currently come from route/weather assessment;
unclassified social posts are displayed, not promoted to confirmed disruptions.

## Verification

Final verification: **59 offline tests passed**. JavaScript syntax, Python
compilation and installer shell syntax checks passed. Chromium checks at desktop
and mobile sizes covered route alternatives, keyboard search, swapping endpoints,
travel modes, refresh, stubbed saves, stale responses, map-loading failure and
error recovery. The final live dashboard had no JavaScript errors or page overflow.
The local screenshot is saved at `artifacts/dashboard-live.png` (git-ignored).
After a user-reported map block, the document referrer policy was corrected and
tile responses now undergo an HTTP status check before image rendering. A
separate browser regression intercepts all tile traffic and covers success,
403 responses containing valid PNGs, partial failures and reload recovery.
A live check on this machine returned two Google route alternatives, weather for
all four selected-route checkpoints, and successful timeline reads from
`Bengalururain`, `blrcitytraffic`, and the route-relevant `halairporttrfps`, with one
recent report returned. That verifies the current credentials and adapters for
those requests; it is not a guarantee of future source availability or completeness.
No notifications were sent and no user configuration was changed by that check.

## Google place search update — 4 October 2026

Replaced legacy Text Search plus silent Photon fallback with Places Autocomplete
(New), raw partial input, India country filtering and a local location bias.
A selected prediction resolves through Place Details using the same session token.
The UI rotates tokens after Details, ignores obsolete requests and attributes Google.
Coordinate validation now accepts valid geographic coordinates outside Bengaluru;
Bengaluru social accounts are only fetched for routes intersecting its approximate
coverage. The map uses Google Maps JavaScript with a separate public browser key.
Missing keys/provider failures leave search, routing and weather available.

Live autocomplete and Details checks succeeded for `hoodi metr`, `Manyata Tech Park`
and `Connaught Place Delhi`. Tests cover API errors, input validation, secret redaction,
India-wide coordinates and X coverage. Browser fixtures cover keyboard/mouse selection,
sessions, stale responses, desktop/mobile layout and the map adapter. A real Google
basemap remains unverified until the browser key is added locally.
