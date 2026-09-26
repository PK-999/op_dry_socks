import pytesseract
from PIL import Image
import requests
import io
import re
import logging

logger = logging.getLogger(__name__)

def parse_advisory_local(tweet_text, media_url):
    combined_text = tweet_text
    
    if media_url:
        try:
            resp = requests.get(media_url, timeout=10)
            if resp.status_code == 200:
                img = Image.open(io.BytesIO(resp.content))
                ocr_text = pytesseract.image_to_string(img)
                combined_text += "\n" + ocr_text
        except Exception as e:
            logger.error(f"OCR Error: {e}")
            
    locations = []
    
    match_procession = re.search(r'passing through (.*?) and (.*?) Traffic', combined_text, re.IGNORECASE)
    if match_procession:
        locations.extend([match_procession.group(1).strip(), match_procession.group(2).strip()])
        
    match_near = re.search(r'near\s+(.*?)\s+towards\s+(.*?)\s+(?:is|will|having)', combined_text, re.IGNORECASE)
    if match_near:
        locations.extend([match_near.group(1).strip(), match_near.group(2).strip()])

    match_restricted = re.search(r'Restricted Places:?([\s\S]*?)public are requested', combined_text, re.IGNORECASE)
    if match_restricted:
        places_str = match_restricted.group(1)
        places = [p.strip() for p in places_str.split(',') if len(p.strip()) > 3]
        locations.extend(places)

    duration = "None"
    match_duration = re.search(r'on (\d{1,2}(?:st|nd|rd|th)? \w+ \d{4}.*?(?:AM|PM))', combined_text, re.IGNORECASE)
    if match_duration:
        duration = match_duration.group(1).strip()
    else:
        match_dur2 = re.search(r'from (\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4}) to (\d{1,2}[\./-]\d{1,2}[\./-]\d{2,4})', combined_text, re.IGNORECASE)
        if match_dur2:
            duration = f"From {match_dur2.group(1)} to {match_dur2.group(2)}"
            
    results = []
    if locations:
        for loc in set(locations):
            results.append({
                "location": loc,
                "reason": "Traffic Advisory",
                "duration": duration
            })
            
    return results
