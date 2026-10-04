"""Local configuration. Private credentials never belong in browser responses."""
import json
import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / 'config.json'
SECRET_ENV = {
    'google_maps_token': 'GOOGLE_MAPS_API_KEY',
    'google_maps_browser_key': 'GOOGLE_MAPS_BROWSER_KEY',
    'mapbox_token': 'MAPBOX_ACCESS_TOKEN',
    'tomorrow_io_token': 'TOMORROW_IO_API_KEY',
    'twitter_auth_token': 'TWITTER_AUTH_TOKEN',
    'twitter_bearer_token': 'X_BEARER_TOKEN',
}


def configured(value):
    return bool(value and not str(value).startswith('YOUR_'))


def load_config(path=None, include_env=True):
    path = Path(path or os.environ.get('DRYSOCKS_CONFIG', DEFAULT_CONFIG))
    with open(path if path.exists() else ROOT / 'config.json.example') as stream:
        config = json.load(stream)
    if include_env:
        for key, env in SECRET_ENV.items():
            if os.environ.get(env):
                config[key] = os.environ[env]
    return config


def save_config(config, path=None):
    path = Path(path or os.environ.get('DRYSOCKS_CONFIG', DEFAULT_CONFIG))
    fd, temporary = tempfile.mkstemp(prefix='.dry-socks-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(config, stream, indent=2)
            stream.write('\n')
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def public_config(config):
    return {
        # This dedicated, referrer-restricted key is intentionally public.
        'google_maps_browser_key': config.get('google_maps_browser_key') if configured(config.get('google_maps_browser_key')) else None,
        'locations': config.get('locations', {}),
        'route': config.get('route', {}),
        'thresholds': config.get('thresholds', {}),
        'polling': config.get('polling', {}),
        'providers': {
            'google_maps': configured(config.get('google_maps_token')),
            'mapbox': configured(config.get('mapbox_token')),
            'tomorrow': configured(config.get('tomorrow_io_token')),
            'x': configured(config.get('twitter_auth_token')) or configured(config.get('twitter_bearer_token')),
        },
    }
