"""Automatic firmware test over the Serial port (test B02), for both boards.

The ESP32 must run a *_local_test build, where Serial replaces AWS: each line
sent is processed as an /update/delta document and each report is printed as
LOCAL_REPORT. The script sends valid, invalid, duplicated and out-of-order
deltas and checks the response in the device log.

Board 1 (vent): the gas reading is simulated with "sim_gas_pct" (only in
vent_local_test), so the hysteresis of rule E1, rule E2, the rejection of
voice commands, the clean-up of desired, the event queue and the NVS
persistence (E3) are checked without smoke.

Board 2 (lights): the five zones, repeated and invalid commands, the
clean-up of cmd_origin and the grouping of an "all lights" command.

Usage, from the project root, with the Serial Monitor closed:
    python tools/serial_check.py --board vent --port COM3 --log docs/evidencias_p4/B02/B02_vent_ESP32.log
    python tools/serial_check.py --board lights --port COM4 --log docs/evidencias_p4/B02/B02_lights_ESP32.log

Add --skip-heartbeat to leave out the last case, which waits about 60 s.
Exit code 0 when every case passes.
"""
import argparse
import json
import re
import sys
import time

import serial  # pyserial

BAUD_RATE = 115200
BOOT_TIMEOUT_S = 15           # Reset to the first report
QUIET_WINDOW_S = 1.5          # Time to wait for a reaction that must NOT happen
RESPONSE_TIMEOUT_S = 4.0      # Gas windows close every 1 s, reports every >= 1 s

# Values copied from the firmware configuration (must match the code).
SETTLE_TIME_MS = 400           # config::window::SETTLE_TIME_MS
SETTLE_TOLERANCE_MS = 60
MIN_REPORT_INTERVAL_MS = 1000  # config::report::MIN_REPORT_INTERVAL_MS
HEARTBEAT_MS = 60_000          # config::report::HEARTBEAT_PERIOD_MS
HEARTBEAT_TOLERANCE_MS = 1_500
HEARTBEAT_WAIT_S = 180         # Event reports restart the heartbeat period
MAX_LINE_LENGTH = 512          # config::local_test::MAX_LINE_LENGTH
PAYLOAD_BUFFER_SIZE = 1024     # config::report::PAYLOAD_BUFFER_SIZE
OPEN_ANGLE = 90                # config::window::OPEN_ANGLE_DEG
CLOSED_ANGLE = 0               # config::window::CLOSED_ANGLE_DEG
GAS_WINDOW_MS = 1000           # config::gas::AVERAGE_WINDOW_MS

# Thresholds used by the test (set explicitly at the start, not the defaults).
TEST_HIGH_PCT = 30
TEST_LOW_PCT = 20

COMMON_KEYS = ("event", "origin", "seq", "device_ts")
VENT_KEYS = ("gas_pct", "gas_mv", "gas_alarm", "warming_up", "window",
             "servo_angle", "mode", "gas_high_pct", "gas_low_pct")
ZONES = ("kitchen", "living", "dining", "bathroom", "bedroom")
LIGHT_KEYS = tuple(f"light_{zone}" for zone in ZONES) + ("presence",)

DEVICE_LINE = re.compile(r"\[(\d+)\|[^\]]+\]\s+(\S+)\s*(.*)")


class Device:
    """Serial connection that keeps every line received as evidence."""

    def __init__(self, port, log_path):
        self.port = serial.Serial(port, BAUD_RATE, timeout=0.05)
        self.log = open(log_path, "w", encoding="utf-8", newline="\n")
        self.buffer = b""
        self.lines = []  # (t_ms, event, details)
        self.version = 0

    def reset(self):
        """Pulses EN through RTS, like the upload tool does."""
        self.port.dtr = False
        self.port.rts = True
        time.sleep(0.1)
        self.port.rts = False
        self.port.reset_input_buffer()
        self.buffer = b""
        self.lines = []
        self.log.write("# RESET\n")

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

    def send_raw(self, text):
        self.log.write(f"# TX {text}\n")
        self.port.write(text.encode("utf-8") + b"\n")

    def send_state(self, state):
        """Sends a delta with the next Shadow version."""
        self.version += 1
        self.send_raw(json.dumps({"version": self.version, "state": state}))

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

    def wait_report(self, start, predicate, timeout_s=RESPONSE_TIMEOUT_S):
        """First LOCAL_REPORT whose parsed document satisfies predicate."""
        return self.wait_for(start, "LOCAL_REPORT", timeout_s,
                             lambda line: predicate(report_doc(line)))


