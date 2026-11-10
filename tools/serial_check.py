"""Automatic firmware test over the Serial port (test B02).

The ESP32 must run the local_test build, where Serial replaces AWS: each line
sent is processed as an /update/delta document and each report is printed as
LOCAL_REPORT. The script sends valid, invalid, duplicated and out-of-order
deltas and checks the response in the device log.

Usage, from the project root, with the Serial Monitor closed:
    python tools/serial_check.py --port COM3 --log docs/evidencias/B02/B02_ESP32.log

Exit code 0 when every case passes.
"""
import argparse
import json
import re
import sys
import time

import serial  # pyserial

BAUD_RATE = 115200
BOOT_TIMEOUT_S = 15  # Reset to LOCAL_TEST_MODE line
QUIET_WINDOW_S = 1.5  # Time to wait for a reaction that must NOT happen
RESPONSE_TIMEOUT_S = 3.0
SETTLE_TIME_MS = 400  # config::door::SETTLE_TIME_MS
SETTLE_TOLERANCE_MS = 60
MIN_REPORT_INTERVAL_MS = 1000  # config::report::MIN_REPORT_INTERVAL_MS
HEARTBEAT_MS = 60_000  # config::report::HEARTBEAT_PERIOD_MS
HEARTBEAT_TOLERANCE_MS = 1_500
HEARTBEAT_WAIT_S = 180  # Allows a few PIR events to restart the period
MAX_LINE_LENGTH = 256  # config::local_test::MAX_LINE_LENGTH
OPEN_ANGLE = 90
CLOSED_ANGLE = 0

DEVICE_LINE = re.compile(r"\[(\d+)\|[^\]]+\]\s+(\S+)\s*(.*)")


