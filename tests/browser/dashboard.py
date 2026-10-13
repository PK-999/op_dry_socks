"""Full offline UI → Flask → demo → save/reload regression.

Run with Python after installing requirements-dev.txt and Playwright Chromium.
All HTTP responses come from the real app; external requests are forbidden.
"""

import sys
from pathlib import Path
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from server import create_app


def run():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        for width in (1440, 390):
            web = create_app(demo=True).test_client()
            context = browser.new_context(
                viewport={"width": width, "height": 1000},
                color_scheme="dark",
                reduced_motion="reduce",
                timezone_id="America/Los_Angeles",
            )
            page = context.new_page()
            errors, external = [], []
            fail_weather = False
            page.on("pageerror", lambda error: errors.append(str(error)))

            def respond(route):
                url = urlparse(route.request.url)
                if url.hostname != "localhost":
                    external.append(route.request.url)
                    route.abort()
                    return
                if fail_weather and url.path == "/api/weather":
                    route.fulfill(status=503, json={"error": "Forecast temporarily unavailable."})
                    return
                path = url.path + ("?" + url.query if url.query else "")
                response = web.open(
                    path,
                    method=route.request.method,
                    data=route.request.post_data,
                    content_type="application/json" if route.request.method == "POST" else None,
                )
                route.fulfill(
                    status=response.status_code,
                    content_type=response.content_type,
                    body=response.data,
                )

            page.route("**/*", respond)
            page.goto("http://localhost:5111/", wait_until="networkidle")
            page.wait_for_function("state.weather !== null && !state.weatherLoading")
            assert page.locator("#demo-notice").is_visible()
            assert page.locator("#map").get_attribute("data-provider") == "demo"
            assert page.locator(".route-option").count() == 2
            assert page.locator(".forecast-table tbody tr").count() >= 2
            assert "Demo" in page.locator("#forecast-source").inner_text()
            assert "disabled in the demo" in page.locator("#reports-content").inner_text()

            # Route choice survives a save and page reload through the real Flask app.
            page.locator(".route-option").nth(1).click()
            page.wait_for_function("state.selectedRoute === 1 && !state.weatherLoading")
            page.locator("#save-btn").click()
            page.wait_for_function("!state.saving && state.savedFingerprint === fingerprint()")
            page.reload(wait_until="networkidle")
            page.wait_for_function("state.selectedRoute === 1 && state.weather !== null")
            assert (
                web.get("/api/config").json["route"]["selected_route"]["summary"]
                == "Sample corridor 2"
            )

            page.locator('[data-mode="DRIVE"]').click()
            page.wait_for_function("state.travelMode === 'DRIVE' && state.weather !== null")
            page.locator("#swap-btn").click()
            page.wait_for_function("state.origin.name === 'Indiranagar' && state.weather !== null")

            page.locator("#destination-input").fill("bellan")
            page.wait_for_selector("#destination-option-0")
            assert "Demo places" in page.locator("#destination-results").inner_text()
            page.locator("#destination-input").press("ArrowDown")
            page.locator("#destination-input").press("Enter")
            page.wait_for_function(
                "state.destination?.name === 'Bellandur' && state.weather !== null"
            )

            # A provider failure removes prior advice; a later refresh can recover.
            fail_weather = True
            page.locator("#refresh-btn").click()
            page.wait_for_function(
                "document.querySelector('#advice-title').textContent === 'The forecast is out of reach.'"
            )
            assert page.locator("#departure-window").is_hidden()
            fail_weather = False
            page.locator("#refresh-btn").click()
            page.wait_for_function("state.weather !== null && !state.weatherLoading")
            assert page.locator("#advice-title").inner_text() != "The forecast is out of reach."
            before = page.locator("html").get_attribute("data-theme")
            page.locator("#theme-toggle").click()
            assert page.locator("html").get_attribute("data-theme") != before
            page.locator("#theme-toggle").click()

            assert not errors, errors
            assert not external, external
            assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
            assert page.evaluate(
                "document.querySelector('header').scrollWidth <= window.innerWidth"
            )
            screenshot = ROOT / "artifacts" / f"dashboard-demo-{width}.png"
            screenshot.parent.mkdir(exist_ok=True)
            page.screenshot(path=str(screenshot), full_page=True, animations="disabled")
            print(
                f"{width}px: full demo pipeline, alternatives, save/reload, mode, swap, search, outage/recovery passed; no external requests"
            )
            context.close()
        browser.close()


if __name__ == "__main__":
    run()
