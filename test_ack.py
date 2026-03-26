#!/usr/bin/env python3
import sys
import time

from send_command import send_command

PORT = "/dev/ttyACM0"
TESTS = [
    ("PING", "PONG"),
    ("TEXT:Hello from host", "OK"),
    ("STATUS", "STATUS:"),
    ("TIME:2026-03-26 14:25", "OK"),
    ("STATUS", "line2=2026-03-26 14:25"),
    ("LINES:Now Playing|Artist Name|Track Title", "OK"),
    ("STATUS", "STATUS:"),
    ("BOGUS", "ERR:UNKNOWN_COMMAND"),
]


def main():
    failures = 0

    for command, expected in TESTS:
        startup, response = send_command(PORT, command)
        print(f"COMMAND: {command}")
        if startup:
            print("  startup:")
            for line in startup:
                print(f"    {line}")
        print("  response:")
        if response:
            for line in response:
                print(f"    {line}")
        else:
            print("    <no response>")

        matched = any(expected in line for line in response)
        if not matched:
            failures += 1
            print(f"  RESULT: FAIL (expected contains {expected!r})")
        else:
            print("  RESULT: PASS")
        print()
        time.sleep(0.5)

    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
