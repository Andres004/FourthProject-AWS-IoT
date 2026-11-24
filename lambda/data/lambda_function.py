"""Storage backend of SmartLoft: validates each Shadow report and saves it.

Trigger: the IoT rule smartloft_data_rule, on every accepted Shadow update
that carries a "reported" section. The rule sends:
    {"thingName": ..., "timestamp": <ms, AWS clock>, "thingType": ...,
     "serialNumber": ..., "place": ..., "reported": {...}}

Steps (technical guide 5.10, RF11 and RF12):
  1. Validate: every attribute of the board must be present and in range.
     An invalid report is NOT stored; DATA_DISCARDED logs the reason.
  2. Classify: heartbeat and gas_changed are readings; the rest are events.
     Only events get "eventKey", so the GSI event-index holds only events.
  3. Enrich: thing type, serial number, place, storedTs and the TTL.
  4. PutItem into smartloft-data.

Every invocation ends with one JSON log line in CloudWatch (evidence).
"""
import json
import logging
import os
import re
import time
from decimal import Decimal

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Deployment settings, from the Lambda environment variables.
TABLE_NAME = os.environ.get("TABLE_NAME", "smartloft-data")
READING_TTL_DAYS = int(os.environ.get("READING_TTL_DAYS", "30"))
EVENT_TTL_DAYS = int(os.environ.get("EVENT_TTL_DAYS", "365"))

SECONDS_PER_DAY = 86400
MS_PER_SECOND = 1000

# Thing name contract: smartloft-<six-digit home code>-<place>.
THING_NAME_PATTERN = re.compile(r"^(smartloft)-(\d{6})-(vent|lights)$")
PLACE_VENT = "vent"
PLACE_LIGHTS = "lights"

# Shared report attributes (include/config_common.h).
ORIGINS = {"voice", "cloud", "edge", "boot"}
COMMON_EVENTS = {"boot", "heartbeat"}
READING_EVENTS = {"heartbeat", "gas_changed"}  # Everything else is an event

# Board 1 (-vent) contract (include/config_vent.h, technical guide 5.3).
VENT_EVENTS = COMMON_EVENTS | {
    "gas_changed", "gas_alarm_on", "gas_alarm_off",
    "window_changed", "mode_changed", "thresholds_changed",
}
GAS_PCT_MIN, GAS_PCT_MAX = 0.0, 100.0  # Relative index [% of MQ-2 supply]
# AO voltage rebuilt through the 0.6 divider: the ADC saturates near 3300 mV
# on the pin, so the highest value the board can report is 3300 / 0.6 = 5500.
GAS_MV_MIN, GAS_MV_MAX = 0, 5500       # [mV]
SERVO_ANGLE_MIN, SERVO_ANGLE_MAX = 0, 180  # SG90 range [deg]
THRESHOLD_MIN, THRESHOLD_MAX = 1, 99   # gas_high_pct / gas_low_pct [%]
WINDOW_STATES = {"open", "closed"}
MODES = {"auto", "manual"}

# Board 2 (-lights) contract (include/config_lights.h, technical guide 5.4).
LIGHTS_EVENTS = COMMON_EVENTS | {
    "light_changed", "presence_detected", "presence_cleared",
}
LIGHT_STATES = {"on", "off"}
# Shadow attribute -> item attribute, one per zone.
LIGHT_ATTRIBUTES = {
    "light_kitchen": "lightKitchen",
    "light_living": "lightLiving",
    "light_dining": "lightDining",
    "light_bathroom": "lightBathroom",
    "light_bedroom": "lightBedroom",
}


class InvalidReport(Exception):
    """The report breaks the Shadow contract; the reason is the message."""


def _is_int(value):
    """True for JSON integers (bool is excluded, although it subclasses int)."""
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    return _is_int(value) or isinstance(value, float)


