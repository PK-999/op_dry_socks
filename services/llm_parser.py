import google.generativeai as genai
import requests
import json
import logging

logger = logging.getLogger(__name__)

def parse_advisory(tweet_text, media_url, gemini_api_key):
    if not gemini_api_key or gemini_api_key == "YOUR_GEMINI_API_KEY":
        return []
        
    genai.configure(api_key=gemini_api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
    
    prompt = """
    Extract all traffic incident locations and their scheduled durations from the provided text and image.
    Return ONLY a JSON list of objects with this exact format, with no markdown formatting:
    [
      {
        "location": "Name of the specific road, junction, or underpass",
        "reason": "Brief reason (e.g. vehicle breakdown, procession)",
        "duration": "Specific date and time (e.g. '18th Sep 11:00 AM to 04:00 AM' or 'None' if not mentioned)"
      }
    ]
    Text from tweet: {tweet_text}
    """
    
    try:
        contents = [prompt.format(tweet_text=tweet_text)]
        
        if media_url:
            resp = requests.get(media_url)
            if resp.status_code == 200:
                img_data = resp.content
                contents.append({"mime_type": "image/jpeg", "data": img_data})
                
        response = model.generate_content(contents)
        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:-3]
            
        return json.loads(response_text)
    except Exception as e:
        logger.error(f"Gemini API error: {e}")
        return []
