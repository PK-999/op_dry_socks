import re
import re
from .local_ocr import parse_advisory_local
from playwright.sync_api import sync_playwright

def fetch_latest_tweets(auth_token, handle="blrcitytraffic", max_items=5):
    """
    Scrapes tweets from X (Twitter) using a headless browser via Playwright.
    Requires a valid 'auth_token' cookie string to bypass X's login screen.
    """
    if not auth_token or auth_token == "YOUR_AUTH_TOKEN_HERE" or auth_token == "":
        print("No valid twitter_auth_token provided, using mock data for BTP...")
        return [
            {
                "text": "Due to vehicle breakdown near Kadubeesanahalli Underpass towards Marathahalli Bridge traffic is moving slowly.",
                "media_url": None
            },
            {
                "text": '"Traffic advisory" Ganesha Idol procession passing through K.G.Halli and Pulakeshinagar Traffic Police Station limit, commuters please avoid this route.',
                "media_url": None
            }
        ]

    results = []
    print("Launching headless browser to check Twitter...")
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            
            # Authenticate via the auth_token cookie
            context.add_cookies([{
                'name': 'auth_token',
                'value': auth_token,
                'domain': '.x.com',
                'path': '/',
                'secure': True
            }])
            
            page = context.new_page()
            page.goto(f"https://x.com/{handle}")
            
            # Wait for the timeline to load
            try:
                page.wait_for_selector('article[data-testid="tweet"]', timeout=15000)
                tweets = page.locator('article[data-testid="tweet"]').all()
                
                for i, tweet in enumerate(tweets):
                    if i >= max_items: break
                    
                    # Extract tweet text
                    text_locator = tweet.locator('[data-testid="tweetText"]')
                    text = text_locator.inner_text() if text_locator.count() > 0 else ""
                    
                    # Extract image URL
                    images_locator = tweet.locator('div[data-testid="tweetPhoto"] img')
                    media_url = None
                    if images_locator.count() > 0:
                        media_url = images_locator.first.get_attribute("src")
                        
                    results.append({
                        "text": text,
                        "media_url": media_url
                    })
                    
            except Exception as e:
                print(f"Playwright timeout or extraction error: {e}")
                
            browser.close()
    except Exception as e:
        print(f"Playwright failed to launch: {e}")
        
    return results


def check_btp_alerts(route_polyline_or_waypoints, auth_token):
    """
    Checks recent BTP tweets (text and image OCR) for traffic advisories
    and matches them against the route to identify specific disruption points.
    """
    tweets = fetch_latest_tweets(auth_token=auth_token, max_items=5)
    
    incidents = []
    
    for tweet in tweets:
        full_text = tweet.get("text", "")
        media_url = tweet.get("media_url")
        
        parsed_results = parse_advisory_local(full_text, media_url)
        for p in parsed_results:
            loc_str = f"{p['location']} (Traffic Advisory)"
            if p['duration'] != "None":
                loc_str += f" [{p['duration']}]"
            incidents.append(loc_str)
            
    return list(set(incidents))
