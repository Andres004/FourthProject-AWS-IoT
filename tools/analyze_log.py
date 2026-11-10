"""Measures the requirements from the logs of a test run.

Usage, from the project root:
    python tools/analyze_log.py FILE [FILE ...] [-o OUTPUT.txt]

FILE is either a Serial Monitor log of the ESP32 (logs/device-monitor-*.log)
or a CloudWatch export of the Lambda (CSV or text with SKILL_REQUEST lines).
The type of each file is detected from its content. When both kinds are
given, Lambda commands are matched with the device by Shadow version to
measure the end-to-end time with the UTC clocks of both sides.

Each result line starts with the requirement it measures and ends with
PASS, FAIL, NOT ENOUGH DATA or INFO.
"""
import argparse
import csv
import io
import json
import re
import statistics
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Acceptance values of the declared requirements (docs/PLAN_DE_PRUEBAS.md).
MIN_STABLE_RUN_MS = 15 * 60_000  # RNF1: continuous run of at least 15 min.
MAX_LOOP_MS = 500  # RNF1: longest loop() iteration while connected.
MAX_HEAP_LOSS_BYTES = 4096  # RNF1: free heap, first vs. last HEALTH line.
MAX_REPORT_GAP_MS = 61_500  # RF2/RNF4: 60 s heartbeat + loop tolerance.
MAX_EVENT_REPORT_MS = 1_100  # RNF4: state change -> REPORT_TX (1 s limit).
MAX_DELTA_TO_REPORT_MS = 1_500  # RF3: DELTA_RX -> confirming REPORT_TX.
MAX_END_TO_END_MS = 3_000  # RNF3: Lambda receives intent -> door confirmed.
MIN_COMMANDS = 20  # RNF3: commands needed for the measurement.
MAX_PENDING_APPLY_MS = 10_000  # RNF5: WIFI_CONNECTED -> pending door moved.
WIFI_RETRY_MS = 10_000  # RNF5: firmware WiFi retry interval.
RETRY_TOLERANCE_MS = 500  # Loop and logging delays around a retry.
PRESENCE_HOLD_MS = 10_000  # RNF2: presence kept after the last motion.
PIR_WARMUP_MS = 30_000  # RNF2: readings ignored after boot.
HEARTBEATS_PER_DAY = 24 * 60  # RNF4: one heartbeat per minute.
DAYS_PER_MONTH = 30

DEVICE_LINE = re.compile(r"\[(\d+)\|([^\]]+)\]\s+(\S+)\s*(.*)")
VERSION = re.compile(r"version=(-?\d+)")
DOOR = re.compile(r"door=(\w+)")
MS_PER_S = 1000
MS_PER_HOUR = 3_600_000
LIST_LIMIT = 25  # Rows printed one by one in each table.


@dataclass
class Event:
    """One line of the ESP32 log."""

    t_ms: int
    utc_ms: int | None
    name: str
    details: str
    line_no: int

    def payload(self):
        """Returns the JSON object at the end of the details, or None."""
        start = self.details.find("{")
        if start < 0:
            return None
        try:
            return json.loads(self.details[start:])
        except json.JSONDecodeError:
            return None


class Report:
    """Collects result lines and prints them."""

    def __init__(self):
        self.lines = []

    def title(self, text):
        self.lines.append("")
        self.lines.append(f"== {text} ==")

    def info(self, text):
        self.lines.append(f"   {text}")

    def result(self, requirement, text, passed, enough=True):
        if passed is None:
            word = "INFO"
        elif not enough:
            word = "NOT ENOUGH DATA"
        else:
            word = "PASS" if passed else "FAIL"
        self.lines.append(f"{requirement} {text} -> {word}")

    def text(self):
        return "\n".join(self.lines) + "\n"


def parse_utc(text):
    """Returns epoch milliseconds for an ISO time, or None for '-'."""
    if text in ("-", ""):
        return None
    moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    return int(moment.timestamp() * MS_PER_S)


