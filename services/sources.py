"""Bengaluru source selection; circles are heuristics, not police boundaries.

Geometry follows GeoJSON [longitude, latitude]. Waypoints are lat/lon dicts.
Evidence and limitations are recorded in docs/SOURCES.md.
"""

import math


CAG_EVIDENCE = 'https://cag.gov.in/uploads/download_audit_report/2021/6.%20Chapter%204-0614304648218f2.56827708.pdf'


def _source(handle, name, area, circles=(), kind='traffic', evidence=None):
    return {'handle': handle, 'name': name, 'scope': 'route' if circles else 'citywide',
            'area': area, 'kind': kind, 'circles': circles,
            'url': f'https://x.com/{handle}', 'coverage': 'approximate' if circles else 'citywide',
            'evidence_url': evidence or f'https://x.com/{handle}'}


SOURCE_REGISTRY = (
    _source('Bengalururain', 'Bengaluru Rain', 'Bengaluru', kind='weather'),
    _source('blrcitytraffic', 'Bengaluru Traffic Police', 'Bengaluru',
            evidence='https://btp.gov.in/images/TWO%20Note%20English.pdf'),
    _source('wftrps', 'Whitefield Traffic Police', 'Whitefield / Varthur',
            ((12.9698, 77.7500, 3.0), (12.9400, 77.7470, 2.4))),
    _source('halairporttrfps', 'HAL Airport Traffic Police', 'HAL / Old Airport Road / Marathahalli',
            ((12.9590, 77.6660, 2.5), (12.9550, 77.6980, 2.0))),
    _source('hsrltrafficps', 'HSR Layout Traffic Police', 'HSR Layout / Agara',
            ((12.9130, 77.6430, 2.5),)),
    _source('JnagarTr', 'Jayanagar Traffic Police', 'Jayanagar', ((12.9300, 77.5830, 2.5),)),
    _source('halasoortrfps', 'Halasuru Traffic Police', 'Halasuru / Ulsoor', ((12.9770, 77.6250, 2.2),)),
    _source('yprtrps', 'Yeshwanthpur Traffic Police', 'Yeshwanthpur', ((13.0230, 77.5500, 3.0),)),
    _source('madivalatrfps', 'Madiwala Traffic Police', 'Madiwala / Silk Board', ((12.9170, 77.6200, 2.5),)),
    _source('bellandurutrfps', 'Bellandur Traffic Police', 'Bellandur / ORR / Kadubeesanahalli',
            ((12.9300, 77.6750, 2.5), (12.9390, 77.6940, 1.8))),
    _source('ashoknagartfps', 'Ashok Nagar Traffic Police', 'Ashok Nagar / Richmond Road',
            ((12.9660, 77.6070, 1.8),), evidence=CAG_EVIDENCE),
    _source('adugoditraffic', 'Adugodi Traffic Police', 'Adugodi / Hosur Road',
            ((12.9440, 77.6080, 2.0),), evidence=CAG_EVIDENCE),
    _source('chickpetetrfps', 'Chickpet Traffic Police', 'Chickpet / City Market',
            ((12.9670, 77.5750, 1.8),), evidence=CAG_EVIDENCE),
    _source('kengeritrfps', 'Kengeri Traffic Police', 'Kengeri / Mysuru Road',
            ((12.9100, 77.4850, 3.0),), evidence='https://x.com/kengeritrfps/with_replies'),
)


def _point(value):
    try:
        if isinstance(value, dict):
            lat, lon = float(value['lat']), float(value.get('lon', value.get('lng')))
        else:
            lon, lat = float(value[0]), float(value[1])
        if math.isfinite(lat) and math.isfinite(lon) and -90 <= lat <= 90 and -180 <= lon <= 180:
            return lat, lon
    except (KeyError, IndexError, TypeError, ValueError):
        pass
    return None


def _route_points(route_waypoints, geometry):
    if isinstance(geometry, dict):
        geometry = geometry.get('geometry', geometry)
        geometry = geometry.get('coordinates') if isinstance(geometry, dict) else None
    values = geometry if isinstance(geometry, (list, tuple)) and geometry else route_waypoints or []
    return [point for value in values if (point := _point(value)) is not None]


def _segment_distance_km(center, start, end):
    """Local equirectangular projection is sufficient for Bengaluru area circles."""
    scale_x = 111.32 * math.cos(math.radians(center[0]))
    ax, ay = (start[1] - center[1]) * scale_x, (start[0] - center[0]) * 111.32
    bx, by = (end[1] - center[1]) * scale_x, (end[0] - center[0]) * 111.32
    dx, dy = bx - ax, by - ay
    length = dx * dx + dy * dy
    fraction = max(0, min(1, -(ax * dx + ay * dy) / length)) if length else 0
    return math.hypot(ax + fraction * dx, ay + fraction * dy)


def select_sources(route_waypoints, geometry=None):
    """Select local accounts before fetching, using every route line segment."""
    points = _route_points(route_waypoints, geometry)
    segments = list(zip(points, points[1:])) if len(points) > 1 else [(p, p) for p in points]
    # Approximate Bengaluru metro coverage; check segments even when endpoints lie outside.
    in_bengaluru = not points or any(_segment_distance_km((12.9716, 77.5946), a, b) <= 45 for a, b in segments)
    selected = []
    for source in SOURCE_REGISTRY:
        if (source['scope'] == 'citywide' and in_bengaluru) or any(
            _segment_distance_km((lat, lon), start, end) <= radius
            for lat, lon, radius in source['circles'] for start, end in segments
        ):
            selected.append({key: value for key, value in source.items() if key != 'circles'})
    return selected