class ReportValidator:
    """Checks one rule payload against the Shadow contract of its board."""

    def validate(self, payload):
        """Returns (thing_parts, reported) or raises InvalidReport."""
        if not isinstance(payload, dict):
            raise InvalidReport("payload_not_object")
        thing_name = payload.get("thingName")
        match = THING_NAME_PATTERN.match(thing_name or "")
        if not match:
            raise InvalidReport("bad_thing_name")
        timestamp = payload.get("timestamp")
        if not _is_int(timestamp) or timestamp <= 0:
            raise InvalidReport("bad_timestamp")
        reported = payload.get("reported")
        if not isinstance(reported, dict):
            raise InvalidReport("missing_reported")

        thing_type, serial_number, place = match.groups()
        self._check_common(reported, VENT_EVENTS if place == PLACE_VENT else LIGHTS_EVENTS)
        if place == PLACE_VENT:
            self._check_vent(reported)
        else:
            self._check_lights(reported)
        return (thing_name, thing_type, serial_number, place), reported

    @staticmethod
    def _require(reported, key):
        if key not in reported:
            raise InvalidReport(f"missing_{key}")
        return reported[key]

    def _check_int(self, reported, key, low, high):
        value = self._require(reported, key)
        if not _is_int(value) or not low <= value <= high:
            raise InvalidReport(f"bad_{key}")

    def _check_in(self, reported, key, allowed):
        if self._require(reported, key) not in allowed:
            raise InvalidReport(f"bad_{key}")

    def _check_bool(self, reported, key):
        if not isinstance(self._require(reported, key), bool):
            raise InvalidReport(f"bad_{key}")

    def _check_common(self, reported, events):
        self._check_in(reported, "event", events)
        self._check_in(reported, "origin", ORIGINS)
        for key in ("seq", "device_ts"):
            value = self._require(reported, key)
            if not _is_int(value) or value < 0:
                raise InvalidReport(f"bad_{key}")

    def _check_vent(self, reported):
        gas_pct = self._require(reported, "gas_pct")
        if not _is_number(gas_pct) or not GAS_PCT_MIN <= gas_pct <= GAS_PCT_MAX:
            raise InvalidReport("bad_gas_pct")
        self._check_int(reported, "gas_mv", GAS_MV_MIN, GAS_MV_MAX)
        self._check_bool(reported, "gas_alarm")
        self._check_bool(reported, "warming_up")
        self._check_in(reported, "window", WINDOW_STATES)
        self._check_int(reported, "servo_angle", SERVO_ANGLE_MIN, SERVO_ANGLE_MAX)
        self._check_in(reported, "mode", MODES)
        self._check_int(reported, "gas_high_pct", THRESHOLD_MIN, THRESHOLD_MAX)
        self._check_int(reported, "gas_low_pct", THRESHOLD_MIN, THRESHOLD_MAX)
        if reported["gas_low_pct"] >= reported["gas_high_pct"]:
            raise InvalidReport("low_not_below_high")

    def _check_lights(self, reported):
        for key in LIGHT_ATTRIBUTES:
            self._check_in(reported, key, LIGHT_STATES)
        self._check_bool(reported, "presence")


class ItemBuilder:
    """Turns a validated report into a smartloft-data item (guide 5.11)."""

    def build(self, thing_parts, timestamp, reported, stored_ms):
        thing_name, thing_type, serial_number, place = thing_parts
        event = reported["event"]
        is_reading = event in READING_EVENTS
        ttl_days = READING_TTL_DAYS if is_reading else EVENT_TTL_DAYS
        item = {
            "thingName": thing_name,
            "timestamp": timestamp,
            "thingType": thing_type,
            "serialNumber": serial_number,
            "place": place,
            "recordType": "reading" if is_reading else "event",
            "event": event,
            "origin": reported["origin"],
            "seq": reported["seq"],
            "deviceTs": reported["device_ts"],
            "storedTs": stored_ms,
            "expiresAt": stored_ms // MS_PER_SECOND + ttl_days * SECONDS_PER_DAY,
        }
        if not is_reading:
            item["eventKey"] = f"{thing_name}#{event}"  # Sparse GSI key
        if place == PLACE_VENT:
            item.update({
                # boto3 rejects float: numbers with decimals go as Decimal.
                "gasPct": Decimal(str(reported["gas_pct"])),
                "gasMv": reported["gas_mv"],
                "gasAlarm": reported["gas_alarm"],
                "warmingUp": reported["warming_up"],
                "window": reported["window"],
                "servoAngle": reported["servo_angle"],
                "mode": reported["mode"],
                "gasHighPct": reported["gas_high_pct"],
                "gasLowPct": reported["gas_low_pct"],
            })
        else:
            for shadow_key, item_key in LIGHT_ATTRIBUTES.items():
                item[item_key] = reported[shadow_key]
            item["presence"] = reported["presence"]
        return item


class DataRecorder:
    """Validates, builds and stores one report; logs one JSON line."""

    def __init__(self, table, clock_ms):
        self._table = table
        self._clock_ms = clock_ms
        self._validator = ReportValidator()
        self._builder = ItemBuilder()

    def record(self, payload):
        try:
            thing_parts, reported = self._validator.validate(payload)
        except InvalidReport as error:
            self._log("DATA_DISCARDED", reason=str(error),
                      thingName=_safe_get(payload, "thingName"),
                      event=_safe_get(_safe_get(payload, "reported"), "event"))
            return {"status": "discarded", "reason": str(error)}

        stored_ms = self._clock_ms()
        timestamp = payload["timestamp"]
        item = self._builder.build(thing_parts, timestamp, reported, stored_ms)
        self._table.put_item(Item=item)
        device_ts = reported["device_ts"]
        self._log(
            "DATA_STORED",
            thingName=item["thingName"],
            recordType=item["recordType"],
            event=item["event"],
            origin=item["origin"],
            seq=item["seq"],
            timestamp=timestamp,
            # Storage latency: AWS clock only, and board clock (NTP) vs AWS.
            ruleToStoreMs=stored_ms - timestamp,
            deviceToStoreMs=stored_ms - device_ts if device_ts else None,
        )
        return {"status": "stored", "recordType": item["recordType"]}

    @staticmethod
    def _log(kind, **fields):
        logger.info(json.dumps({"log": kind, **fields}))


def _safe_get(value, key):
    return value.get(key) if isinstance(value, dict) else None


def _now_ms():
    return int(time.time() * MS_PER_SECOND)


_recorder = None


def _get_recorder():
    """Creates the DynamoDB table handle once per Lambda container."""
    global _recorder
    if _recorder is None:
        import boto3  # Provided by the Lambda runtime

        table = boto3.resource("dynamodb").Table(TABLE_NAME)
        _recorder = DataRecorder(table, _now_ms)
    return _recorder


def lambda_handler(event, context):
    return _get_recorder().record(event)
