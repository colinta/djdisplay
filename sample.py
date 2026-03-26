import time

try:
    from picographics import PicoGraphics, DISPLAY_INKY_PACK
except ImportError as e:
    raise SystemExit(
        "This demo needs Pimoroni MicroPython with picographics and DISPLAY_INKY_PACK"
    ) from e


display = PicoGraphics(display=DISPLAY_INKY_PACK)
WIDTH, HEIGHT = display.get_bounds()

# Common pen mapping for Pimoroni Inky displays:
# 0 = white, 1 = black, 2 = color (if available)
WHITE = 0
BLACK = 1
ACCENT = 2


def draw_message(counter):
    display.set_pen(WHITE)
    display.clear()

    display.set_pen(BLACK)
    display.set_font("bitmap8")
    display.text("Pico Ink 2.9", 10, 10, WIDTH - 20, 2)
    display.text("Hello from MicroPython!", 10, 42, WIDTH - 20, 2)
    display.text("Pimoroni Inky sample", 10, 68, WIDTH - 20, 2)
    display.text("Refresh #: {}".format(counter), 10, HEIGHT - 34, WIDTH - 20, 2)

    # If the panel supports a third color, use it for a small accent bar.
    try:
        display.set_pen(ACCENT)
        display.rectangle(10, HEIGHT - 14, WIDTH - 20, 6)
    except Exception:
        pass

    display.update()


count = 1
while True:
    draw_message(count)
    count += 1
    time.sleep(15)
