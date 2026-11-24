"""Measures the P4 requirements from the Serial logs of the SmartLoft boards.

Usage, from the project root:
    python tools/analyze_log.py LOG [LOG ...] [options] [-o OUTPUT.txt]

LOG is a Serial log of board 1 (vent) or board 2 (lights) recorded with
tools/serial_logger.py; the board is detected from its reports. Every
section is printed; each result line starts with the requirement or test it
measures and ends with PASS, FAIL, NOT ENOUGH DATA or INFO.

Sections and tests:
    RNF1 stability ................ A11 (and the long run A08)
    RNF4 reporting and seq (V2) ... A08, B02
    RNF3 voice commands ........... A02 (lights), A03 (window)
    E1 / RNF7 edge response ....... A05
    C1 / RNF8 cloud response ...... A06 (board side)
    RNF5 / RNF9 offline ........... A09
    RNF2 PIR ...................... A12

Options:
    --from-ms / --to-ms   analyze only that part of the log (millis() of the
                          board), e.g. the 5 min without people of A12.
    --dynamo CSV          items exported from smartloft-data (Explore items ->
                          Download as CSV): integrity and storage latency per
                          Thing (A08), and which logged seq never got stored.

The P3 version of this script (door, SKILL_REQUEST) is kept at tag p3-final.
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

# Declared values (technical guide sections 5.8 and 9; Informe_P4 section 1.5).
MIN_STABLE_RUN_MS = 30 * 60_000   # A11: >= 30 min without restart
MAX_LOOP_MS = 500                 # RNF1: longest loop() while connected
MAX_HEAP_LOSS_BYTES = 4096        # RNF1: free heap, first vs. last HEALTH
MAX_REPORT_GAP_MS = 61_500        # RNF4: 60 s heartbeat + tolerance
MIN_REPORT_GAP_MS = 995           # RNF4: 1 s minimum between reports
MAX_PAYLOAD_BYTES = 1024          # V3: PAYLOAD_BUFFER_SIZE
MAX_VOICE_APPLY_MS = 1_500        # RNF3: DELTA_RX -> applied and reported
MAX_EDGE_RESPONSE_MS = 1_000      # RNF7: GAS_ALARM_ON -> ACTUATOR_DONE
MIN_EDGE_CYCLES = 10              # A05: smoke cycles
MAX_CLOUD_RESPONSE_MS = 5_000     # RNF8: gas_alarm_on report -> MODE_APPLIED
MAX_PENDING_APPLY_MS = 10_000     # RNF5: WIFI_CONNECTED -> pending applied
MAX_STORAGE_LATENCY_MS = 5_000    # A08: storedTs - deviceTs
MIN_INTEGRITY_PCT = 99.0          # A08: stored seq / expected seq
PIR_WARMUP_MS = 30_000            # config::pir::WARMUP_MS
PRESENCE_HOLD_MS = 10_000         # config::pir::PRESENCE_HOLD_MS
SEARCH_MS = 3_000                 # Window to find the reaction to a line
TOLERANCE_MS = 500                # Loop and logging delays

VENT_KEYS = ("gas_pct", "gas_mv", "gas_alarm", "warming_up", "window",
             "servo_angle", "mode", "gas_high_pct", "gas_low_pct")
LIGHTS_KEYS = ("light_kitchen", "light_living", "light_dining",
               "light_bathroom", "light_bedroom", "presence")
COMMON_KEYS = ("event", "origin", "seq", "device_ts")

DEVICE_LINE = re.compile(r"\[(\d+)\|([^\]]+)\]\s+(\S+)\s*(.*)")
KEY_VALUE = re.compile(r"(\w+)=([^\s{]+)")
REPORT_LINES = ("REPORT_TX", "LOCAL_REPORT")
MS_PER_MIN = 60_000
MS_PER_HOUR = 3_600_000
LIST_LIMIT = 25


@dataclass
class Event:
    """One line of a board log."""

    t_ms: int
    utc_ms: int | None
    name: str
    details: str
    line_no: int

    def fields(self):
        """key=value pairs of the details (before any JSON)."""
        head = self.details.split("{", 1)[0]
        return dict(KEY_VALUE.findall(head))

    def payload(self):
        """JSON object at the end of the details, or None."""
        start = self.details.find("{")
        if start < 0:
            return None
        try:
            return json.loads(self.details[start:])
        except json.JSONDecodeError:
            return None

    def reported(self):
        return ((self.payload() or {}).get("state") or {}).get("reported") or {}


class Report:
    """Collects result lines and prints them."""

    def __init__(self):
        self.lines = []

    def title(self, text):
        self.lines += ["", f"== {text} =="]

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


# ---------------------------------------------------------------- helpers

def parse_utc(text):
    if text in ("-", ""):
        return None
    try:
        return int(datetime.fromisoformat(text.replace("Z", "+00:00"))
                   .timestamp() * 1000)
    except ValueError:
        return None


def stats(values):
    """'n, min, median, mean, p95, max' of a list of numbers."""
    if not values:
        return "n=0"
    ordered = sorted(values)
    p95 = ordered[max(0, round(0.95 * len(ordered)) - 1)]
    return (f"n={len(ordered)} min={ordered[0]:.0f} "
            f"median={statistics.median(ordered):.0f} "
            f"mean={statistics.mean(ordered):.0f} p95={p95:.0f} "
            f"max={ordered[-1]:.0f}")


def read_text(path):
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-16", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def load_device(text, from_ms=None, to_ms=None):
    events = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = DEVICE_LINE.search(line)
        if not match:
            continue
        t_ms = int(match.group(1))
        if (from_ms is not None and t_ms < from_ms) or (
                to_ms is not None and t_ms > to_ms):
            continue
        events.append(Event(t_ms, parse_utc(match.group(2)), match.group(3),
                            match.group(4).strip(), number))
    return events


def next_event(events, index, names, limit_ms, predicate=None):
    """First later event in names within limit_ms, or None."""
    origin = events[index].t_ms
    for event in events[index + 1:]:
        if event.t_ms - origin > limit_ms or event.name == "BOOT":
            return None
        if event.name in names and (predicate is None or predicate(event)):
            return event
    return None


def segments(events):
    """Splits the log at each BOOT (a restart)."""
    parts, current = [], []
    for event in events:
        if event.name == "BOOT" and current:
            parts.append(current)
            current = []
        current.append(event)
    if current:
        parts.append(current)
    return parts


def offline_windows(events):
    """(lost_event, back_event or None) for each loss of the Shadow link."""
    windows, lost = [], None
    for event in events:
        if event.name in ("WIFI_LOST", "MQTT_LOST") and lost is None:
            lost = event
        elif event.name == "MQTT_CONNECTED" and lost is not None:
            windows.append((lost, event))
            lost = None
        elif event.name == "BOOT":
            lost = None
    if lost is not None:
        windows.append((lost, None))
    return windows


def report_lines(events):
    """Published reports. local_test prints each one twice (LOCAL_REPORT and
    REPORT_TX), so REPORT_TX is used whenever it is present."""
    tx = [e for e in events if e.name == "REPORT_TX"]
    return tx or [e for e in events if e.name == "LOCAL_REPORT"]


def detect_board(events):
    for event in events:
        if event.name in REPORT_LINES:
            keys = event.reported().keys()
            if "gas_pct" in keys:
                return "vent"
            if "light_kitchen" in keys:
                return "lights"
    return "unknown"


# ---------------------------------------------------------------- sections

def analyze_overview(events, board, report):
    span = events[-1].t_ms - events[0].t_ms
    boots = sum(1 for e in events if e.name == "BOOT")
    reasons = [e.fields().get("reason") for e in events if e.name == "RESET_REASON"]
    report.info(f"board={board} lines={len(events)} span={span / MS_PER_MIN:.1f} min "
                f"boots={boots} reset_reasons={reasons or '-'} "
                f"utc_clock={'yes' if any(e.utc_ms for e in events) else 'no'}")
    warnings = [e for e in events if e.name in (
        "JSON_ERROR", "INVALID_VALUE", "UPDATE_REJECTED", "REPORT_TX_FAILED",
        "REPORT_TOO_LARGE", "REPORT_EVENT_DROPPED", "CONSUMED_KEYS_FULL",
        "MQTT_CONNECT_FAILED", "MQTT_SUBSCRIBE_FAILED", "STALE_IGNORED",
        "GET_REJECTED", "COMMAND_REJECTED", "SETTINGS_SAVE_FAILED")]
    report.info(f"error/warning lines: {len(warnings)}")
    for event in warnings[:LIST_LIMIT]:
        report.info(f"  line {event.line_no} t={event.t_ms} {event.name} "
                    f"{event.details[:90]}")


def analyze_stability(events, report):
    report.title("RNF1 stability (A11)")
    longest = max(segments(events), key=lambda s: s[-1].t_ms - s[0].t_ms)
    run_ms = longest[-1].t_ms - longest[0].t_ms
    restarts = sum(1 for e in events if e.name == "BOOT") - (
        1 if events[0].name == "BOOT" else 0)
    report.result("RNF1", f"longest run without restart: {run_ms / MS_PER_MIN:.1f} "
                  f"min (>= {MIN_STABLE_RUN_MS / MS_PER_MIN:.0f})",
                  run_ms >= MIN_STABLE_RUN_MS)
    report.result("RNF1", f"restarts inside the log: {restarts} (0)", restarts == 0)
    health = [{k: int(v) for k, v in e.fields().items() if v.lstrip("-").isdigit()}
              for e in longest if e.name == "HEALTH"]
    if not health:
        report.result("RNF1", "HEALTH lines", False, enough=False)
        return
    max_loop = max(h.get("max_loop_ms", 0) for h in health)
    drops = health[-1].get("wifi_drops", 0) + health[-1].get("mqtt_drops", 0)
    heap_loss = health[0].get("heap", 0) - health[-1].get("heap", 0)
    rssi = [h["rssi"] for h in health if h.get("rssi")]
    report.info(f"HEALTH lines={len(health)} heap first/last={health[0].get('heap')}/"
                f"{health[-1].get('heap')} rssi {min(rssi, default=0)}.."
                f"{max(rssi, default=0)} dBm")
    report.result("RNF1", f"longest loop iteration: {max_loop} ms (<= {MAX_LOOP_MS})",
                  max_loop <= MAX_LOOP_MS)
    report.result("RNF1", f"WiFi + MQTT drops: {drops} (0)", drops == 0)
    report.result("RNF1", f"free heap loss: {heap_loss} bytes "
                  f"(<= {MAX_HEAP_LOSS_BYTES})", heap_loss <= MAX_HEAP_LOSS_BYTES)


def analyze_reporting(events, board, report):
    report.title("RNF4 reporting, V1 complete reports, V2 seq")
    reports = report_lines(events)
    failed = [e for e in events if e.name == "REPORT_TX_FAILED"]
    if not reports:
        report.result("RNF4", "report lines", False, enough=False)
        return
    by_event, by_origin = {}, {}
    for event in reports:
        values = event.reported()
        by_event[values.get("event")] = by_event.get(values.get("event"), 0) + 1
        by_origin[values.get("origin")] = by_origin.get(values.get("origin"), 0) + 1
    report.info(f"reports={len(reports)} failed={len(failed)} events={by_event}")
    report.info(f"origins={by_origin}")

    expected = COMMON_KEYS + (VENT_KEYS if board == "vent" else
                              LIGHTS_KEYS if board == "lights" else ())
    incomplete = [e for e in reports if not set(expected) <= set(e.reported())]
    report.result("V1", f"reports missing an attribute: {len(incomplete)} (0)",
                  not incomplete)
    largest = max(len(e.details[e.details.find("{"):]) for e in reports)
    report.result("V3", f"largest report: {largest} bytes (< {MAX_PAYLOAD_BYTES})",
                  largest < MAX_PAYLOAD_BYTES)

    gaps_ok, gaps_all = [], []
    offline = offline_windows(events)
    for previous, current in zip(reports, reports[1:]):
        gap = current.t_ms - previous.t_ms
        if gap < 0:
            continue  # A restart in between.
        gaps_all.append(gap)
        broken = any(lost.t_ms <= current.t_ms and (back is None or back.t_ms >= previous.t_ms)
                     for lost, back in offline)
        if not broken:
            gaps_ok.append(gap)
    report.info(f"gap between published reports ms: {stats(gaps_ok)}")
    report.result("RNF4", f"longest gap while connected: {max(gaps_ok, default=0)} ms "
                  f"(<= {MAX_REPORT_GAP_MS})",
                  bool(gaps_ok) and max(gaps_ok) <= MAX_REPORT_GAP_MS,
                  enough=bool(gaps_ok))
    report.result("RNF4", f"shortest gap: {min(gaps_all, default=0)} ms "
                  f"(>= {MIN_REPORT_GAP_MS})",
                  bool(gaps_all) and min(gaps_all) >= MIN_REPORT_GAP_MS,
                  enough=bool(gaps_all))

    for part in segments(events):
        sent = [int(e.fields().get("seq", e.reported().get("seq", -1)))
                for e in report_lines(part)]
        lost = [int(e.fields().get("seq", -1)) for e in part
                if e.name == "REPORT_TX_FAILED"]
        tried = sorted(set(sent + lost))
        if not tried:
            continue
        missing = sorted(set(range(tried[0], tried[-1] + 1)) - set(tried))
        report.result("V2", f"segment from line {part[0].line_no}: seq {tried[0]}.."
                      f"{tried[-1]}, published {len(sent)}, failed {len(lost)}, "
                      f"never attempted {len(missing)} (0)", not missing)
        if lost:
            report.info(f"  failed seq (lost, no buffer): {lost[:LIST_LIMIT]}")
    hours = (events[-1].t_ms - events[0].t_ms) / MS_PER_HOUR
    if hours > 0:
        per_day = len(reports) / hours * 24
        report.info(f"published: {len(reports) / hours:.0f}/h -> {per_day:.0f}/day "
                    f"-> {per_day * 30:.0f}/month (input for B04)")


def analyze_voice(events, board, report):
    report.title("RNF3 voice commands on the board (A02 lights / A03 window)")
    applied_names = ("LIGHT_APPLIED", "ACTUATOR_DONE", "MODE_APPLIED",
                     "THRESHOLDS_APPLIED", "COMMAND_REJECTED")
    rows = []
    for index, event in enumerate(events):
        if event.name != "DELTA_RX":
            continue
        if next_event(events, index, ("STALE_IGNORED",), 50):
            continue
        applied = next_event(events, index, applied_names, SEARCH_MS)
        if applied is None:
            continue
        if applied.name == "ACTUATOR_DONE":
            started = next_event(events, index, ("ACTUATOR_START",), SEARCH_MS)
            if started is None or "origin=edge" in started.details:
                continue  # Moved by rule E1, not by this command.
        sent = next_event(events, index, ("REPORT_TX",), SEARCH_MS,
                          lambda e: e.t_ms >= applied.t_ms)
        rows.append((event, applied, sent))
    if not rows:
        report.info("no DELTA_RX followed by an applied command")
        return
    for delta, applied, sent in rows[:LIST_LIMIT]:
        report.info(f"line {delta.line_no} {applied.name} {applied.details[:50]}: "
                    f"applied +{applied.t_ms - delta.t_ms} ms, reported "
                    f"+{(sent.t_ms - delta.t_ms) if sent else None} ms")
    for name in ("LIGHT_APPLIED", "ACTUATOR_DONE"):
        subset = [r for r in rows if r[1].name == name]
        if not subset:
            continue
        reported = [r[2].t_ms - r[0].t_ms for r in subset if r[2]]
        report.info(f"DELTA_RX -> {name} ms: "
                    f"{stats([r[1].t_ms - r[0].t_ms for r in subset])}")
        report.info(f"DELTA_RX -> report ms: {stats(reported)}")
        late = [v for v in reported if v > MAX_VOICE_APPLY_MS]
        report.result("RNF3", f"{name}: {len(subset)} commands reported within "
                      f"{MAX_VOICE_APPLY_MS} ms: {len(reported) - len(late)}/"
                      f"{len(subset)}", not late and len(reported) == len(subset))
    rejected = [r for r in rows if r[1].name == "COMMAND_REJECTED"]
    if rejected:
        reasons = {}
        for row in rejected:
            reason = row[1].fields().get("reason")
            reasons[reason] = reasons.get(reason, 0) + 1
        report.info(f"rejected commands by reason: {reasons}")


def analyze_edge(events, report):
    report.title("E1 / E2 / RNF7 edge response (A05)")
    ready = next((e for e in events if e.name == "GAS_READY"), None)
    alarms = [e for e in events if e.name in ("GAS_ALARM_ON", "GAS_ALARM_OFF")]
    first_sample = next((e for e in events if e.name == "GAS_SAMPLE"), None)
    warm_at_start = (ready is None and first_sample is not None
                     and first_sample.fields().get("warming_up") == "0")
    if ready:
        report.info(f"GAS_READY at t={ready.t_ms} ms ({ready.t_ms / 1000:.0f} s after boot)")
    elif warm_at_start:
        report.info("warm-up ended before this log started (first GAS_SAMPLE has "
                    "warming_up=0)")
    early = [] if warm_at_start else [
        e for e in alarms if ready is None or e.t_ms < ready.t_ms]
    report.result("E2", f"alarms during warm-up: {len(early)} (0)", not early,
                  enough=ready is not None or warm_at_start)

    wrong = []
    for event in alarms:
        fields = event.fields()
        pct = float(fields.get("gas_pct", "nan"))
        if event.name == "GAS_ALARM_ON" and not pct >= float(fields.get("gas_high_pct", 0)):
            wrong.append(event)
        if event.name == "GAS_ALARM_OFF" and not pct <= float(fields.get("gas_low_pct", 100)):
            wrong.append(event)
    report.result("E1", f"alarm changes outside the thresholds: {len(wrong)}/"
                  f"{len(alarms)} (0)", not wrong, enough=bool(alarms))

    responses = {"open": [], "closed": []}
    missing = []
    for index, event in enumerate(events):
        if event.name not in ("GAS_ALARM_ON", "GAS_ALARM_OFF"):
            continue
        if event.fields().get("mode") != "auto":
            continue
        target = "open" if event.name == "GAS_ALARM_ON" else "closed"
        done = next_event(events, index, ("ACTUATOR_DONE",), SEARCH_MS,
                          lambda e, t=target: f"window={t}" in e.details)
        if done is None:
            missing.append(event)
        else:
            responses[target].append(done.t_ms - event.t_ms)
    all_ms = responses["open"] + responses["closed"]
    report.info(f"GAS_ALARM_ON -> ACTUATOR_DONE open ms: {stats(responses['open'])}")
    report.info(f"GAS_ALARM_OFF -> ACTUATOR_DONE closed ms: {stats(responses['closed'])}")
    report.result("RNF7", f"edge response max {max(all_ms, default=0)} ms "
                  f"(<= {MAX_EDGE_RESPONSE_MS}), alarms without window move: "
                  f"{len(missing)}",
                  bool(all_ms) and max(all_ms) <= MAX_EDGE_RESPONSE_MS and not missing,
                  enough=bool(all_ms))
    report.result("A05", f"smoke cycles in auto: {len(responses['open'])} "
                  f"(>= {MIN_EDGE_CYCLES})", len(responses["open"]) >= MIN_EDGE_CYCLES)


def analyze_cloud(events, report):
    report.title("C1 / RNF8 cloud response seen from board 1 (A06)")
    rows = []
    for index, event in enumerate(events):
        if event.name != "REPORT_TX":
            continue
        values = event.reported()
        if values.get("event") != "gas_alarm_on" or values.get("mode") != "manual":
            continue
        delta = next_event(events, index, ("DELTA_RX",), MAX_CLOUD_RESPONSE_MS * 2,
                           lambda e: '"mode":"auto"' in e.details.replace(" ", ""))
        applied = next_event(events, index, ("MODE_APPLIED",),
                             MAX_CLOUD_RESPONSE_MS * 2,
                             lambda e: "origin=cloud" in e.details)
        rows.append((event, delta, applied))
    if not rows:
        report.info("no gas_alarm_on report in manual mode")
        return
    totals = []
    for sent, delta, applied in rows[:LIST_LIMIT]:
        total = applied.t_ms - sent.t_ms if applied else None
        if total is not None:
            totals.append(total)
        report.info(f"line {sent.line_no} seq={sent.reported().get('seq')}: "
                    f"REPORT_TX -> DELTA_RX "
                    f"{(delta.t_ms - sent.t_ms) if delta else None} ms -> "
                    f"MODE_APPLIED {total} ms"
                    + ("" if applied else " (no change: fewer than the limit)"))
    report.info(f"gas_alarm_on -> MODE_APPLIED origin=cloud ms: {stats(totals)}")
    report.result("RNF8", f"cloud response max {max(totals, default=0)} ms "
                  f"(<= {MAX_CLOUD_RESPONSE_MS})",
                  bool(totals) and max(totals) <= MAX_CLOUD_RESPONSE_MS,
                  enough=bool(totals))


def analyze_offline(events, report):
    report.title("RNF9 offline operation / RNF5 reconnection (A09)")
    windows = offline_windows(events)
    if not windows:
        report.info("no WIFI_LOST or MQTT_LOST in this log")
        return
    for lost, back in windows:
        end = back.t_ms if back else events[-1].t_ms
        inside = [e for e in events if lost.t_ms <= e.t_ms <= end]
        edge = [e for e in inside if e.name == "EDGE_ACTION"]
        alarms = [e for e in inside if e.name.startswith("GAS_ALARM")]
        failed = [int(e.fields().get("seq", -1)) for e in inside
                  if e.name == "REPORT_TX_FAILED"]
        report.info(f"{lost.name} line {lost.line_no}: offline "
                    f"{(end - lost.t_ms) / 1000:.1f} s{'' if back else ' (log ends)'}; "
                    f"alarms={len(alarms)} edge actions={len(edge)} "
                    f"lost seq={failed[:LIST_LIMIT]}")
        if alarms:
            report.result("RNF9", "rule E1 acted while offline: "
                          f"{len(edge)} window moves for {len(alarms)} alarm changes",
                          bool(edge))
        if back is None:
            continue
        index = events.index(back)
        wifi = next((e for e in reversed(events[:index + 1])
                     if e.name == "WIFI_CONNECTED" and e.t_ms >= lost.t_ms), back)
        got = next_event(events, index, ("GET_RX",), MAX_PENDING_APPLY_MS)
        applied = next_event(
            events, events.index(wifi),
            ("ACTUATOR_DONE", "LIGHT_APPLIED", "MODE_APPLIED", "THRESHOLDS_APPLIED"),
            MAX_PENDING_APPLY_MS * 2,
            lambda e: "origin=edge" not in e.details)
        report.info(f"  WIFI_CONNECTED t={wifi.t_ms} -> MQTT_CONNECTED "
                    f"+{back.t_ms - wifi.t_ms} ms -> GET_RX "
                    f"+{(got.t_ms - wifi.t_ms) if got else None} ms")
        if applied:
            total = applied.t_ms - wifi.t_ms
            report.result("RNF5", f"pending command applied: {applied.name} "
                          f"{applied.details[:40]} {total} ms after WIFI_CONNECTED "
                          f"(<= {MAX_PENDING_APPLY_MS})", total <= MAX_PENDING_APPLY_MS)
        else:
            report.result("RNF5", "no pending command applied after reconnecting", None)


def analyze_presence(events, report):
    report.title("RNF2 PIR (A12)")
    ready = next((e for e in events if e.name == "PIR_READY"), None)
    detected = [e for e in events if e.name == "PRESENCE_DETECTED"]
    cleared = [e for e in events if e.name == "PRESENCE_CLEARED"]
    report.info(f"PRESENCE_DETECTED={len(detected)} PRESENCE_CLEARED={len(cleared)} "
                "(compare with the passes counted on video)")
    if ready:
        early = [e for e in detected if e.t_ms < ready.t_ms]
        report.result("RNF2", f"PIR_READY at {ready.t_ms} ms (>= "
                      f"{PIR_WARMUP_MS - TOLERANCE_MS}); detections before: "
                      f"{len(early)} (0)",
                      not early and ready.t_ms >= PIR_WARMUP_MS - TOLERANCE_MS)
    durations = []
    for on in detected:
        off = next((e for e in cleared if e.t_ms > on.t_ms), None)
        if off:
            durations.append(off.t_ms - on.t_ms)
    short = [d for d in durations if d < PRESENCE_HOLD_MS - TOLERANCE_MS]
    report.info(f"presence episodes ms: {stats(durations)}")
    report.result("RNF2", f"episodes shorter than the {PRESENCE_HOLD_MS} ms hold: "
                  f"{len(short)} (0)", not short, enough=bool(durations))


# ---------------------------------------------------------------- DynamoDB

def load_dynamo(path):
    """Rows of a DynamoDB console CSV; 'name (N)' headers become 'name'."""
    rows = []
    for row in csv.DictReader(io.StringIO(read_text(path))):
        clean = {}
        for key, value in row.items():
            if key is None:
                continue
            name = re.sub(r"\s*\([A-Z]+\)\s*$", "", key.strip())
            clean[name] = (value or "").strip().strip('"')
        rows.append(clean)
    return rows


def number(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def analyze_dynamo(rows, device_logs, report):
    report.title("A08 storage integrity and latency (DynamoDB export)")
    by_thing = {}
    for row in rows:
        by_thing.setdefault(row.get("thingName"), []).append(row)
    for thing, items in sorted(by_thing.items(), key=lambda kv: str(kv[0])):
        seqs = sorted({s for s in (number(i.get("seq")) for i in items) if s is not None})
        if not seqs:
            continue
        expected = seqs[-1] - seqs[0] + 1
        integrity = 100.0 * len(seqs) / expected
        report.result("A08", f"{thing}: {len(seqs)} distinct seq stored of {expected} "
                      f"({seqs[0]}..{seqs[-1]}) = {integrity:.2f} % "
                      f"(>= {MIN_INTEGRITY_PCT})", integrity >= MIN_INTEGRITY_PCT)
        missing = sorted(set(range(seqs[0], seqs[-1] + 1)) - set(seqs))
        if missing:
            report.info(f"  seq not stored: {missing[:LIST_LIMIT]}")

        device_ms, aws_ms, negative = [], [], 0
        for item in items:
            stored, device, rule = (number(item.get(k)) for k in
                                    ("storedTs", "deviceTs", "timestamp"))
            if stored and device:
                if stored - device < 0:
                    negative += 1
                device_ms.append(stored - device)
            if stored and rule:
                aws_ms.append(stored - rule)
        report.info(f"  storedTs - deviceTs ms (board NTP vs AWS): {stats(device_ms)}; "
                    f"negative={negative}")
        report.info(f"  storedTs - timestamp ms (AWS clock only): {stats(aws_ms)}")
        report.result("A08", f"{thing}: storage latency max "
                      f"{max(device_ms, default=0)} ms (<= {MAX_STORAGE_LATENCY_MS}), "
                      f"negative values {negative} (0)",
                      bool(device_ms) and max(device_ms) <= MAX_STORAGE_LATENCY_MS
                      and negative == 0, enough=bool(device_ms))

    for path, events, board in device_logs:
        thing_rows = [r for r in rows if str(r.get("thingName", "")).endswith(f"-{board}")]
        stored = {number(r.get("seq")) for r in thing_rows}
        published = [int(e.fields().get("seq", -1)) for e in events
                     if e.name == "REPORT_TX"]
        lost = [s for s in published if s not in stored]
        if published:
            report.result("A08", f"{Path(path).name}: REPORT_TX seq not in DynamoDB: "
                          f"{len(lost)}/{len(published)}", not lost)
            if lost:
                report.info(f"  published but not stored: {lost[:LIST_LIMIT]}")


# ---------------------------------------------------------------- main

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="+", help="Serial logs of the boards")
    parser.add_argument("--from-ms", type=int)
    parser.add_argument("--to-ms", type=int)
    parser.add_argument("--dynamo", help="CSV export of smartloft-data")
    parser.add_argument("-o", "--output", help="also write the result here")
    arguments = parser.parse_args(argv)

    report = Report()
    device_logs = []
    for path in arguments.files:
        events = load_device(read_text(path), arguments.from_ms, arguments.to_ms)
        report.title(f"FILE {Path(path).name}")
        if not events:
            report.info("no device lines found")
            continue
        board = detect_board(events)
        device_logs.append((path, events, board))
        analyze_overview(events, board, report)
        analyze_stability(events, report)
        analyze_reporting(events, board, report)
        analyze_voice(events, board, report)
        if board == "vent":
            analyze_edge(events, report)
            analyze_cloud(events, report)
        if board == "lights":
            analyze_presence(events, report)
        analyze_offline(events, report)

    if arguments.dynamo:
        analyze_dynamo(load_dynamo(arguments.dynamo), device_logs, report)

    output = report.text()
    sys.stdout.reconfigure(encoding="utf-8")
    print(output, end="")
    if arguments.output:
        Path(arguments.output).write_text(output, encoding="utf-8")


if __name__ == "__main__":
    main()
