#!/usr/bin/env python3
import argparse
import datetime as dt
import sys

from send_command import send_command


def main():
    parser = argparse.ArgumentParser(description="Send time updates to a Pico Ink display over USB serial")
    parser.add_argument("--port", default="/dev/ttyACM0")
    parser.add_argument("--value", help="Time text to send. Defaults to current local time.")
    args = parser.parse_args()

    value = args.value or dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    _startup, responses = send_command(args.port, f"TIME:{value}")
    if responses:
        for line in responses:
            print(line)
    else:
        print("<no response>")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
