#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path

from send_command import send_command

CACHE_PATH = Path('/opt/inky/now_playing_cache.json')
DEFAULT_PORT = '/dev/ttyACM0'


def ascii_only(value: str) -> str:
    return ''.join(ch for ch in value if ord(ch) < 128).strip()


def truncate(value: str, max_len: int = 40) -> str:
    value = value.strip()
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + '...'


def get_current_track() -> dict:
    result = subprocess.run(
        ['mpc', '--format', '%artist%\n%album%\n%title%', 'current'],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or 'mpc current failed')

    lines = result.stdout.splitlines()
    while len(lines) < 3:
        lines.append('')

    artist, album, title = lines[:3]

    data = {
        'artist': truncate(ascii_only(artist) or 'Unknown Artist'),
        'album': truncate(ascii_only(album) or 'Unknown Album'),
        'title': truncate(ascii_only(title) or 'Unknown Track'),
    }
    return data


def load_cache(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_cache(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + '\n')


def update_display(port: str, track: dict) -> list[str]:
    command = f"LINES:{track['artist']}|{track['album']}|{track['title']}"
    _startup, response = send_command(port, command)
    return response


def main() -> int:
    parser = argparse.ArgumentParser(description='Update Pico Inky with current MPC track info')
    parser.add_argument('--port', default=DEFAULT_PORT)
    parser.add_argument('--cache', default=str(CACHE_PATH))
    parser.add_argument('--force', action='store_true', help='Update even if cached values match')
    args = parser.parse_args()

    cache_path = Path(args.cache)

    try:
        current = get_current_track()
    except Exception as e:
        print(f'ERROR: failed to get track info: {e}', file=sys.stderr)
        return 1

    previous = load_cache(cache_path)

    if not args.force and current == previous:
        print('UNCHANGED')
        return 0

    response = update_display(args.port, current)
    if not response:
        print('ERROR: no response from Pico', file=sys.stderr)
        return 1

    if any(line == 'OK' for line in response):
        save_cache(cache_path, current)
        print('UPDATED')
        print(json.dumps(current, indent=2))
        return 0

    print('ERROR: unexpected response from Pico')
    for line in response:
        print(line)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
