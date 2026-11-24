"""Cloud control rule C1 of SmartLoft: repeated gas alarms force auto mode.

Trigger: the IoT rule smartloft_control_rule, only for reports whose event is
gas_alarm_on. The rule sends:
    {"thingName": ..., "timestamp": <ms, AWS clock>, "reported": {...}}

C1 (technical guide 5.5 and 5.10): when a gas alarm starts while the
ventilation is in manual mode, count the gas_alarm_on events of the last
GAS_EVENTS_WINDOW_H hours. If there are GAS_EVENTS_LIMIT or more, write
desired.mode = auto with cmd_origin = cloud. The board applies it, and its
edge rule E1 opens the window if the gas is still high.

Race between rules: the data rule and this rule run in parallel on the same
message, so the current alarm may or may not be stored yet. Stored alarms are
counted by their (seq, deviceTs) pair, the current one is excluded and then
added once.

C1 fires again on purpose (guide V5): if the user goes back to manual and
another alarm arrives within the window, the count is still over the limit.

Every invocation ends with one JSON log line CONTROL_DECISION (evidence).
"""
import json
import logging
import os
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Deployment settings, from the Lambda environment variables.
TABLE_NAME = os.environ.get("TABLE_NAME", "smartloft-data")
EVENT_INDEX = os.environ.get("EVENT_INDEX", "event-index")
GAS_EVENTS_LIMIT = int(os.environ.get("GAS_EVENTS_LIMIT", "3"))
GAS_EVENTS_WINDOW_H = int(os.environ.get("GAS_EVENTS_WINDOW_H", "24"))
IOT_ENDPOINT = os.environ.get("IOT_ENDPOINT", "")  # e.g. xxxx-ats.iot.us-east-2.amazonaws.com
IOT_REGION = os.environ.get("IOT_REGION", "us-east-2")

MS_PER_HOUR = 3600 * 1000
VENT_SUFFIX = "-vent"
THING_PREFIX = "smartloft-"
EVENT_GAS_ALARM_ON = "gas_alarm_on"
MODE_MANUAL = "manual"
MODE_AUTO = "auto"
CMD_ORIGIN_CLOUD = "cloud"


class AlarmCounter:
    """Counts the stored gas_alarm_on events of a Thing in a time window."""

    def __init__(self, table):
        self._table = table

    def stored_alarms(self, thing_name, from_ms, to_ms):
        """Returns the set of distinct (seq, deviceTs) pairs in the window."""
        pairs = set()
        query = {
            "IndexName": EVENT_INDEX,
            # "timestamp" is a DynamoDB reserved word (guide V4): use #ts.
            "KeyConditionExpression": "eventKey = :key AND #ts BETWEEN :from AND :to",
            "ExpressionAttributeNames": {"#ts": "timestamp"},
            "ExpressionAttributeValues": {
                ":key": f"{thing_name}#{EVENT_GAS_ALARM_ON}",
                ":from": from_ms,
                ":to": to_ms,
            },
            "ProjectionExpression": "seq, deviceTs",
        }
        while True:
            page = self._table.query(**query)
            for item in page.get("Items", []):
                pairs.add((int(item["seq"]), int(item["deviceTs"])))
            last_key = page.get("LastEvaluatedKey")
            if not last_key:
                return pairs
            query["ExclusiveStartKey"] = last_key


class ShadowWriter:
    """Writes the desired section of a Thing Shadow."""

    def __init__(self, iot_data):
        self._iot_data = iot_data

    def force_auto(self, thing_name):
        payload = {"state": {"desired": {"mode": MODE_AUTO,
                                         "cmd_origin": CMD_ORIGIN_CLOUD}}}
        self._iot_data.update_thing_shadow(
            thingName=thing_name, payload=json.dumps(payload).encode("utf-8"))


class GasControl:
    """Applies C1 to one gas_alarm_on report; logs one JSON line."""

    def __init__(self, counter, writer, clock_ms):
        self._counter = counter
        self._writer = writer
        self._clock_ms = clock_ms

    def handle(self, payload):
        thing_name = payload.get("thingName", "")
        reported = payload.get("reported") or {}
        base = {"thingName": thing_name, "seq": reported.get("seq")}

        if not (thing_name.startswith(THING_PREFIX)
                and thing_name.endswith(VENT_SUFFIX)):
            return self._decide(base, action="none", reason="not_vent_thing")
        if reported.get("event") != EVENT_GAS_ALARM_ON:
            return self._decide(base, action="none", reason="not_gas_alarm_on")
        if reported.get("mode") != MODE_MANUAL:
            return self._decide(base, action="none", reason="auto_mode")

        now_ms = payload.get("timestamp") or self._clock_ms()
        from_ms = now_ms - GAS_EVENTS_WINDOW_H * MS_PER_HOUR
        stored = self._counter.stored_alarms(thing_name, from_ms, now_ms)
        current = (reported.get("seq"), reported.get("device_ts"))
        count = len(stored - {current}) + 1  # The current alarm counts once
        fields = dict(base, count=count, limit=GAS_EVENTS_LIMIT,
                      windowH=GAS_EVENTS_WINDOW_H)

        if count < GAS_EVENTS_LIMIT:
            return self._decide(fields, action="none", reason="below_limit")
        self._writer.force_auto(thing_name)
        return self._decide(fields, action="force_auto", reason="limit_reached")

    @staticmethod
    def _decide(fields, action, reason):
        logger.info(json.dumps({"log": "CONTROL_DECISION", "action": action,
                                "reason": reason, **fields}))
        return {"action": action, "reason": reason, "count": fields.get("count")}


def _now_ms():
    return int(time.time() * 1000)


_control = None


def _get_control():
    """Creates the AWS clients once per Lambda container."""
    global _control
    if _control is None:
        import boto3  # Provided by the Lambda runtime

        table = boto3.resource("dynamodb").Table(TABLE_NAME)
        endpoint = f"https://{IOT_ENDPOINT}" if IOT_ENDPOINT else None
        iot_data = boto3.client("iot-data", region_name=IOT_REGION,
                                endpoint_url=endpoint)
        _control = GasControl(AlarmCounter(table), ShadowWriter(iot_data), _now_ms)
    return _control


def lambda_handler(event, context):
    return _get_control().handle(event)
