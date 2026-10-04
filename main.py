"""One-shot or continuous local commute monitor, sharing the dashboard pipeline."""
import argparse
import datetime
import hashlib
import json
import os
import time
from zoneinfo import ZoneInfo

from services.configuration import load_config as read_config
from services.routing import get_routes, select_saved_route, RoutingUnavailable
from services.state_manager import should_notify, update_state
from services.notifier import notify

DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.environ.get('DRYSOCKS_CONFIG', os.path.join(DIR, 'config.json'))
INDIA = ZoneInfo('Asia/Kolkata')


def load_config():
    return read_config(CONFIG_FILE)


def is_active_window(config, now=None):
    now = now or datetime.datetime.now(INDIA)
    if now.tzinfo is None:
        now = now.replace(tzinfo=INDIA)
    clock = now.astimezone(INDIA).time().replace(tzinfo=None)
    polling = config.get('polling', {})
    start = datetime.time.fromisoformat(polling.get('active_hours_start', '16:00'))
    end = datetime.time.fromisoformat(polling.get('active_hours_end', '20:30'))
    return start <= clock <= end if start <= end else clock >= start or clock <= end


def assess_commute(config, reverse=False, social=True):
    from services.weather import get_route_weather
    from services.evaluator import departure_advice
    from services.twitter import get_route_alerts
    origin, destination = config['locations']['origin'], config['locations']['destination']
    if reverse:
        origin, destination = destination, origin
    settings, thresholds = config.get('route', {}), config.get('thresholds', {})
    mode = settings.get('travel_mode', 'TWO_WHEELER')
    route_key = hashlib.sha256(json.dumps([origin, destination, mode, settings.get('selected_route')], sort_keys=True).encode()).hexdigest()[:20]
    try:
        routes = get_routes(config, origin, destination, mode)
        # Reverse commutes need their own newly calculated choice.
        route = select_saved_route(routes, None if reverse else settings.get('selected_route'))
    except RoutingUnavailable as error:
        return {'state': 'UNKNOWN', 'title': 'Route unavailable', 'subtitle': 'Commute timing could not be checked.',
                'body': str(error), 'leave_in_mins': None, 'route_key': route_key, 'rain_mins': None,
                'weather': [], 'commute_mins': None, 'origin': origin, 'destination': destination,
                'social_status': 'not_checked'}
    points = route['waypoints']
    points[0]['name'], points[-1]['name'] = origin['name'], destination['name']
    weather = get_route_weather(points, config.get('tomorrow_io_token'), thresholds.get('rain_mm_15min', .4),
                                thresholds.get('waterlogging_past_2h_mm', 5))
    reports = get_route_alerts(points, config.get('twitter_auth_token'), config.get('twitter_bearer_token'),
                               geometry=route['geometry'], max_age_hours=config.get('social', {}).get('max_age_hours', 2),
                               enabled=social and config.get('social', {}).get('enabled', True))
    # Source coverage alone does not prove a post describes an active incident.
    # Keep original reports as attributed context, as the dashboard does.
    advice = departure_advice(route['duration_mins'], thresholds.get('safety_buffer_mins', 15), weather,
                              origin['name'], destination['name'])
    known = [p['mins_to_rain'] for p in weather if p.get('mins_to_rain') is not None]
    advice.update(route_key=route_key, rain_mins=min(known) if known else None, weather=weather,
                  commute_mins=route['duration_mins'], origin=origin, destination=destination,
                  social_status=reports['status'], reports=reports['alerts'])
    return advice


def run_once(config, dry_run=False, reverse=False, social=True):
    result = assess_commute(config, reverse, social)
    print(f"{result['state']}: {result['title']} — {result['subtitle']}")
    print(result['body'])
    print(f"X sources: {result['social_status']}")
    for report in result.get('reports', [])[:3]:
        print(f"  @{report['handle']} ({report['area']}): {report['text'][:200]} {report['url']}")
    if dry_run:
        for point in result['weather']:
            rain = point.get('mins_to_rain')
            print(f"  {point['name']}: {'unavailable' if rain is None else 'no rain in forecast horizon' if rain == 999 else str(rain) + ' min to forecast rain'}")
        return result
    from services.telemetry import log_telemetry
    log_telemetry(result['origin']['name'], result['destination']['name'], result['commute_mins'], result['state'], result['rain_mins'], result['weather'])
    rain = result['rain_mins'] if result['rain_mins'] is not None else 999
    send, state = should_notify(result['state'], rain, route_key=result['route_key'])
    if result['state'] == 'CLEAR':
        # Observe recovery without recording a notification or resetting its cooldown.
        state['last_state'] = 'CLEAR'
        from services.state_manager import save_state
        save_state(state)
    elif send and notify(result['state'], result['title'], result['subtitle'], result['body']):
        update_state(state, result['state'], rain)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dry-run', action='store_true', help='Fetch and print, without notifications or local state writes')
    parser.add_argument('--reverse', action='store_true', help='Swap saved endpoints')
    parser.add_argument('--watch', action='store_true', help='Poll during the configured India-time window')
    parser.add_argument('--no-social', action='store_true', help='Skip X checks for this run')
    parser.add_argument('--config', help='Read a separate config file')
    args = parser.parse_args()
    global CONFIG_FILE
    if args.config:
        CONFIG_FILE = os.path.abspath(args.config)
    try:
        while True:
            config = load_config()
            if args.dry_run or is_active_window(config):
                run_once(config, args.dry_run, args.reverse, not args.no_social)
            if not args.watch or args.dry_run:
                break
            time.sleep(max(1, float(config.get('polling', {}).get('interval_minutes', 5))) * 60)
    except KeyboardInterrupt:
        pass
    except (KeyError, ValueError, OSError) as error:
        parser.exit(1, f'Unable to run Dry Socks: {type(error).__name__}. Check config.json and README.md.\n')


if __name__ == '__main__':
    main()
