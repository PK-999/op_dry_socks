"""Explicit live-provider checks: python e2e_test.py --live.

Uses provider quota but never edits saved configuration or sends notifications.
"""
import argparse
import copy

ROUTES = [
    ('Koramangala to Indiranagar', (12.9350, 77.6245), (12.9784, 77.6408)),
    ('Whitefield to Silk Board', (12.9698, 77.7499), (12.9177, 77.6238)),
    ('Bellandur to Marathahalli', (12.9304, 77.6784), (12.9569, 77.7011)),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live', action='store_true', help='Allow real provider requests')
    args = parser.parse_args()
    if not args.live:
        parser.error('--live is required; this script makes external provider requests')
    from main import assess_commute
    from services.configuration import load_config
    original = load_config()
    failed = []
    for name, origin, destination in ROUTES:
        config = copy.deepcopy(original)
        config['locations'] = {'origin': {'name': name + ' start', 'lat': origin[0], 'lon': origin[1]},
                               'destination': {'name': name + ' end', 'lat': destination[0], 'lon': destination[1]}}
        config.get('route', {}).pop('selected_route', None)
        result = assess_commute(config, social=False)
        print(f"{name}: {result['state']}")
        if result['state'] == 'UNKNOWN':
            failed.append(name)
    if failed:
        parser.exit(1, 'Live check incomplete: ' + ', '.join(failed) + '\n')


if __name__ == '__main__':
    main()
