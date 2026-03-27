#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

import serial
from serial import SerialException

CONFIG_PATH = Path('/opt/inky/config.json')


def load_config() -> dict:
    with CONFIG_PATH.open() as f:
        return json.load(f)


def load_json(path: Path, default=None):
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text())
    except Exception:
        return default


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(data, indent=2) + '\n')
    tmp.replace(path)


def ascii_only(value: str) -> str:
    return ''.join(ch for ch in value if ord(ch) < 128).strip()


def truncate(value: str, max_len: int) -> str:
    value = ascii_only(value)
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + '...'


def normalize_track(track: dict, max_len: int) -> dict:
    return {
        'status': truncate(track.get('status', '') or '', 12),
        'artist': truncate(track.get('artist', '') or '', max_len),
        'album': truncate(track.get('album', '') or '', max_len),
        'title': truncate(track.get('title', '') or 'Not Playing', max_len),
    }


def tracks_equal(a: dict, b: dict) -> bool:
    return (
        a.get('status', '') == b.get('status', '')
        and a.get('artist', '') == b.get('artist', '')
        and a.get('album', '') == b.get('album', '')
        and a.get('title', '') == b.get('title', '')
    )


def run_mpc(args):
    return subprocess.run(['mpc', *args], capture_output=True, text=True, check=False)


def handle_button(button: str):
    mapping = {
        'A': ['prev'],
        'B': ['toggle'],
        'C': ['next'],
    }
    cmd = mapping.get(button)
    if not cmd:
        return
    result = run_mpc(cmd)
    if result.returncode == 0:
        print(f'button {button} -> mpc {cmd[0]}')
        sys.stdout.flush()
    else:
        print(f'ERROR: button {button} failed: {result.stderr.strip()}', file=sys.stderr)
        sys.stderr.flush()


def open_serial(port: str):
    ser = serial.Serial(port, 115200, timeout=0.1, dsrdtr=False, rtscts=False)
    try:
        ser.dtr = False
        ser.rts = False
    except Exception:
        pass
    time.sleep(0.5)
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    return ser


def send_track(ser, track: dict) -> bool:
    command = f"TRACK:{track['status']}|{track['artist']}|{track['album']}|{track['title']}\r\n"
    ser.write(command.encode('utf-8'))
    ser.flush()

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            line = ser.readline()
        except SerialException:
            return False
        if not line:
            continue
        text = line.decode('utf-8', errors='replace').strip()
        if not text or text == 'READY':
            continue
        if text.startswith('BUTTON:'):
            handle_button(text.split(':', 1)[1].strip())
            continue
        if text == 'OK':
            return True
        if text.startswith('ERR:'):
            print(f'ERROR: pico responded {text}', file=sys.stderr)
            sys.stderr.flush()
            return False
    return False


def main() -> int:
    config = load_config()
    state_dir = Path(config['state_dir'])
    state_dir.mkdir(parents=True, exist_ok=True)

    current_track_path = state_dir / 'current-track.json'
    pending_track_path = state_dir / 'pending-track.json'
    displayed_track_path = state_dir / 'displayed-track.json'
    last_update_path = state_dir / 'last-update.json'

    serial_port = config.get('serial_port', '/dev/ttyACM0')
    min_interval = float(config.get('min_update_interval_seconds', 120))
    poll_interval = float(config.get('poll_interval_seconds', 0.5))
    max_len = int(config.get('max_field_length', 40))

    ser = None

    while True:
        if ser is None:
            try:
                ser = open_serial(serial_port)
                print(f'connected {serial_port}')
                sys.stdout.flush()
            except Exception as e:
                print(f'ERROR: serial connect failed: {e}', file=sys.stderr)
                sys.stderr.flush()
                time.sleep(1)
                continue

        try:
            while True:
                try:
                    line = ser.readline()
                except SerialException as e:
                    raise e
                if not line:
                    break
                text = line.decode('utf-8', errors='replace').strip()
                if not text or text == 'READY':
                    continue
                if text.startswith('BUTTON:'):
                    handle_button(text.split(':', 1)[1].strip())
                else:
                    print(f'pico: {text}')
                    sys.stdout.flush()

            current_raw = load_json(current_track_path, {})
            displayed = load_json(displayed_track_path, {})
            pending = load_json(pending_track_path, {})
            last_update = load_json(last_update_path, {'updated_at': 0})

            current = normalize_track(current_raw, max_len) if current_raw else {}
            now = time.time()
            updated_at = float(last_update.get('updated_at', 0))
            due = (now - updated_at) >= min_interval

            candidate = None

            if pending and due and not tracks_equal(pending, displayed):
                candidate = pending
            elif current and not tracks_equal(current, displayed):
                if due:
                    candidate = current
                else:
                    if not tracks_equal(current, pending):
                        write_json(pending_track_path, current)
                        print(f"queued {current['status']} {current['artist']} / {current['album']} / {current['title']}")
                        sys.stdout.flush()

            if candidate:
                if send_track(ser, candidate):
                    write_json(displayed_track_path, candidate)
                    write_json(last_update_path, {'updated_at': time.time()})
                    if pending_track_path.exists() and tracks_equal(candidate, pending):
                        pending_track_path.unlink()
                    print(f"updated {candidate['status']} {candidate['artist']} / {candidate['album']} / {candidate['title']}")
                    sys.stdout.flush()
                else:
                    raise SerialException('failed to send track or receive ack')

            time.sleep(poll_interval)

        except (OSError, SerialException) as e:
            print(f'ERROR: serial disconnected: {e}', file=sys.stderr)
            sys.stderr.flush()
            try:
                ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(1)


if __name__ == '__main__':
    raise SystemExit(main())