def stats(values):
    """Returns 'n, min, median, p95, max' for a list of numbers."""
    if not values:
        return "n=0"
    ordered = sorted(values)
    p95 = ordered[max(0, round(0.95 * len(ordered)) - 1)]
    return (
        f"n={len(ordered)} min={ordered[0]:.0f} "
        f"median={statistics.median(ordered):.0f} p95={p95:.0f} "
        f"max={ordered[-1]:.0f}"
    )


def read_text(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_device(text):
    events = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = DEVICE_LINE.search(line)
        if match:
            events.append(
                Event(
                    int(match.group(1)),
                    parse_utc(match.group(2)),
                    match.group(3),
                    match.group(4).strip(),
                    number,
                )
            )
    return events


def load_lambda(text, path):
    """Extracts the SKILL_REQUEST JSON objects from any export format."""
    chunks = [text]
    if path.lower().endswith(".csv"):
        chunks = [cell for row in csv.reader(io.StringIO(text)) for cell in row]
    decoder = json.JSONDecoder()
    records = []
    for chunk in chunks:
        position = chunk.find('{"event": "SKILL_REQUEST"')
        while position >= 0:
            try:
                record, end = decoder.raw_decode(chunk, position)
                records.append(record)
            except json.JSONDecodeError:
                end = position + 1
            position = chunk.find('{"event": "SKILL_REQUEST"', end)
    unique = {}
    for record in records:  # Exports may repeat a line.
        unique[(record.get("start_utc_ms"), record.get("intent"))] = record
    return sorted(unique.values(), key=lambda r: r.get("start_utc_ms") or 0)


def segments(events):
    """Splits the device log at each BOOT (a restart)."""
    parts, current = [], []
    for event in events:
        if event.name == "BOOT" and current:
            parts.append(current)
            current = []
        current.append(event)
    if current:
        parts.append(current)
    return parts


def connected_windows(events):
    """Returns (start, end) t_ms ranges where the MQTT link was up."""
    windows, start = [], None
    for event in events:
        if event.name == "MQTT_CONNECTED":
            start = event.t_ms
        elif event.name in ("MQTT_LOST", "WIFI_LOST", "BOOT") and start is not None:
            windows.append((start, event.t_ms))
            start = None
    if start is not None:
        windows.append((start, events[-1].t_ms))
    return windows


def inside(t_ms, windows):
    return any(start <= t_ms <= end for start, end in windows)


def next_event(events, index, names, limit_ms, predicate=None):
    """Returns the first later event in names within limit_ms, or None."""
    origin = events[index].t_ms
    for event in events[index + 1:]:
        if event.t_ms - origin > limit_ms:
            return None
        if event.name in names and (predicate is None or predicate(event)):
            return event
    return None


def analyze_device(events, report):
    report.title("ESP32 log")
    if not events:
        report.info("no device lines found")
        return
    span_ms = events[-1].t_ms - events[0].t_ms
    boots = [e for e in events if e.name == "BOOT"]
    reasons = [e.details for e in events if e.name == "RESET_REASON"]
    synced = any(e.utc_ms is not None for e in events)
    report.info(
        f"lines={len(events)} span={span_ms / 60_000:.1f} min boots={len(boots)} "
        f"reset_reasons={reasons or '-'} utc_clock={'yes' if synced else 'no'}"
    )
    for name in ("LINK_CODE", "PIR_READY", "TIME_SYNCED"):
        found = [e for e in events if e.name == name]
        if found:
            report.info(f"{name} at t={found[0].t_ms} ms {found[0].details}")
    errors = [
        e for e in events
        if e.name in ("JSON_ERROR", "INVALID_VALUE", "UPDATE_REJECTED",
                      "REPORT_TX_FAILED", "REPORT_TOO_LARGE", "GET_TX_FAILED",
                      "MQTT_CONNECT_FAILED", "MQTT_SUBSCRIBE_FAILED",
                      "STALE_IGNORED", "GET_REJECTED")
    ]
    report.info(f"error/warning lines: {len(errors)}")
    for event in errors[:LIST_LIMIT]:
        report.info(f"  line {event.line_no} t={event.t_ms} {event.name} {event.details[:90]}")

    analyze_stability(events, report)
    analyze_reports(events, report)
    analyze_actuation(events, report)
    analyze_presence(events, report)
    analyze_reconnection(events, report)


def analyze_stability(events, report):
    report.title("RNF1 stability")
    longest = max(segments(events), key=lambda s: s[-1].t_ms - s[0].t_ms)
    run_ms = longest[-1].t_ms - longest[0].t_ms
    restarts = sum(1 for e in events if e.name == "BOOT") - (
        1 if events[0].name == "BOOT" else 0
    )
    health = [e for e in longest if e.name == "HEALTH"]
    fields = []
    for event in health:
        values = dict(item.split("=") for item in event.details.split())
        fields.append({key: int(value) for key, value in values.items()})
    report.result(
        "RNF1", f"longest run without restart: {run_ms / 60_000:.1f} min (>= 15.0)",
        run_ms >= MIN_STABLE_RUN_MS,
    )
    report.result("RNF1", f"restarts inside the log: {restarts} (0)", restarts == 0)
    if not fields:
        report.result("RNF1", "HEALTH lines", False, enough=False)
        return
    max_loop = max(f["max_loop_ms"] for f in fields)
    drops = fields[-1]["wifi_drops"] + fields[-1]["mqtt_drops"]
    heap_loss = fields[0]["heap"] - fields[-1]["heap"]
    rssi = [f["rssi"] for f in fields if f["rssi"] != 0]
    report.info(
        f"HEALTH lines={len(fields)} heap first/last={fields[0]['heap']}/"
        f"{fields[-1]['heap']} min_heap={min(f['min_heap'] for f in fields)} "
        f"rssi {min(rssi, default=0)}..{max(rssi, default=0)} dBm"
    )
    report.result("RNF1", f"longest loop iteration: {max_loop} ms (<= {MAX_LOOP_MS})",
                  max_loop <= MAX_LOOP_MS)
    report.result("RNF1", f"WiFi + MQTT drops: {drops} (0)", drops == 0)
    report.result(
        "RNF1",
        f"free heap loss first->last HEALTH: {heap_loss} bytes "
        f"(<= {MAX_HEAP_LOSS_BYTES})",
        heap_loss <= MAX_HEAP_LOSS_BYTES,
    )


def analyze_reports(events, report):
    report.title("RF2 / RNF4 reporting")
    windows = connected_windows(events)
    reports = [e for e in events if e.name == "REPORT_TX"]
    if not reports:
        report.result("RF2", "REPORT_TX lines", False, enough=False)
        return
    kinds = {}
    for event in reports:
        kind = event.details.split()[0]
        kinds[kind] = kinds.get(kind, 0) + 1
    gaps = []
    for previous, current in zip(reports, reports[1:]):
        same_window = any(
            start <= previous.t_ms and current.t_ms <= end for start, end in windows
        )
        if same_window:
            gaps.append(current.t_ms - previous.t_ms)
    report.info(f"reports={len(reports)} {kinds} gap ms: {stats(gaps)}")
    report.result(
        "RF2/RNF4",
        f"longest gap between reports while connected: {max(gaps, default=0)} ms "
        f"(<= {MAX_REPORT_GAP_MS})",
        bool(gaps) and max(gaps) <= MAX_REPORT_GAP_MS,
        enough=bool(gaps),
    )
    incomplete = [
        e for e in reports
        if not {"door", "servo_angle", "presence"} <= set(
            ((e.payload() or {}).get("state", {}).get("reported", {})).keys()
        )
    ]
    report.result("RF2", f"reports missing an attribute: {len(incomplete)} (0)",
                  not incomplete)

    delays = []
    late = []
    for index, event in enumerate(events):
        if event.name not in ("PRESENCE_ON", "PRESENCE_OFF", "ACTUATOR_DONE"):
            continue
        if not inside(event.t_ms, windows):
            continue
        sent = next_event(events, index, ("REPORT_TX",), 5_000)
        if sent is None:
            late.append((event, None))
            continue
        delay = sent.t_ms - event.t_ms
        delays.append(delay)
        if delay > MAX_EVENT_REPORT_MS:
            late.append((event, delay))
    report.info(f"state change -> REPORT_TX ms: {stats(delays)}")
    for event, delay in late[:LIST_LIMIT]:
        report.info(f"  late: line {event.line_no} {event.name} delay={delay}")
    report.result(
        "RNF4",
        f"event report delay: max {max(delays, default=0)} ms (<= {MAX_EVENT_REPORT_MS})",
        not late,
        enough=bool(delays),
    )
    hours = (events[-1].t_ms - events[0].t_ms) / MS_PER_HOUR
    if hours > 0:
        per_day = len(reports) / hours * 24
        report.info(
            f"published reports: {len(reports) / hours:.0f}/h -> {per_day:.0f}/day, "
            f"{per_day * DAYS_PER_MONTH:.0f}/month (heartbeat only: "
            f"{HEARTBEATS_PER_DAY}/day)"
        )


def analyze_actuation(events, report):
    report.title("RF3 actuation")
    rows = []
    for index, event in enumerate(events):
        if event.name != "DELTA_RX":
            continue
        payload = event.payload() or {}
        door = payload.get("state", {}).get("door")
        stale = next_event(events, index, ("STALE_IGNORED",), 50)
        if stale is not None:
            rows.append((event, door, "stale_ignored", None, None))
            continue
        done = next_event(events, index, ("ACTUATOR_DONE",), 3_000)
        confirm = next_event(
            events, index, ("REPORT_TX",), 3_000,
            lambda e: ((e.payload() or {}).get("state", {})
                       .get("reported", {}).get("door")) == door,
        )
        rows.append(
            (event, door, "moved" if done else "no_move",
             done.t_ms - event.t_ms if done else None,
             confirm.t_ms - event.t_ms if confirm else None)
        )
    if not rows:
        report.info("no DELTA_RX lines")
        return
    for event, door, kind, move_ms, confirm_ms in rows[:LIST_LIMIT]:
        version = VERSION.search(event.details)
        report.info(
            f"line {event.line_no} version={version.group(1) if version else '-'} "
            f"door={door} {kind} move={move_ms} ms reported={confirm_ms} ms"
        )
    valid = [r for r in rows if r[1] in ("open", "closed") and r[2] != "stale_ignored"]
    confirms = [r[4] for r in valid if r[4] is not None]
    missing = [r for r in valid if r[4] is None or r[4] > MAX_DELTA_TO_REPORT_MS]
    report.info(f"DELTA_RX -> reported door ms: {stats(confirms)}")
    report.result(
        "RF3",
        f"valid deltas confirmed in reported within {MAX_DELTA_TO_REPORT_MS} ms: "
        f"{len(valid) - len(missing)}/{len(valid)}",
        not missing,
        enough=bool(valid),
    )


def analyze_presence(events, report):
    report.title("RF1 / RNF2 presence")
    ons = [e for e in events if e.name == "PRESENCE_ON"]
    offs = [e for e in events if e.name == "PRESENCE_OFF"]
    ready = [e for e in events if e.name == "PIR_READY"]
    report.info(f"PRESENCE_ON={len(ons)} PRESENCE_OFF={len(offs)}")
    if ready:
        early = [e for e in ons if e.t_ms < ready[0].t_ms]
        report.result(
            "RNF2",
            f"PIR_READY at {ready[0].t_ms} ms; presence before warm-up: {len(early)} (0)",
            not early and ready[0].t_ms >= PIR_WARMUP_MS - RETRY_TOLERANCE_MS,
        )
    durations = []
    for on in ons:
        off = next((e for e in offs if e.t_ms > on.t_ms), None)
        if off is not None:
            durations.append(off.t_ms - on.t_ms)
    short = [d for d in durations if d < PRESENCE_HOLD_MS]
    report.info(f"presence episodes ms: {stats(durations)}")
    report.result(
        "RNF2",
        f"episodes shorter than the {PRESENCE_HOLD_MS} ms hold: {len(short)} (0)",
        not short,
        enough=bool(durations),
    )


def analyze_reconnection(events, report):
    report.title("RNF5 reconnection")
    losses = [i for i, e in enumerate(events) if e.name == "WIFI_LOST"]
    boots = [i for i, e in enumerate(events) if e.name == "BOOT"]
    if not losses and not boots:
        report.info("no WIFI_LOST or BOOT in this log")
        return
    for index in sorted(losses + boots):
        origin = events[index]
        attempts = []
        wifi = mqtt = got = None
        for event in events[index + 1:]:
            if event.name == "WIFI_CONNECTING":
                attempts.append(event.t_ms)
            elif event.name == "WIFI_CONNECTED" and wifi is None:
                wifi = event
            elif event.name == "MQTT_CONNECTED" and wifi and mqtt is None:
                mqtt = event
            elif event.name == "GET_RX" and mqtt and got is None:
                got = event
                break
            elif event.name in ("BOOT", "WIFI_LOST"):
                break
        retry_gaps = [b - a for a, b in zip(attempts, attempts[1:])]
        bad_retry = [
            g for g in retry_gaps
            if abs(g - WIFI_RETRY_MS) > RETRY_TOLERANCE_MS
        ]
        report.info(
            f"{origin.name} line {origin.line_no} t={origin.t_ms}: "
            f"WiFi attempts={len(attempts)} retry gaps ms: {stats(retry_gaps)}"
        )
        if wifi is None:
            report.result("RNF5", "WiFi came back", False, enough=False)
            continue
        steps = [f"WIFI_CONNECTED t={wifi.t_ms}"]
        if mqtt:
            steps.append(f"MQTT_CONNECTED +{mqtt.t_ms - wifi.t_ms} ms")
        if got:
            steps.append(f"GET_RX +{got.t_ms - wifi.t_ms} ms ({got.details})")
        report.info("  " + ", ".join(steps))
        report.result(
            "RNF5", f"WiFi retries every {WIFI_RETRY_MS} +/- {RETRY_TOLERANCE_MS} ms",
            not bad_retry, enough=bool(retry_gaps),
        )
        if got is None:
            report.result("RNF5", "Shadow synchronized after reconnection",
                          False, enough=mqtt is not None)
            continue
        got_index = events.index(got)
        moved = next_event(events, got_index, ("ACTUATOR_DONE",), 3_000)
        if moved:
            total = moved.t_ms - wifi.t_ms
            report.result(
                "RNF5",
                f"pending desired applied: {moved.details} {total} ms after "
                f"WIFI_CONNECTED (<= {MAX_PENDING_APPLY_MS})",
                total <= MAX_PENDING_APPLY_MS,
            )
        else:
            report.result("RNF5", "no pending desired to apply after GET_RX", None)


def analyze_lambda(records, report):
    report.title("Lambda (CloudWatch SKILL_REQUEST lines)")
    if not records:
        report.info("no SKILL_REQUEST lines found")
        return
    counts = {}
    for record in records:
        key = f"{record.get('intent') or record.get('request')}:{record.get('result', '-')}"
        counts[key] = counts.get(key, 0) + 1
    report.info(f"requests={len(records)} users={len({r.get('user') for r in records})}")
    for key, count in sorted(counts.items()):
        report.info(f"  {key} x{count}")
    for record in records[:LIST_LIMIT * 2]:
        report.info(
            f"  {record.get('alexa_timestamp')} {record.get('intent') or record.get('request')} "
            f"user={record.get('user')} thing={record.get('thing')} "
            f"result={record.get('result')} lambda_ms={record.get('lambda_ms')} "
            f"confirm_ms={record.get('confirm_ms')}"
        )
    lambda_ms = [r["lambda_ms"] for r in records if r.get("confirm_ms") is None
                 and isinstance(r.get("lambda_ms"), int)]
    report.info(f"lambda_ms of non-command requests: {stats(lambda_ms)}")
    commands = [r for r in records if r.get("intent") in ("OpenDoor", "CloseDoor")
                and r.get("result") in ("confirmed", "sent_unconfirmed")]
    confirm = [r["confirm_ms"] for r in commands if r.get("confirm_ms") is not None]
    unconfirmed = [r for r in commands if r.get("confirm_ms") is None]
    report.info(f"confirm_ms (Lambda start -> door in reported): {stats(confirm)}")
    report.result(
        "RNF3",
        f"commands confirmed within {MAX_END_TO_END_MS} ms: "
        f"{sum(1 for c in confirm if c <= MAX_END_TO_END_MS)}/{len(commands)} "
        f"(need >= {MIN_COMMANDS})",
        not unconfirmed and all(c <= MAX_END_TO_END_MS for c in confirm),
        enough=len(commands) >= MIN_COMMANDS,
    )
    errors = [r for r in records if r.get("result") == "error"]
    report.result("RF4-RF9", f"requests that ended in error: {len(errors)} (0)",
                  not errors)


def analyze_cross(events, records, report):
    report.title("RNF3 end-to-end with both clocks (NTP on the ESP32)")
    by_version = {}
    for index, event in enumerate(events):
        if event.name == "DELTA_RX" and event.utc_ms is not None:
            match = VERSION.search(event.details)
            if match:
                by_version[int(match.group(1))] = index
    rows = []
    for record in records:
        version = record.get("version")
        if version is None or version not in by_version:
            continue
        index = by_version[version]
        delta = events[index]
        done = next_event(events, index, ("ACTUATOR_DONE",), 3_000)
        sent = next_event(events, index, ("REPORT_TX",), 3_000)
        rows.append({
            "version": version,
            "cloud_ms": delta.utc_ms - record["desired_set_utc_ms"],
            "servo_ms": (done.utc_ms - record["start_utc_ms"])
            if done and done.utc_ms else None,
            "reported_ms": (sent.utc_ms - record["start_utc_ms"])
            if sent and sent.utc_ms else None,
            "confirm_ms": record.get("confirm_ms"),
        })
    if not rows:
        report.info("no command matched by version (needs both logs and NTP time)")
        return
    for row in rows[:LIST_LIMIT]:
        report.info(
            f"version={row['version']} UpdateThingShadow->DELTA_RX={row['cloud_ms']} ms "
            f"Lambda start->servo done={row['servo_ms']} ms "
            f"->REPORT_TX={row['reported_ms']} ms confirm_ms={row['confirm_ms']}"
        )
    report.info(f"cloud delivery ms: {stats([r['cloud_ms'] for r in rows])}")
    servo = [r["servo_ms"] for r in rows if r["servo_ms"] is not None]
    report.info(f"Lambda start -> servo done ms: {stats(servo)}")
    report.result(
        "RNF3",
        f"Lambda start -> servo done <= {MAX_END_TO_END_MS} ms: "
        f"{sum(1 for s in servo if s <= MAX_END_TO_END_MS)}/{len(servo)}",
        bool(servo) and all(s <= MAX_END_TO_END_MS for s in servo),
        enough=bool(servo),
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+")
    parser.add_argument("-o", "--output", help="also write the result here")
    arguments = parser.parse_args(argv)

    report = Report()
    device_logs, records = [], []
    for path in arguments.files:
        text = read_text(path)
        lambda_records = load_lambda(text, path)
        device_events = load_device(text)
        kind = "lambda" if lambda_records else "device" if device_events else "unknown"
        report.info(f"input {path}: {kind}")
        if device_events and not lambda_records:
            device_logs.append((path, device_events))
        records.extend(lambda_records)

    for path, events in device_logs:
        report.title(f"FILE {Path(path).name}")
        analyze_device(events, report)
    if records:
        analyze_lambda(records, report)
    for path, events in device_logs:
        if records:
            analyze_cross(events, records, report)

    output = report.text()
    sys.stdout.reconfigure(encoding="utf-8")
    print(output, end="")
    if arguments.output:
        Path(arguments.output).write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
