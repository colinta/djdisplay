# Inky MPD Display

This project drives a **Pimoroni Pico Inky Pack** from this host computer over the Pico's **USB serial port**.

The host watches MPD for player events, reads the current track metadata with `mpc`, and sends artist/album/title text to the Pico. The Pico listens for simple serial commands and redraws the Inky display.

## Architecture

The system is split into two host-side processes plus one Pico-side script.

### Pico-side

File:
- `/opt/inky/pico_serial_display.py`

Deployed to the Pico as:
- `main.py`

Responsibilities:
- listens on USB serial
- accepts simple text commands in `COMMAND:DATA` format
- redraws the Inky display
- returns acknowledgments like `OK`, `PONG`, or `ERR:...`

Supported commands:
- `PING`
- `TEXT:<text>`
- `TIME:<text>`
- `LINES:<title>|<line1>|<line2>`
- `STATUS`
- `CLEAR`
- `SHOW`

For the MPD display flow, the host mainly uses:
- `LINES:<artist>|<album>|<title>`

## Host-side processes

### 1. MPD watcher

File:
- `/opt/inky/mpd_watcher.py`

Responsibilities:
- waits for MPD player events using:
  - `mpc idleloop player`
- fetches current metadata using:
  - `mpc --format '%artist%\n%album%\n%title%' current`
- filters metadata to ASCII only
- writes the latest seen track to:
  - `/opt/inky/state/current-track.json`

This process does **not** do throttling. It always writes the newest track state.

### 2. Inky updater

File:
- `/opt/inky/inky_updater.py`

Responsibilities:
- reads the latest desired track from:
  - `/opt/inky/state/current-track.json`
- compares it against the last displayed track
- enforces a minimum delay between eInk updates
- sends updates to the Pico over USB serial
- coalesces rapid changes so only the newest pending update is eventually shown

This process owns the display timing logic.

## Throttling behavior

The updater implements this logic:

1. read the current desired track
2. compare it to the last displayed track
3. if unchanged:
   - sleep briefly and check again
4. if changed and enough time has passed since the last display update:
   - update the Inky immediately
5. if changed but not enough time has passed:
   - store it as pending
6. if more events arrive before the delay expires:
   - replace the pending track with the newest one
7. when the delay expires:
   - display the pending track

This avoids excessive eInk refreshes while still ensuring the display catches up to the latest track.

## Configuration

File:
- `/opt/inky/config.json`

Current fields:
```json
{
  "serial_port": "/dev/ttyACM0",
  "min_update_interval_seconds": 120,
  "poll_interval_seconds": 0.5,
  "max_field_length": 40,
  "state_dir": "/opt/inky/state"
}
```

Meaning:
- `serial_port`: Pico serial device
- `min_update_interval_seconds`: minimum time between actual Inky refreshes
- `poll_interval_seconds`: how often the updater checks state files
- `max_field_length`: maximum displayed length for artist/album/title
- `state_dir`: location of runtime JSON state files

## State files

Directory:
- `/opt/inky/state`

Files:
- `current-track.json`
  - latest track seen from MPD
- `pending-track.json`
  - latest queued update waiting for throttle window to expire
- `displayed-track.json`
  - most recently confirmed track sent to the Pico
- `last-update.json`
  - timestamp of the last successful display update

These files make the system easy to inspect and recover after restarts.

## ASCII filtering

Track metadata is filtered to ASCII characters before being written and displayed. This avoids issues with unsupported characters on the display path.

## Manual usage

### Run the watcher
```bash
python3 /opt/inky/mpd_watcher.py
```

### Run the updater
```bash
python3 /opt/inky/inky_updater.py
```

Run them in separate terminals.

## systemd services

Installed system services:
- `inky-mpd-watcher.service`
- `inky-updater.service`

These are enabled at boot and start automatically.

### Service management

Check status:
```bash
systemctl status inky-mpd-watcher.service
systemctl status inky-updater.service
```

Follow logs:
```bash
journalctl -u inky-mpd-watcher.service -f
journalctl -u inky-updater.service -f
```

Force an immediate display refresh:
```bash
rm -f /opt/inky/state/displayed-track.json /opt/inky/state/last-update.json
```

This clears the remembered display state and throttle timestamp, so the updater will redraw the current track on its next loop.

Restart services after code changes:
```bash
sudo systemctl restart inky-mpd-watcher.service inky-updater.service
```

Stop services:
```bash
sudo systemctl stop inky-mpd-watcher.service inky-updater.service
```

Disable services:
```bash
sudo systemctl disable inky-mpd-watcher.service inky-updater.service
```

Unit files:
- `/etc/systemd/system/inky-mpd-watcher.service`
- `/etc/systemd/system/inky-updater.service`

## Other useful scripts

### Send one command directly to the Pico
File:
- `/opt/inky/send_command.py`

Examples:
```bash
python3 /opt/inky/send_command.py "PING"
python3 /opt/inky/send_command.py "TEXT:Hello from host"
python3 /opt/inky/send_command.py "LINES:Now Playing|Artist Name|Track Title"
```

### Send a time update
File:
- `/opt/inky/send_time.py`

Example:
```bash
python3 /opt/inky/send_time.py
```

### Acknowledgment test suite
File:
- `/opt/inky/test_ack.py`

Example:
```bash
python3 /opt/inky/test_ack.py
```

## Display notes

The Pico Inky Pack uses these safe display settings in the current Pico script:
- white pen = `15`
- black pen = `0`
- `display.set_update_speed(2)`

Using incorrect pen values can produce a mostly black or unreadable display.

## Typical end-to-end flow

1. MPD changes track
2. `mpd_watcher.py` receives a `player` event
3. watcher reads artist/album/title and writes `current-track.json`
4. `inky_updater.py` notices the desired track changed
5. if allowed by the throttle window, it sends:
   - `LINES:<artist>|<album>|<title>`
6. Pico receives the command and redraws the Inky display
7. Pico replies `OK`
8. updater records the new displayed state and timestamp

If updates happen too quickly, the newest desired track is stored in `pending-track.json` until the minimum interval expires.
