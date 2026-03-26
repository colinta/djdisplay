import time
import sys
import uselect
import machine

from picographics import PicoGraphics, DISPLAY_INKY_PACK


display = PicoGraphics(display=DISPLAY_INKY_PACK)
WIDTH, HEIGHT = display.get_bounds()
display.set_update_speed(2)

# On Pico Inky Pack, 15 is white and 0 is black.
WHITE = 15
BLACK = 0
# Some variants expose extra shades/colours, but black/white is the safe baseline.
ACCENT = 0

state = {
    "status": "",
    "title": "Pico Ink 2.9",
    "line1": "Waiting for host...",
    "line2": "Send: TEXT:Hello",
    "footer": "",
}
command_count = 0

button_a = machine.Pin(12, machine.Pin.IN, pull=machine.Pin.PULL_UP)
button_b = machine.Pin(13, machine.Pin.IN, pull=machine.Pin.PULL_UP)
button_c = machine.Pin(14, machine.Pin.IN, pull=machine.Pin.PULL_UP)
last_button_times = {"A": 0, "B": 0, "C": 0}
BUTTON_DEBOUNCE_MS = 300

# USB CDC serial input from the host.
poll = uselect.poll()
poll.register(sys.stdin, uselect.POLLIN)


def render():
    display.set_pen(WHITE)
    display.clear()
    display.set_pen(BLACK)

    display.set_font("bitmap8")

    display.text(state["title"], 8, 12, WIDTH - 16, 3)
    display.text(state["line1"], 8, 52, WIDTH - 16, 2)
    display.text(state["line2"], 8, 84, WIDTH - 16, 2)

    if state["status"]:
        status_label = state["status"]
        status_x = max(10, WIDTH - (len(status_label) * 8 * 2) - 8)
        display.text(status_label, status_x, HEIGHT - 22, WIDTH - status_x, 2)

    display.update()


def set_text(value):
    state["status"] = ""
    state["line1"] = value
    state["line2"] = ""
    state["footer"] = ""
    render()


def set_time(value):
    state["status"] = ""
    state["line1"] = "Time"
    state["line2"] = value
    state["footer"] = ""
    render()


def set_lines(payload):
    parts = payload.split("|", 2)
    while len(parts) < 3:
        parts.append("")
    state["status"] = ""
    state["title"], state["line1"], state["line2"] = parts
    state["footer"] = ""
    render()


def set_track(payload):
    parts = payload.split("|", 3)
    while len(parts) < 4:
        parts.append("")
    state["status"], state["title"], state["line1"], state["line2"] = parts
    state["footer"] = ""
    render()


def handle_command(line):
    global command_count

    line = line.strip()
    if not line:
        return

    if ":" in line:
        cmd, payload = line.split(":", 1)
    else:
        cmd, payload = line, ""

    cmd = cmd.strip().upper()
    payload = payload.strip()

    if cmd == "PING":
        print("PONG")
    elif cmd == "TEXT":
        set_text(payload)
        command_count += 1
        print("OK")
    elif cmd == "TIME":
        set_time(payload)
        command_count += 1
        print("OK")
    elif cmd == "LINES":
        set_lines(payload)
        command_count += 1
        print("OK")
    elif cmd == "TRACK":
        set_track(payload)
        command_count += 1
        print("OK")
    elif cmd == "CLEAR":
        state["status"] = ""
        state["line1"] = ""
        state["line2"] = ""
        state["footer"] = ""
        render()
        command_count += 1
        print("OK")
    elif cmd == "SHOW":
        render()
        command_count += 1
        print("OK")
    elif cmd == "STATUS":
        print(
            "STATUS:status={}|title={}|line1={}|line2={}|footer={}|count={}".format(
                state["status"],
                state["title"],
                state["line1"],
                state["line2"],
                state["footer"],
                command_count,
            )
        )
    else:
        print("ERR:UNKNOWN_COMMAND")


def check_buttons():
    now = time.ticks_ms()

    if not button_a.value() and time.ticks_diff(now, last_button_times["A"]) > BUTTON_DEBOUNCE_MS:
        last_button_times["A"] = now
        print("BUTTON:A")

    if not button_b.value() and time.ticks_diff(now, last_button_times["B"]) > BUTTON_DEBOUNCE_MS:
        last_button_times["B"] = now
        print("BUTTON:B")

    if not button_c.value() and time.ticks_diff(now, last_button_times["C"]) > BUTTON_DEBOUNCE_MS:
        last_button_times["C"] = now
        print("BUTTON:C")


render()
print("READY")

buffer = ""
while True:
    if poll.poll(20):
        ch = sys.stdin.read(1)
        if ch == "\n":
            handle_command(buffer)
            buffer = ""
        elif ch != "\r":
            buffer += ch
    check_buttons()
    time.sleep_ms(20)