def report_doc(line):
    """Parses the JSON document of a LOCAL_REPORT line."""
    try:
        return json.loads(line[2])
    except json.JSONDecodeError:
        return {"state": {"reported": {}}}


def reported(doc):
    return doc["state"]["reported"]


def desired(doc):
    return doc["state"].get("desired", {})


def has(doc, **expected):
    values = reported(doc)
    return all(values.get(key) == value for key, value in expected.items())


class Checker:
    def __init__(self, device):
        self.device = device
        self.results = []

    def record(self, case, requirement, passed, detail):
        verdict = "PASS" if passed else "FAIL"
        self.results.append((case, requirement, verdict, detail))
        print(f"{case} [{requirement}] {verdict}: {detail}", flush=True)

    def rejected(self, case, requirement, text, expected_event,
                 forbidden=("ACTUATOR_START", "LIGHT_APPLIED")):
        """An unusable delta must be logged and must not move anything."""
        dev = self.device
        start = dev.mark()
        dev.send_raw(text)
        logged = dev.wait_for(start, expected_event, RESPONSE_TIMEOUT_S)
        time.sleep(QUIET_WINDOW_S)
        moves = [line for event in forbidden
                 for line in dev.events_since(start, event)]
        self.record(
            case, requirement, logged is not None and not moves,
            f"sent {text[:60]!r}: {expected_event} "
            f"{'logged' if logged else 'MISSING'} "
            f"({logged[2][:60] if logged else ''}), moves={len(moves)}",
        )

    def boot(self, case, keys):
        """Reset, then the first report: event=boot, seq=1 and every key."""
        dev = self.device
        dev.reset()
        ready = dev.wait_for(0, "LOCAL_TEST_MODE", BOOT_TIMEOUT_S)
        first = dev.wait_for(0, "LOCAL_REPORT", BOOT_TIMEOUT_S)
        doc = report_doc(first) if first else None
        missing = [key for key in keys + COMMON_KEYS
                   if doc is None or key not in reported(doc)]
        ok = (ready is not None and doc is not None and not missing
              and has(doc, event="boot", origin="boot", seq=1))
        self.record(case, "RF2/V1", ok,
                    f"first report event=boot origin=boot seq=1, "
                    f"missing keys={missing}")
        return doc

    def common_tail(self, prefix, skip_heartbeat):
        """Stale versions, broken JSON, seq, report size and heartbeat."""
        dev = self.device
        stale = json.dumps({"version": dev.version, "state": {}})
        self.rejected(f"{prefix}90", "RF12", stale, "STALE_IGNORED")
        self.rejected(f"{prefix}91", "RF12", '{"version": 99999, "state": {',
                      "JSON_ERROR")
        self.rejected(f"{prefix}92", "RF12",
                      json.dumps({"version": 99999, "foo": 1}), "JSON_ERROR")
        self.rejected(f"{prefix}93", "RF12", "x" * (MAX_LINE_LENGTH + 40),
                      "JSON_ERROR")

        reports = dev.events_since(0, "LOCAL_REPORT")
        seqs = [reported(report_doc(line)).get("seq") for line in reports]
        consecutive = seqs == list(range(1, len(seqs) + 1))
        self.record(f"{prefix}94", "V2", consecutive and bool(seqs),
                    f"{len(seqs)} reports with seq 1..{len(seqs)} without gaps")

        times = [line[0] for line in reports]
        gaps = [b - a for a, b in zip(times, times[1:])]
        sizes = [len(line[2]) for line in reports]
        self.record(
            f"{prefix}95", "RNF4/V3",
            bool(gaps) and min(gaps) >= MIN_REPORT_INTERVAL_MS - 5
            and max(sizes) < PAYLOAD_BUFFER_SIZE,
            f"minimum gap {min(gaps, default=None)} ms (>= "
            f"{MIN_REPORT_INTERVAL_MS}), largest report {max(sizes)} bytes "
            f"(< {PAYLOAD_BUFFER_SIZE})",
        )

        if skip_heartbeat:
            return
        start = dev.mark()
        print(f"{prefix}96 waiting for the heartbeat (60 s after the last "
              "report)...", flush=True)
        beat = dev.wait_for(start, "REPORT_TX", HEARTBEAT_WAIT_S,
                            lambda line: "event=heartbeat" in line[2])
        gap = None
        if beat:
            before = [line for line in dev.events_since(0, "REPORT_TX")
                      if line[0] < beat[0]]
            gap = beat[0] - before[-1][0] if before else None
        self.record(
            f"{prefix}96", "RF2/RNF4",
            gap is not None and abs(gap - HEARTBEAT_MS) <= HEARTBEAT_TOLERANCE_MS,
            f"heartbeat {gap} ms after the last report (expected "
            f"{HEARTBEAT_MS} +/- {HEARTBEAT_TOLERANCE_MS})",
        )


