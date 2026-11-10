"""Saves the ESP32 Serial output to a file without resetting the board.

Usage, from the project root:
    python tools/serial_logger.py --port COM3 --out logs/A01_ESP32.log

Runs until it is stopped (Ctrl+C) or until --minutes have passed. If the
board is unplugged, it keeps trying to reopen the port, so a power cut
test (A08) is recorded in a single file.
"""
import argparse
import time
from datetime import datetime
from pathlib import Path

import serial  # pyserial

BAUD_RATE = 115200
REOPEN_DELAY_S = 0.2
READ_TIMEOUT_S = 0.1


def open_port(name):
    """Opens the port with DTR and RTS released, so EN is not pulsed."""
    port = serial.Serial()
    port.port = name
    port.baudrate = BAUD_RATE
    port.timeout = READ_TIMEOUT_S
    port.dtr = False
    port.rts = False
    port.open()
    return port


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--out", required=True)
    parser.add_argument("--minutes", type=float, default=0, help="0 = no limit")
    arguments = parser.parse_args()

    Path(arguments.out).parent.mkdir(parents=True, exist_ok=True)
    deadline = (
        time.monotonic() + arguments.minutes * 60 if arguments.minutes else None
    )
    with open(arguments.out, "a", encoding="utf-8", newline="\n") as log:
        def note(text):
            stamp = datetime.now().isoformat(timespec="milliseconds")
            log.write(f"# {stamp} {text}\n")
            log.flush()

        port, pending = None, b""
        note(f"logger start on {arguments.port}")
        try:
            while deadline is None or time.monotonic() < deadline:
                if port is None:
                    try:
                        port = open_port(arguments.port)
                        note("port open")
                    except serial.SerialException:
                        time.sleep(REOPEN_DELAY_S)
                        continue
                try:
                    pending += port.read(4096)
                except serial.SerialException:
                    note("port lost (board unplugged?)")
                    port.close()
                    port, pending = None, b""
                    continue
                while b"\n" in pending:
                    raw, pending = pending.split(b"\n", 1)
                    log.write(raw.decode("utf-8", errors="replace").rstrip("\r") + "\n")
                    log.flush()
        except KeyboardInterrupt:
            pass
        finally:
            note("logger stop")
            if port is not None:
                port.close()


if __name__ == "__main__":
    main()