class Device:
    """Serial connection that keeps every line received as evidence."""

    def __init__(self, port, log_path):
        self.port = serial.Serial(port, BAUD_RATE, timeout=0.05)
        self.log = open(log_path, "w", encoding="utf-8", newline="\n")
        self.buffer = b""
        self.lines = []  # (t_ms, event, details)

    def reset(self):
        """Pulses EN through RTS, like the upload tool does."""
        self.port.dtr = False
        self.port.rts = True
        time.sleep(0.1)
        self.port.rts = False
        self.port.reset_input_buffer()

    def poll(self):
        self.buffer += self.port.read(4096)
        while b"\n" in self.buffer:
            raw, self.buffer = self.buffer.split(b"\n", 1)
            text = raw.decode("utf-8", errors="replace").rstrip("\r")
            self.log.write(text + "\n")
            self.log.flush()
            match = DEVICE_LINE.search(text)
            if match:
                self.lines.append(
                    (int(match.group(1)), match.group(2), match.group(3))
                )

    def mark(self):
        """Returns the index of the next line to arrive."""
        self.poll()
        return len(self.lines)

    def send(self, text):
        self.log.write(f"# TX {text}\n")
        self.port.write(text.encode("utf-8") + b"\n")

    def wait_for(self, start, event, timeout_s, predicate=None):
        """Returns the first line from start with that event, or None."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            self.poll()
            for line in self.lines[start:]:
                if line[1] == event and (predicate is None or predicate(line)):
                    return line
            time.sleep(0.02)
        return None

    def events_since(self, start, event):
        self.poll()
        return [line for line in self.lines[start:] if line[1] == event]


def report_door(line):
    """Returns (door, servo_angle) of a LOCAL_REPORT line."""
    reported = json.loads(line[2])["state"]["reported"]
    return reported.get("door"), reported.get("servo_angle")


class Checker:
    def __init__(self, device):
        self.device = device
        self.results = []

    def record(self, case, requirement, passed, detail):
        verdict = "PASS" if passed else "FAIL"
        self.results.append((case, requirement, verdict, detail))
        print(f"{case} [{requirement}] {verdict}: {detail}", flush=True)

    def command(self, case, requirement, version, door, angle):
        """A valid delta must move the servo and be confirmed."""
        dev = self.device
        start = dev.mark()
        dev.send(json.dumps({"version": version, "state": {"door": door}}))
        began = dev.wait_for(start, "ACTUATOR_START", RESPONSE_TIMEOUT_S)
        done = dev.wait_for(start, "ACTUATOR_DONE", RESPONSE_TIMEOUT_S)
        sent = dev.wait_for(
            start, "LOCAL_REPORT", RESPONSE_TIMEOUT_S,
            lambda line: report_door(line) == (door, angle),
        )
        delta = dev.wait_for(start, "DELTA_RX", RESPONSE_TIMEOUT_S)
        ok = all((began, done, sent, delta))
        move = done[0] - began[0] if ok else None
        confirm = sent[0] - delta[0] if ok else None
        ok = ok and abs(move - SETTLE_TIME_MS) <= SETTLE_TOLERANCE_MS
        self.record(
            case, requirement, ok,
            f"door={door}: move {move} ms (expected {SETTLE_TIME_MS} +/- "
            f"{SETTLE_TOLERANCE_MS}), DELTA_RX -> report {confirm} ms, "
            f"reported angle={angle}",
        )

    def rejected(self, case, requirement, line, expected_event):
        """An unusable delta must be logged and must not move the servo."""
        dev = self.device
        start = dev.mark()
        dev.send(line)
        logged = dev.wait_for(start, expected_event, RESPONSE_TIMEOUT_S)
        time.sleep(QUIET_WINDOW_S)
        moves = dev.events_since(start, "ACTUATOR_START")
        self.record(
            case, requirement, logged is not None and not moves,
            f"sent {line[:60]!r}: {expected_event} "
            f"{'logged' if logged else 'MISSING'} "
            f"({logged[2][:50] if logged else ''}), servo moves={len(moves)}",
        )


def run(checker):
    dev = checker.device
    dev.reset()
    ready = dev.wait_for(0, "LOCAL_TEST_MODE", BOOT_TIMEOUT_S)
    first = dev.wait_for(0, "LOCAL_REPORT", BOOT_TIMEOUT_S)
    checker.record(
        "C01", "RF2", ready is not None and first is not None
        and report_door(first) == ("closed", CLOSED_ANGLE),
        "boot in local test mode and first report with door=closed angle=0",
    )

    checker.command("C02", "RF3", 1, "open", OPEN_ANGLE)
    checker.rejected("C03", "RF12", json.dumps(
        {"version": 1, "state": {"door": "closed"}}), "STALE_IGNORED")
    checker.rejected("C04", "RF12", json.dumps(
        {"version": 0, "state": {"door": "closed"}}), "STALE_IGNORED")

    start = dev.mark()
    dev.send(json.dumps({"version": 2, "state": {"door": "open"}}))
    sent = dev.wait_for(start, "LOCAL_REPORT", RESPONSE_TIMEOUT_S)
    moves = dev.events_since(start, "ACTUATOR_START")
    checker.record(
        "C05", "RF3", sent is not None and not moves
        and report_door(sent) == ("open", OPEN_ANGLE),
        "same position again: no movement, report sent to clear the delta",
    )

    checker.rejected("C06", "RF12", json.dumps(
        {"version": 3, "state": {"door": "half"}}), "INVALID_VALUE")
    checker.rejected("C07", "RF12", json.dumps(
        {"version": 4, "state": {"door": 1}}), "INVALID_VALUE")
    checker.rejected("C08", "RF12", json.dumps(
        {"version": 5, "state": {"door": "OPEN"}}), "INVALID_VALUE")
    checker.rejected("C09", "RF12", '{"version": 6, "state": {"door": ',
                     "JSON_ERROR")
    checker.rejected("C10", "RF12", json.dumps({"version": 7, "foo": 1}),
                     "JSON_ERROR")
    checker.rejected("C11", "RF12", "x" * (MAX_LINE_LENGTH + 40), "JSON_ERROR")

    start = dev.mark()
    dev.send(json.dumps({"version": 8, "state": {"presence": True}}))
    time.sleep(QUIET_WINDOW_S)
    moves = dev.events_since(start, "ACTUATOR_START")
    errors = dev.events_since(start, "INVALID_VALUE")
    checker.record(
        "C12", "RF12", not moves and not errors,
        "delta without the door attribute is ignored by the actuator",
    )

    checker.command("C13", "RF3", 9, "closed", CLOSED_ANGLE)

    start = dev.mark()
    dev.send(json.dumps({"version": 10, "state": {"door": "open"}}))
    time.sleep(0.15)  # Reverse while the servo is still moving.
    dev.send(json.dumps({"version": 11, "state": {"door": "closed"}}))
    final = dev.wait_for(
        start, "LOCAL_REPORT", RESPONSE_TIMEOUT_S,
        lambda line: report_door(line) == ("closed", CLOSED_ANGLE),
    )
    opened = [
        line for line in dev.events_since(start, "LOCAL_REPORT")
        if report_door(line)[0] == "open"
    ]
    checker.record(
        "C14", "RF3", final is not None and not opened,
        "order reversed during the move: ends closed and never reports open",
    )

    start = dev.mark()
    for version, door in ((12, "open"), (13, "closed"), (14, "open")):
        dev.send(json.dumps({"version": version, "state": {"door": door}}))
        time.sleep(0.6)  # Each move ends before the next order.
    dev.wait_for(start, "LOCAL_REPORT", 4.0,
                 lambda line: report_door(line) == ("open", OPEN_ANGLE))
    time.sleep(1.5)
    times = [line[0] for line in dev.events_since(start, "LOCAL_REPORT")]
    gaps = [b - a for a, b in zip(times, times[1:])]
    checker.record(
        "C15", "RNF4", bool(gaps) and min(gaps) >= MIN_REPORT_INTERVAL_MS - 5,
        f"3 orders 600 ms apart: {len(times)} reports, minimum gap "
        f"{min(gaps, default=None)} ms (>= {MIN_REPORT_INTERVAL_MS})",
    )

    # Any event report (e.g. the PIR) restarts the heartbeat period, so the
    # gap is measured from the report just before the heartbeat.
    start = dev.mark()
    print("C16 waiting for the heartbeat (60 s after the last report)...",
          flush=True)
    beat = dev.wait_for(
        start, "REPORT_TX", HEARTBEAT_WAIT_S,
        lambda line: line[2].startswith("reason=heartbeat"),
    )
    gap = None
    if beat:
        before = [
            line for line in dev.events_since(0, "REPORT_TX")
            if line[0] < beat[0]
        ]
        gap = beat[0] - before[-1][0]
    checker.record(
        "C16", "RF2/RNF4",
        gap is not None and abs(gap - HEARTBEAT_MS) <= HEARTBEAT_TOLERANCE_MS,
        f"heartbeat {gap} ms after the last report (expected {HEARTBEAT_MS} "
        f"+/- {HEARTBEAT_TOLERANCE_MS})",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--log", default="B02_ESP32.log")
    arguments = parser.parse_args()

    device = Device(arguments.port, arguments.log)
    checker = Checker(device)
    try:
        run(checker)
    finally:
        device.port.close()
        device.log.close()

    passed = sum(1 for result in checker.results if result[2] == "PASS")
    print(f"\nRESULT {passed}/{len(checker.results)} cases PASS")
    sys.exit(0 if passed == len(checker.results) else 1)


if __name__ == "__main__":
    main()