# --------------------------------------------------------------------------
# Board 1: ventilation
# --------------------------------------------------------------------------

def set_gas(dev, pct):
    dev.send_state({"sim_gas_pct": pct})


def run_vent(checker, skip_heartbeat):
    dev = checker.device
    doc = checker.boot("V01", VENT_KEYS)
    checker.record(
        "V02", "E2", doc is not None and has(doc, warming_up=True, gas_alarm=False),
        "boot report during warm-up: warming_up=true, gas_alarm=false",
    )

    # Known starting point: auto, test thresholds, clean air.
    start = dev.mark()
    dev.send_state({"mode": "auto", "gas_high_pct": TEST_HIGH_PCT,
                    "gas_low_pct": TEST_LOW_PCT, "cmd_origin": "voice"})
    set_gas(dev, 5)
    ready = dev.wait_report(start, lambda d: has(
        d, mode="auto", gas_high_pct=TEST_HIGH_PCT, gas_low_pct=TEST_LOW_PCT,
        warming_up=False, gas_alarm=False, window="closed"))
    checker.record("V03", "E2/RF14", ready is not None,
                   f"auto, {TEST_HIGH_PCT}/{TEST_LOW_PCT}, simulated 5 %: "
                   "warm-up ends, no alarm, window closed")

    # E1 hysteresis, upper border: just below and exactly at the threshold.
    start = dev.mark()
    set_gas(dev, TEST_HIGH_PCT - 1)
    time.sleep(2 * GAS_WINDOW_MS / 1000)
    early = dev.events_since(start, "GAS_ALARM_ON")
    checker.record("V04", "E1", not early,
                   f"gas {TEST_HIGH_PCT - 1} % (< high): no alarm")

    start = dev.mark()
    set_gas(dev, TEST_HIGH_PCT)
    alarm = dev.wait_for(start, "GAS_ALARM_ON", RESPONSE_TIMEOUT_S)
    done = dev.wait_for(start, "ACTUATOR_DONE", RESPONSE_TIMEOUT_S,
                        lambda line: "window=open" in line[2])
    rep = dev.wait_report(start, lambda d: has(
        d, event="gas_alarm_on", origin="edge", gas_alarm=True))
    rep_win = dev.wait_report(start, lambda d: has(
        d, event="window_changed", origin="edge", window="open",
        servo_angle=OPEN_ANGLE))
    edge_ms = done[0] - alarm[0] if alarm and done else None
    checker.record(
        "V05", "E1/RF12", all((alarm, done, rep, rep_win)),
        f"gas {TEST_HIGH_PCT} % (= high): GAS_ALARM_ON -> ACTUATOR_DONE "
        f"{edge_ms} ms; reports gas_alarm_on and window_changed, origin=edge",
    )

    # E1 hysteresis, lower border.
    start = dev.mark()
    set_gas(dev, TEST_LOW_PCT + 1)
    time.sleep(2 * GAS_WINDOW_MS / 1000)
    early = dev.events_since(start, "GAS_ALARM_OFF")
    checker.record("V06", "E1", not early,
                   f"gas {TEST_LOW_PCT + 1} % (inside the band): alarm stays on")

    start = dev.mark()
    set_gas(dev, TEST_LOW_PCT)
    off = dev.wait_for(start, "GAS_ALARM_OFF", RESPONSE_TIMEOUT_S)
    closed = dev.wait_report(start, lambda d: has(
        d, window="closed", gas_alarm=False, origin="edge"))
    checker.record("V07", "E1", off is not None and closed is not None,
                   f"gas {TEST_LOW_PCT} % (= low): alarm off, window closes "
                   "(origin=edge)")

    # Voice command in auto: rejected and removed from desired.
    start = dev.mark()
    dev.send_state({"window": "open", "cmd_origin": "voice"})
    rejected = dev.wait_for(start, "COMMAND_REJECTED", RESPONSE_TIMEOUT_S,
                            lambda line: "reason=auto_mode" in line[2])
    cleaned = dev.wait_report(start, lambda d: "window" in desired(d)
                              and desired(d)["window"] is None)
    time.sleep(QUIET_WINDOW_S)
    moves = dev.events_since(start, "ACTUATOR_START")
    checker.record("V08", "5.6", rejected is not None and cleaned is not None
                   and not moves,
                   "window=open in auto: COMMAND_REJECTED auto_mode, no move, "
                   "desired.window=null")

    # Manual mode by voice.
    start = dev.mark()
    dev.send_state({"mode": "manual", "cmd_origin": "voice"})
    applied = dev.wait_for(start, "MODE_APPLIED", RESPONSE_TIMEOUT_S,
                           lambda line: "mode=manual origin=voice" in line[2])
    rep = dev.wait_report(start, lambda d: has(
        d, event="mode_changed", mode="manual", origin="voice")
        and desired(d).get("cmd_origin", 0) is None)
    checker.record("V09", "RF14", applied is not None and rep is not None,
                   "mode=manual by voice: MODE_APPLIED, mode_changed, "
                   "desired.cmd_origin=null")

    # Manual: voice opens and closes the window.
    for case, target, angle in (("V10", "open", OPEN_ANGLE),
                                ("V11", "closed", CLOSED_ANGLE)):
        start = dev.mark()
        dev.send_state({"window": target, "cmd_origin": "voice"})
        began = dev.wait_for(start, "ACTUATOR_START", RESPONSE_TIMEOUT_S)
        done = dev.wait_for(start, "ACTUATOR_DONE", RESPONSE_TIMEOUT_S)
        rep = dev.wait_report(start, lambda d, t=target, a=angle: has(
            d, event="window_changed", window=t, servo_angle=a, origin="voice")
            and desired(d).get("window", 0) is None)
        move = done[0] - began[0] if began and done else None
        ok = (rep is not None and move is not None
              and abs(move - SETTLE_TIME_MS) <= SETTLE_TOLERANCE_MS)
        checker.record(case, "RF3/RF12", ok,
                       f"manual, window={target}: move {move} ms (expected "
                       f"{SETTLE_TIME_MS} +/- {SETTLE_TOLERANCE_MS}), report "
                       "origin=voice, desired.window=null")

    # Manual with alarm: the window does not move by itself...
    start = dev.mark()
    set_gas(dev, TEST_HIGH_PCT + 10)
    alarm = dev.wait_for(start, "GAS_ALARM_ON", RESPONSE_TIMEOUT_S)
    rep = dev.wait_report(start, lambda d: has(
        d, event="gas_alarm_on", gas_alarm=True, mode="manual",
        window="closed"))
    time.sleep(QUIET_WINDOW_S)
    moves = dev.events_since(start, "ACTUATOR_START")
    checker.record("V12", "5.5", alarm is not None and rep is not None
                   and not moves,
                   "manual + gas: alarm reported, window stays closed")

    # ...and "close the window" is rejected while the alarm is on.
    dev.send_state({"window": "open", "cmd_origin": "voice"})
    time.sleep(1.5)
    start = dev.mark()
    dev.send_state({"window": "closed", "cmd_origin": "voice"})
    rejected = dev.wait_for(start, "COMMAND_REJECTED", RESPONSE_TIMEOUT_S,
                            lambda line: "reason=gas_alarm" in line[2])
    time.sleep(QUIET_WINDOW_S)
    moves = dev.events_since(start, "ACTUATOR_START")
    checker.record("V13", "5.6", rejected is not None and not moves,
                   "manual + alarm, window=closed: COMMAND_REJECTED gas_alarm")

    # Cloud rule C1 seen from the board: auto from the Cloud while the window
    # is closed and the gas is high. Two separate reports, mode first.
    dev.send_state({"sim_gas_pct": TEST_LOW_PCT - 5})
    dev.wait_for(dev.mark(), "GAS_ALARM_OFF", RESPONSE_TIMEOUT_S)
    dev.send_state({"window": "closed", "cmd_origin": "voice"})
    time.sleep(1.5)
    set_gas(dev, TEST_HIGH_PCT + 10)
    dev.wait_for(dev.mark(), "GAS_ALARM_ON", RESPONSE_TIMEOUT_S)
    time.sleep(1.5)
    start = dev.mark()
    dev.send_state({"mode": "auto", "cmd_origin": "cloud"})
    applied = dev.wait_for(start, "MODE_APPLIED", RESPONSE_TIMEOUT_S,
                           lambda line: "origin=cloud" in line[2])
    rep_mode = dev.wait_report(start, lambda d: has(
        d, event="mode_changed", origin="cloud", mode="auto"))
    rep_win = dev.wait_report(start, lambda d: has(
        d, event="window_changed", origin="edge", window="open"),
        timeout_s=2 * RESPONSE_TIMEOUT_S)
    checker.record("V14", "C1/E1", all((applied, rep_mode, rep_win)),
                   "auto from the Cloud with gas high: mode_changed "
                   "origin=cloud, then window_changed origin=edge (2 reports)")

    # Thresholds by voice: valid, then invalid ones.
    set_gas(dev, 5)
    time.sleep(2.5)
    start = dev.mark()
    dev.send_state({"gas_high_pct": 40, "gas_low_pct": 25,
                    "cmd_origin": "voice"})
    applied = dev.wait_for(start, "THRESHOLDS_APPLIED", RESPONSE_TIMEOUT_S)
    rep = dev.wait_report(start, lambda d: has(
        d, event="thresholds_changed", gas_high_pct=40, gas_low_pct=25))
    checker.record("V15", "RF14/E3", applied is not None and rep is not None,
                   "thresholds 40/25: THRESHOLDS_APPLIED and thresholds_changed")

    for case, state in (("V16", {"gas_low_pct": 40}),
                        ("V17", {"gas_high_pct": 100}),
                        ("V18", {"gas_low_pct": 0}),
                        ("V19", {"gas_high_pct": "abc"})):
        dev.version += 1
        checker.rejected(case, "RF14", json.dumps(
            {"version": dev.version, "state": state}), "COMMAND_REJECTED")

    dev.version += 1
    checker.rejected("V20", "RF12", json.dumps(
        {"version": dev.version, "state": {"mode": "turbo"}}), "INVALID_VALUE")
    dev.version += 1
    checker.rejected("V21", "RF12", json.dumps(
        {"version": dev.version, "state": {"window": "half"}}), "INVALID_VALUE")

    # E3: manual + 40/25 survive a restart.
    dev.send_state({"mode": "manual", "cmd_origin": "voice"})
    time.sleep(1.5)
    dev.reset()
    loaded = dev.wait_for(0, "SETTINGS_LOADED", BOOT_TIMEOUT_S,
                          lambda line: "mode=manual gas_high_pct=40 "
                          "gas_low_pct=25" in line[2])
    first = dev.wait_report(0, lambda d: has(
        d, event="boot", mode="manual", gas_high_pct=40, gas_low_pct=25),
        timeout_s=BOOT_TIMEOUT_S)
    checker.record("V22", "E3", loaded is not None and first is not None,
                   "after a restart: SETTINGS_LOADED manual 40/25 and boot "
                   "report with those values")
    dev.version = 0

    # Leave the board in its normal state.
    dev.send_state({"mode": "auto", "gas_high_pct": TEST_HIGH_PCT,
                    "gas_low_pct": TEST_LOW_PCT, "cmd_origin": "voice",
                    "sim_gas_pct": 5})
    time.sleep(1.5)
    checker.common_tail("V", skip_heartbeat)


