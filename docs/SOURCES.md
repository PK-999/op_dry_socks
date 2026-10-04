# Source registry and integration notes

Research checked on **3 October 2026**. This document records identity evidence and technical limits. It does not attest that an X timeline was successfully read live. Several direct X profile requests returned empty content or access errors during research.

## Which X accounts are selected

`services/sources.py` selects `Bengalururain` and `blrcitytraffic` for routes intersecting an approximate 45 km Bengaluru coverage circle. Outside that coverage, no Bengaluru accounts are fetched. It selects a local station before any network request when the route intersects an approximate area circle. The algorithm tests each full line segment, so an area between distant sample points is not skipped. GeoJSON coordinates are longitude, latitude; waypoint dictionaries use `lat` and `lon`.

The circles are manually chosen neighborhood approximations, **not official police jurisdiction boundaries**. They can include nearby streets outside a station's remit and miss outlying streets. A selected station's post is an area report, not evidence that a particular incident is on the route. Citywide posts retain their citywide label. A route should supply its actual road geometry; straight lines between endpoints are an approximation.

| Account | Selection area | Identity evidence |
| --- | --- | --- |
| [@Bengalururain](https://x.com/Bengalururain) | Always, citywide weather | User requested independent weather account; not an IMD/government feed. Current ownership was not independently confirmed through an authoritative site. |
| [@blrcitytraffic](https://x.com/blrcitytraffic) | Always, citywide traffic | Named by BTP's own [traffic warden notice](https://btp.gov.in/images/TWO%20Note%20English.pdf). |
| [@wftrps](https://x.com/wftrps) | Whitefield and Varthur | User supplied. Profile link retained; no current official-domain directory located. |
| [@halairporttrfps](https://x.com/halairporttrfps) | HAL, Old Airport Road, Marathahalli | User supplied. Profile link retained. |
| [@hsrltrafficps](https://x.com/hsrltrafficps) | HSR Layout and Agara | User supplied; historical post reproduced in the CAG evidence below. |
| [@JnagarTr](https://x.com/JnagarTr) | Jayanagar | User supplied. Profile link retained. |
| [@halasoortrfps](https://x.com/halasoortrfps) | Halasuru / Ulsoor | User supplied. Profile link retained. |
| [@yprtrps](https://x.com/yprtrps) | Yeshwanthpur | User supplied. Profile link retained. |
| [@madivalatrfps](https://x.com/madivalatrfps) | Madiwala and Silk Board | User supplied. Profile link retained. |
| [@bellandurutrfps](https://x.com/bellandurutrfps) | Bellandur, ORR, Kadubeesanahalli | User supplied. Profile link retained. |
| [@ashoknagartfps](https://x.com/ashoknagartfps) | Ashok Nagar and Richmond Road | Added from the CAG's primary government audit evidence. Historical, not proof of current account control. |
| [@adugoditraffic](https://x.com/adugoditraffic) | Adugodi and Hosur Road | Added from the same historical government evidence. |
| [@chickpetetrfps](https://x.com/chickpetetrfps) | Chickpet and City Market | Added from the same historical government evidence. |
| [@kengeritrfps](https://x.com/kengeritrfps) | Kengeri and Mysuru Road | Added from its [indexed X profile](https://x.com/kengeritrfps/with_replies), which identifies it as Kengeri Traffic Police and links to BTP. Direct live access was unavailable during research. |

The Comptroller and Auditor General's [2021 audit, Chapter IV, Exhibit 4.10, printed page 58](https://cag.gov.in/uploads/download_audit_report/2021/6.%20Chapter%204-0614304648218f2.56827708.pdf) reproduces 2018 waterlogging posts from HSR, Adugodi, Ashok Nagar, Chickpet, Mico Layout, and the older Whitefield handle. Only the three added accounts named above enter this registry; the old Whitefield handle is not substituted for the user's requested `wftrps`.

Candidates such as `KRPURATRAFFIC` and `mahadevapuratrf` appeared in search results and third-party mirrors, but no sufficiently strong current primary identity confirmation was obtained. They are not silently added. Extend the registry after checking primary identity evidence and local coverage.

## X access behavior

The app uses the explicitly configured `twitter_auth_token` cookie first, honoring the existing-browser-login preference. It does not extract cookies from browser profiles or reveal credentials in results. Playwright imports only when X is enabled with a supplied cookie. One temporary browser context serves the selected accounts. An optional developer bearer token is supported when no cookie is supplied; it never automatically replaces an expired supplied browser cookie.

The browser adapter reads the first visible timeline posts, up to 20 articles per source, without unbounded scrolling. Each navigation has a 5-second limit, timeline waiting a 2.5-second limit, and the fetch loop a 25-second budget including launch. A slow batch can leave some sources unchecked; those show unavailable rather than silently clear. Browser setup/cleanup has overhead beyond the loop budget. X can require reauthentication, throttle reads, change its DOM, or show incomplete timelines. A successful page read is not an exhaustive monitoring guarantee.

The optional API adapter uses recent search with `from:HANDLE`, excludes reposts/replies, resolves the returned author ID, and reads one page of up to 20 posts. X's [recent-search documentation](https://docs.x.com/x-api/posts/search/introduction) states a seven-day search window. API access requires a developer credential and available access/credits. The [official pricing page](https://docs.x.com/x-api/getting-started/pricing) currently lists post reads at **US$0.005 per returned post**, user reads at **US$0.010 per resource**, and a three-million-post monthly cap for pay-per-use. Repeated resources are normally deduplicated within a UTC day, but X describes that as a soft guarantee. Check current pricing before enabling billed access.

Application cache entries expire after 120 seconds for successful reads and 30 seconds for failures. Cache keys include credential fingerprints; credentials are not returned. Posts are age-filtered again on each read. Missing, invalid, timezone-less, future, or older-than-two-hour timestamps are rejected by default. Wrong-author permalinks and reposts are excluded; canonical permalinks deduplicate reports. Image reports retain their original post link, without invented OCR text. `updated_at` is the response time; each source's `checked_at` is its actual fetch time, and `cached` distinguishes reuse.

Missing credentials produce `unavailable` / `not_configured`; disabling X produces `disabled`; mixed source success produces `partial`. None of these states generate sample posts or imply that roads are clear. Display raw reports as source updates. They can include general announcements, and their event period may differ from the posting time.

## Weather and traffic providers

| Provider | Practical use | Verified limitations |
| --- | --- | --- |
| [Open-Meteo forecast API](https://open-meteo.com/en/docs) | Coordinate-based rainfall forecasts along the route | In Bengaluru, 15-minute values are interpolated from hourly forecasts. Current conditions are model estimates. Minute-level rain-onset certainty and observed street flooding cannot be inferred from this product. |
| [Open-Meteo access plans](https://open-meteo.com/en/pricing) | Keyless personal evaluation and noncommercial use | Free access lists 600/minute, 5,000/hour, 10,000/day and 300,000/month limits, no uptime guarantee, and attribution requirements. Commercial service access needs a paid plan. |
| [IMD API reference](https://api.imd.gov.in/public/api_reference.html) and [Bengaluru centre](https://mausam.imd.gov.in/bengaluru/) | Official district/station nowcasts, warnings, AWS/ARG observations and forecast links | Current documented APIs exist through the IMD portal. Access/registration and station mapping must be confirmed; district warnings are not a street-level rainfall forecast. |
| [Tomorrow.io forecast API](https://docs.tomorrow.io/reference/weather-forecast) | Optional second weather provider | Official documentation lists minute forecasts for premium users for the next hour, hourly forecasts for 120 hours, daily forecasts for five days. Bengaluru-specific minute-product skill and account entitlement still need checking; an error must not override another provider's rain forecast as dry weather. |
| [Google Routes traffic options](https://developers.google.com/maps/documentation/routes/traffic-opt) | Traffic-sensitive routing and estimated arrival time | Traffic model settings affect both route choice and duration. Traffic-aware polylines incur higher billing. An ETA does not establish that a street is free of waterlogging. |
| [Mapbox Directions](https://docs.mapbox.com/api/navigation/directions/) | Alternative route geometry and driving duration | `driving-traffic` combines current and historical traffic where supported. Traffic coverage is geography-dependent; a returned driving route alone is not proof of live local traffic coverage. |
| [TomTom Calculate Route](https://docs.tomtom.com/routing-api/documentation/tomtom-maps/v1/calculate-route) | A candidate additional route/traffic provider | Supports separate no-traffic, historical-traffic and live-incident travel-time summaries. [India is listed for traffic incidents and flow](https://docs.tomtom.com/traffic-api/documentation/tomtom-maps/v1/product-information/market-coverage). It is not integrated here; test route-specific coverage with an account before adopting it. |
| [Bengaluru Traffic Police website](https://btp.karnataka.gov.in/) | Official dated traffic notices and planned works | The homepage exposed congestion timestamps, map links and works during research; several work entries had missing locations. A stable public API was not verified. Do not interpret missing fields or old notices as current route incidents. |

Forecast agreement is corroboration, not proof. Keep model rainfall, traffic travel estimates, and police/citizen source reports visibly distinct. Rain accumulation can indicate a reason for caution; it is not an observation of waterlogging or a calibrated flooding probability.

## Recommended next integrations

**First: IMD.** The current [API reference](https://api.imd.gov.in/public/api_reference.html) documents `/api/v1/districtnowcast`, `/api/v1/districtwarning`, `/api/v1/current_wx`, `/api/v1/aws_data` and station mapping endpoints. Register through the [official access portal](https://api.imd.gov.in/public/index.php); the [IMD API guidance](https://mausam.imd.gov.in/responsive/apis.php) also describes IP whitelisting, attribution and caching. Do not assume anonymous access or hardcode a district ID without consulting its mapping.

Proposed Python integration: `services/imd.py` returns attributed notices with `issued_at`, `valid_until`, `area`, `severity` and original message. Match Bengaluru Urban/Rural district IDs and nearby observation stations to the route; show notices beside the existing source feed. District nowcasts contain issue/expiry times and severity categories, so they should not be forced into an exact `mins_to_rain` value. Observation timestamps and nearby-station distance should be visible. This is a proposed adapter, not enabled code.

**Second: TomTom traffic incidents/flow.** Its documented REST API and India coverage fit the existing requests-based stack. A `services/tomtom.py` adapter could request the route bounding box, then discard incidents whose geometry does not intersect a narrow route corridor. Normalize records to source, geometry, event validity, description and delay fields, and return unknown when coverage is absent. Credentials remain server-side. Trial response quality for the user's roads before switching ETA providers; national coverage is not proof that every junction is instrumented.

**Third: BTP's official notice page.** A small cached HTML adapter can complement X for planned roadworks/events where the official page supplies location and validity. Reject incomplete coordinates and expired events. There is no verified stable public JSON contract here, so this adapter needs saved response fixtures and a visible parser-failure state. It is a lower priority than the documented APIs.

The original X integration is live-verified for the current commute: the two citywide timelines and HAL Airport timeline returned successfully on 3 October 2026. Other registry accounts were researched and covered by offline selection/ingestion tests, not all individually live-read.
