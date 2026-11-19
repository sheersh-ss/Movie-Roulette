"""Operating-system defaults shared by all desktop versions."""
import os
import sys
from pathlib import Path


def cache_path(platform=None, home=None, environ=None):
    platform = sys.platform if platform is None else platform
    home = Path.home() if home is None else Path(home)
    env = os.environ if environ is None else environ
    if platform == 'darwin':
        base = home / 'Library/Application Support'
    elif platform == 'win32':
        base = Path(env.get('LOCALAPPDATA') or home / 'AppData/Local')
    else:
        configured = Path(env.get('XDG_CACHE_HOME', ''))
        base = configured if configured.is_absolute() else home / '.cache'
    return base / 'Movie Roulette' / 'top500.json'


def font_family(platform=None):
    platform = sys.platform if platform is None else platform
    return 'Helvetica Neue' if platform == 'darwin' else 'Segoe UI' if platform == 'win32' else 'DejaVu Sans'