# --------------------------------------------------------------------------
# Board 2: lights and entrance
# --------------------------------------------------------------------------

def run_lights(checker, skip_heartbeat):
    dev = checker.device
    doc = checker.boot("L01", LIGHT_KEYS)
    checker.record(
        "L02", "RF2", doc is not None and has(doc, presence=False)
        and all(reported(doc).get(f"light_{zone}") in ("on", "off")
                for zone in ZONES),
        "boot report: five light_* with on/off and presence=false",
    )

    for index, zone in enumerate(ZONES, start=3):
        key = f"light_{zone}"
        start = dev.mark()
        dev.send_state({key: "on", "cmd_origin": "voice"})
        applied = dev.wait_for(start, "LIGHT_APPLIED", RESPONSE_TIMEOUT_S,
                               lambda line, z=zone: f"zone={z} state=on "
                               "origin=voice" in line[2])
        rep = dev.wait_report(start, lambda d, k=key: has(
            d, event="light_changed", origin="voice", **{k: "on"})
            and desired(d).get("cmd_origin", 0) is None
            and k not in desired(d))
        checker.record(f"L{index:02d}", "RF3/RF12",
                       applied is not None and rep is not None,
                       f"{key}=on: LIGHT_APPLIED, light_changed origin=voice, "
                       "cmd_origin cleared and light kept in desired")

    start = dev.mark()
    dev.send_state({"light_kitchen": "on"})
    confirm = dev.wait_report(start, lambda d: has(d, light_kitchen="on"))
    time.sleep(QUIET_WINDOW_S)
    applied = dev.events_since(start, "LIGHT_APPLIED")
    checker.record("L08", "RF3", confirm is not None and not applied,
                   "light already on: no change, report sent to clear the delta")

    start = dev.mark()
    dev.send_state({f"light_{zone}": "off" for zone in ZONES})
    rep = dev.wait_report(start, lambda d: all(
        reported(d).get(f"light_{zone}") == "off" for zone in ZONES))
    time.sleep(QUIET_WINDOW_S)
    applied = dev.events_since(start, "LIGHT_APPLIED")
    reports = dev.events_since(start, "LOCAL_REPORT")
    checker.record("L09", "RF3/RNF4",
                   rep is not None and len(applied) == len(ZONES)
                   and len(reports) == 1,
                   f"all lights off in one delta: {len(applied)} LIGHT_APPLIED, "
                   f"{len(reports)} report (expected 5 and 1)")

    for case, value in (("L10", "ON"), ("L11", 1), ("L12", "half")):
        dev.version += 1
        checker.rejected(case, "RF12", json.dumps(
            {"version": dev.version, "state": {"light_living": value}}),
            "INVALID_VALUE")

    checker.common_tail("L", skip_heartbeat)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--board", choices=("vent", "lights"), required=True)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--log", default="B02_ESP32.log")
    parser.add_argument("--skip-heartbeat", action="store_true")
    arguments = parser.parse_args()

    device = Device(arguments.port, arguments.log)
    checker = Checker(device)
    try:
        if arguments.board == "vent":
            run_vent(checker, arguments.skip_heartbeat)
        else:
            run_lights(checker, arguments.skip_heartbeat)
    finally:
        device.port.close()
        device.log.close()

    passed = sum(1 for result in checker.results if result[2] == "PASS")
    print(f"\nRESULT {passed}/{len(checker.results)} cases PASS")
    sys.exit(0 if passed == len(checker.results) else 1)


if __name__ == "__main__":
    main()
