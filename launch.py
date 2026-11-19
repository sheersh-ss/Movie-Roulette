"""Shared first-run setup for each operating-system launcher."""
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import venv

ROOT = Path(__file__).resolve().parent


def main():
    os.chdir(ROOT)
    environment = ROOT / '.venv'
    python = environment / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    if not python.exists():
        print('Creating Movie Roulette environment…', flush=True)
        venv.EnvBuilder(with_pip=True).create(environment)
    requirements = ROOT / 'requirements.txt'
    fingerprint = hashlib.sha256(requirements.read_bytes()).hexdigest()
    marker = environment / 'movie-roulette-dependencies'
    if not marker.exists() or marker.read_text() != fingerprint:
        subprocess.run([str(python), '-m', 'pip', 'install', '-r', str(requirements)], check=True)
        marker.write_text(fingerprint)
        # Search remains usable in the normal browser if Chromium setup fails.
        result = subprocess.run([str(python), '-m', 'playwright', 'install', 'chromium'])
        if result.returncode:
            print('Background browser setup failed. Cinejoy will use normal browser search.', flush=True)
    return subprocess.call([str(python), str(ROOT / 'app.py')])


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (OSError, subprocess.CalledProcessError) as error:
        print(f'Could not launch Movie Roulette: {error}', file=sys.stderr)
        input('Press Enter to close…')
        sys.exit(1)
