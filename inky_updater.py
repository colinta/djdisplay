#!/usr/bin/env python3
import json
import sys
import time
from pathlib import Path

from send_command import send_command

CONFIG_PATH = Path("/opt/inky/config.json")


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
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def ascii_only(value: str) -> str:
    return "".join(ch for ch in value if ord(ch) < 128).strip()


def truncate(value: str, max_len: int) -> str:
    value = ascii_only(value)
    if len(value) <= max_len:
        return value
    return value[: max_len - 3].rstrip() + "..."


def normalize_track(track: dict, max_len: int) -> dict:
    return {
        "status": truncate(track.get("status", "") or "", 12),
        "artist": truncate(track.get("artist", "") or "", max_len),
        "album": truncate(track.get("album", "") or "", max_len),
        "title": truncate(track.get("title", "") or "Not Playing", max_len),
    }


def tracks_equal(a: dict, b: dict) -> bool:
    return (
        a.get("status", "") == b.get("status", "")
        and a.get("artist", "") == b.get("artist", "")
        and a.get("album", "") == b.get("album", "")
        and a.get("title", "") == b.get("title", "")
    )


def send_track(port: str, track: dict) -> list[str]:
    command = f"TRACK:{track['status']}|{track['artist']}|{track['album']}|{track['title']}"
    _startup, response = send_command(port, command)
    return response


def main() -> int:
    config = load_config()
    state_dir = Path(config["state_dir"])
    state_dir.mkdir(parents=True, exist_ok=True)

    current_track_path = state_dir / "current-track.json"
    pending_track_path = state_dir / "pending-track.json"
    displayed_track_path = state_dir / "displayed-track.json"
    last_update_path = state_dir / "last-update.json"

    serial_port = config.get("serial_port", "/dev/ttyACM0")
    min_interval = float(config.get("min_update_interval_seconds", 120))
    poll_interval = float(config.get("poll_interval_seconds", 0.5))
    max_len = int(config.get("max_field_length", 40))

    while True:
        current_raw = load_json(current_track_path, {})
        displayed = load_json(displayed_track_path, {})
        pending = load_json(pending_track_path, {})
        last_update = load_json(last_update_path, {"updated_at": 0})

        current = normalize_track(current_raw, max_len) if current_raw else {}
        now = time.time()
        updated_at = float(last_update.get("updated_at", 0))
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
                time.sleep(poll_interval)
                continue

        if candidate:
            response = send_track(serial_port, candidate)
            if any(line == "OK" for line in response):
                write_json(displayed_track_path, candidate)
                write_json(last_update_path, {"updated_at": time.time()})
                if pending_track_path.exists() and tracks_equal(candidate, pending):
                    pending_track_path.unlink()
                print(f"updated {candidate['status']} {candidate['artist']} / {candidate['album']} / {candidate['title']}")
                sys.stdout.flush()
            else:
                print(f"ERROR: unexpected response: {response}", file=sys.stderr)
                sys.stderr.flush()

        time.sleep(poll_interval)


if __name__ == "__main__":
    raise SystemExit(main())
