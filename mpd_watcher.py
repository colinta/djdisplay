#!/usr/bin/env python3
import json
import subprocess
import sys
import time
from pathlib import Path

CONFIG_PATH = Path("/opt/inky/config.json")


def load_config() -> dict:
    with CONFIG_PATH.open() as f:
        return json.load(f)


def ascii_only(value: str) -> str:
    return "".join(ch for ch in value if ord(ch) < 128).strip()


def get_playback_status() -> str:
    result = subprocess.run(
        ["mpc", "status"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return "STOP"

    for line in result.stdout.splitlines():
        if "[playing]" in line:
            return "PLAYING"
        if "[paused]" in line:
            return "PAUSED"
    return "STOPPED"


def get_track() -> dict:
    result = subprocess.run(
        ["mpc", "--format", "%artist%\n%album%\n%title%", "current"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "mpc current failed")

    lines = result.stdout.splitlines()
    while len(lines) < 3:
        lines.append("")

    artist, album, title = lines[:3]
    track = {
        "status": get_playback_status(),
        "artist": ascii_only(artist),
        "album": ascii_only(album),
        "title": ascii_only(title),
        "seen_at": time.time(),
    }

    if not any((track["artist"], track["album"], track["title"])):
        track = {
            "status": "STOPPED",
            "artist": "",
            "album": "",
            "title": "Not Playing",
            "seen_at": time.time(),
        }

    return track


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def main() -> int:
    config = load_config()
    state_dir = Path(config["state_dir"])
    current_track_path = state_dir / "current-track.json"

    while True:
        proc = subprocess.Popen(
            ["mpc", "idleloop", "player"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )

        try:
            for line in proc.stdout:
                event = line.strip()
                if not event:
                    continue
                try:
                    track = get_track()
                    write_json(current_track_path, track)
                    print(f"event={event} status={track['status']} track={track['artist']} / {track['album']} / {track['title']}")
                    sys.stdout.flush()
                except Exception as e:
                    print(f"ERROR: {e}", file=sys.stderr)
                    sys.stderr.flush()
        finally:
            try:
                proc.kill()
            except Exception:
                pass

        time.sleep(1)


if __name__ == "__main__":
    raise SystemExit(main())
