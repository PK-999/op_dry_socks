from services import sources


def handles(points, geometry=None):
    return {source['handle'] for source in sources.select_sources(points, geometry)}


def test_empty_route_only_selects_citywide_sources():
    assert handles([]) == {'Bengalururain', 'blrcitytraffic'}


def test_route_segment_crossing_bellandur_selects_account_without_nearby_endpoints():
    selected = handles([{'lat': 12.93, 'lon': 77.60}, {'lat': 12.93, 'lon': 77.71}])
    assert 'bellandurutrfps' in selected
    assert 'yprtrps' not in selected
    assert 'wftrps' not in selected


def test_full_geometry_selects_area_passed_between_distant_route_endpoints():
    points = [{'lat': 12.88, 'lon': 77.50}, {'lat': 12.88, 'lon': 77.80}]
    geometry = {'type': 'LineString', 'coordinates': [[77.50, 12.88], [77.675, 12.93], [77.80, 12.88]]}
    assert 'bellandurutrfps' in handles(points, geometry)
    assert 'bellandurutrfps' not in handles(points)


def test_bad_coordinates_do_not_select_local_sources():
    assert handles([{'lat': float('nan'), 'lon': 77.6}, {'lat': 200, 'lon': 77.6}]) == {'Bengalururain', 'blrcitytraffic'}
