"""Google Places search. No persistent cache of predictions or place details."""
import math
import re
import requests
from .configuration import configured

BASE = 'https://places.googleapis.com/v1/places'


class PlacesUnavailable(Exception):
    pass


def session_token(value):
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,36}', value):
        raise ValueError('Provide a valid search session token.')
    return value


def _key(config):
    token = config.get('google_maps_token')
    if not configured(token):
        raise PlacesUnavailable('Add GOOGLE_MAPS_API_KEY with Places API (New) enabled to use search.')
    return token


def _decode(response):
    if response.status_code in (400, 401, 403):
        raise PlacesUnavailable('Google Places could not authorize this request. Check Places API (New), billing and server key restrictions.')
    if response.status_code == 429:
        raise PlacesUnavailable('Google Places quota reached. Check your quota or try again later.')
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict) or data.get('error'):
        raise PlacesUnavailable('Google Places returned an unreadable response. Please try again.')
    return data


def autocomplete(config, query, session, lat=12.9716, lon=77.5946):
    key = _key(config)
    body = {'input': query, 'sessionToken': session, 'includedRegionCodes': ['in'],
            'languageCode': 'en', 'regionCode': 'in',
            'locationBias': {'circle': {'center': {'latitude': lat, 'longitude': lon}, 'radius': 30000.0}}}
    try:
        data = _decode(requests.post(BASE + ':autocomplete', json=body, timeout=8,
                                    headers={'X-Goog-Api-Key': key}))
        features = []
        for item in data.get('suggestions', []):
            prediction = item.get('placePrediction', {})
            if not prediction.get('placeId'):
                continue
            text = prediction.get('text', {}).get('text', '')
            structure = prediction.get('structuredFormat', {})
            features.append({'place_id': prediction['placeId'],
                             'text': structure.get('mainText', {}).get('text') or text,
                             'place_name': structure.get('secondaryText', {}).get('text') or text})
        return features
    except (requests.RequestException, ValueError, TypeError, KeyError, AttributeError):
        raise PlacesUnavailable('Google Places search is unavailable. Please try again.') from None


def details(config, place_id, session):
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,255}', place_id):
        raise ValueError('Provide a valid Google place ID.')
    key = _key(config)
    try:
        data = _decode(requests.get(BASE + '/' + place_id, params={'sessionToken': session}, timeout=8,
                                   headers={'X-Goog-Api-Key': key, 'X-Goog-FieldMask': 'id,formattedAddress,location'}))
        point = data['location']
        lat, lon = point['latitude'], point['longitude']
        if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in (lat, lon)) or not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
        return {'place_id': data.get('id', place_id), 'place_name': data.get('formattedAddress', ''), 'center': [lon, lat]}
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise PlacesUnavailable('Could not resolve this place. Please search and select it again.') from None


def reverse(config, lat, lon):
    key = _key(config)
    try:
        data = _decode(requests.get('https://maps.googleapis.com/maps/api/geocode/json',
                                   params={'latlng': f'{lat},{lon}', 'key': key, 'language': 'en'}, timeout=8))
        if data.get('status') == 'ZERO_RESULTS':
            return []
        if data.get('status') != 'OK':
            raise PlacesUnavailable('Google address lookup is unavailable. The selected coordinates are still usable.')
        return [{'text': item['formatted_address'], 'place_name': item['formatted_address'], 'center': [lon, lat]}
                for item in data.get('results', [])[:1]]
    except (requests.RequestException, ValueError, KeyError, TypeError):
        raise PlacesUnavailable('Google address lookup is unavailable. The selected coordinates are still usable.') from None
