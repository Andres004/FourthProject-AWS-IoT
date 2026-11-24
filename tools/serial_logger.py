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
# One read asks for this many bytes. At 115200 baud the board sends at most
# about 1150 bytes per READ_TIMEOUT_S, so a read that comes back full can only
# be the stale data the CP210x driver replays (thousands of repeated line
# fragments) when the port is reopened after being closed for a while.
READ_SIZE_BYTES = 4096


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
        discarding, synced, dropped = False, True, 0
        note(f"logger start on {arguments.port}")
        try:
            while deadline is None or time.monotonic() < deadline:
                if port is None:
                    try:
                        port = open_port(arguments.port)
                        discarding, dropped = True, 0
                        note("port open")
                    except serial.SerialException:
                        time.sleep(REOPEN_DELAY_S)
                        continue
                try:
                    chunk = port.read(READ_SIZE_BYTES)
                except serial.SerialException:
                    note("port lost (board unplugged?)")
                    port.close()
                    port, pending = None, b""
                    continue
                if discarding:
                    # Stale data is replayed back to back. Once a full read
                    # shows it is there, drop everything until the first
                    # empty read (the board's real output has pauses).
                    stale = len(chunk) == READ_SIZE_BYTES or (dropped and chunk)
                    if stale:
                        dropped += len(chunk)
                        continue
                    discarding = False
                    if dropped:
                        # Real output may resume in the middle of a line.
                        synced = False
                        note(f"dropped {dropped} stale bytes from the driver")
                pending += chunk
                while b"\n" in pending:
                    raw, pending = pending.split(b"\n", 1)
                    if not synced:
                        synced = True
                        continue
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
