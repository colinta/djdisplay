#!/usr/bin/env python3
import argparse
import sys
import time

import serial
from serial import SerialException


def collect_lines(ser, duration):
    deadline = time.time() + duration
    lines = []
    while time.time() < deadline:
        try:
            line = ser.readline()
        except SerialException as e:
            lines.append(f"SERIAL_EXCEPTION:{e}")
            break
        if not line:
            continue
        text = line.decode("utf-8", errors="replace").strip()
        if text:
            lines.append(text)
            if text in {"OK", "PONG"} or text.startswith("ERR:") or text.startswith("STATUS:"):
                break
    return lines


def send_command(port, command, baudrate=115200, timeout=1.0, settle=0.5, response_window=10.0, retries=5):
    last_error = None

    for attempt in range(retries):
        try:
            with serial.Serial(port, baudrate, timeout=timeout, dsrdtr=False, rtscts=False) as ser:
                try:
                    ser.dtr = False
                    ser.rts = False
                except Exception:
                    pass

                time.sleep(settle)
                startup_lines = collect_lines(ser, 0.6)
                try:
                    ser.reset_input_buffer()
                except Exception:
                    pass

                ser.write((command + "\r\n").encode("utf-8"))
                ser.flush()
                response_lines = collect_lines(ser, response_window)
                return startup_lines, response_lines
        except Exception as e:
            last_error = e
            time.sleep(0.8)

    return [], [f"SERIAL_EXCEPTION:{last_error}"] if last_error else []


def main():
    parser = argparse.ArgumentParser(description="Send one command to the Pico Ink serial protocol")
    parser.add_argument("command", help="e.g. PING, TEXT:Hello, TIME:2026-03-26 14:20, STATUS")
    parser.add_argument("--port", default="/dev/ttyACM0")
    args = parser.parse_args()

    startup, response = send_command(args.port, args.command)

    if startup:
        print("[startup]")
        for line in startup:
            print(line)

    if response:
        print("[response]")
        for line in response:
            print(line)
    else:
        print("[response]")
        print("<no response>")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
