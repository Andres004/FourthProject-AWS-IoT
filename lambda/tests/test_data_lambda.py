"""Unit tests of smartloft_data_lambda, without AWS.

The DynamoDB table is an in-memory fake and the clock is fixed. Every test
name starts with the requirement it verifies.

Usage, from the project root:
    python -m unittest discover -s lambda/tests -v
"""
import copy
import importlib.util
import json
import logging
import unittest
from decimal import Decimal
from pathlib import Path

# Each Lambda has its own lambda_function.py, so load this one by path under
# a unique module name.
_SOURCE = Path(__file__).resolve().parents[1] / "data" / "lambda_function.py"
_SPEC = importlib.util.spec_from_file_location("data_lambda_function", _SOURCE)
data_lambda = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(data_lambda)

RULE_TS_MS = 1795862400567    # timestamp() of the rule (AWS clock)
STORED_MS = 1795862400890     # Lambda clock when storing
DEVICE_TS_MS = 1795862400123  # Board clock (NTP) when publishing
SECONDS_PER_DAY = 86400


class FakeTable:
    """Keeps the items passed to put_item."""

    def __init__(self):
        self.items = []

    def put_item(self, Item):
        self.items.append(Item)


def vent_payload(**reported_changes):
    reported = {
        "gas_pct": 8.4, "gas_mv": 420, "gas_alarm": False, "warming_up": False,
        "window": "closed", "servo_angle": 0,
        "mode": "auto", "gas_high_pct": 15, "gas_low_pct": 8,
        "event": "heartbeat", "origin": "boot", "seq": 1532,
        "device_ts": DEVICE_TS_MS,
    }
    reported.update(reported_changes)
    return {
        "thingName": "smartloft-739264-vent",
        "timestamp": RULE_TS_MS,
        "thingType": "smartloft",
        "serialNumber": "739264",
        "place": "vent",
        "reported": reported,
    }


def lights_payload(**reported_changes):
    reported = {
        "light_kitchen": "on", "light_living": "off", "light_dining": "off",
        "light_bathroom": "off", "light_bedroom": "off",
        "presence": False,
        "event": "light_changed", "origin": "voice", "seq": 812,
        "device_ts": DEVICE_TS_MS,
    }
    reported.update(reported_changes)
    return {
        "thingName": "smartloft-739264-lights",
        "timestamp": RULE_TS_MS,
        "thingType": "smartloft",
        "serialNumber": "739264",
        "place": "lights",
        "reported": reported,
    }


class DataLambdaTest(unittest.TestCase):

    def setUp(self):
        self.table = FakeTable()
        self.recorder = data_lambda.DataRecorder(self.table, lambda: STORED_MS)

    def record(self, payload):
        with self.assertLogs(data_lambda.logger, logging.INFO) as logs:
            result = self.recorder.record(payload)
        self.log_line = json.loads(logs.records[-1].getMessage())
        return result

    def assert_discarded(self, payload, reason):
        result = self.record(payload)
        self.assertEqual(result, {"status": "discarded", "reason": reason})
        self.assertEqual(self.table.items, [])
        self.assertEqual(self.log_line["log"], "DATA_DISCARDED")
        self.assertEqual(self.log_line["reason"], reason)

    # --- RF11: valid reports are enriched and stored ---------------------

    def test_rf11_vent_heartbeat_is_stored_as_reading(self):
        result = self.record(vent_payload())

        self.assertEqual(result, {"status": "stored", "recordType": "reading"})
        item = self.table.items[0]
        self.assertEqual(item["thingName"], "smartloft-739264-vent")
        self.assertEqual(item["timestamp"], RULE_TS_MS)
        self.assertEqual(item["thingType"], "smartloft")
        self.assertEqual(item["serialNumber"], "739264")
        self.assertEqual(item["place"], "vent")
        self.assertEqual(item["recordType"], "reading")
        self.assertNotIn("eventKey", item)  # Readings stay out of the GSI
        self.assertEqual(item["gasPct"], Decimal("8.4"))
        self.assertEqual(item["gasMv"], 420)
        self.assertIs(item["gasAlarm"], False)
        self.assertEqual(item["mode"], "auto")
        self.assertEqual(item["gasHighPct"], 15)
        self.assertEqual(item["gasLowPct"], 8)
        self.assertEqual(item["seq"], 1532)
        self.assertEqual(item["deviceTs"], DEVICE_TS_MS)
        self.assertEqual(item["storedTs"], STORED_MS)

    def test_rf11_gas_changed_is_a_reading(self):
        self.record(vent_payload(event="gas_changed"))
        self.assertEqual(self.table.items[0]["recordType"], "reading")

    def test_rf11_reading_ttl_is_30_days(self):
        self.record(vent_payload())
        expected = STORED_MS // 1000 + data_lambda.READING_TTL_DAYS * SECONDS_PER_DAY
        self.assertEqual(data_lambda.READING_TTL_DAYS, 30)
        self.assertEqual(self.table.items[0]["expiresAt"], expected)

    def test_rf11_event_ttl_is_365_days(self):
        self.record(vent_payload(event="gas_alarm_on", gas_alarm=True, origin="edge"))
        expected = STORED_MS // 1000 + data_lambda.EVENT_TTL_DAYS * SECONDS_PER_DAY
        self.assertEqual(data_lambda.EVENT_TTL_DAYS, 365)
        self.assertEqual(self.table.items[0]["expiresAt"], expected)

    def test_rf11_lights_report_is_stored_with_every_zone(self):
        result = self.record(lights_payload())

        self.assertEqual(result, {"status": "stored", "recordType": "event"})
        item = self.table.items[0]
        self.assertEqual(item["place"], "lights")
        self.assertEqual(item["lightKitchen"], "on")
        self.assertEqual(item["lightLiving"], "off")
        self.assertEqual(item["lightDining"], "off")
        self.assertEqual(item["lightBathroom"], "off")
        self.assertEqual(item["lightBedroom"], "off")
        self.assertIs(item["presence"], False)
        self.assertNotIn("gasPct", item)

    def test_rf11_device_ts_zero_is_accepted_without_ntp(self):
        result = self.record(vent_payload(device_ts=0))
        self.assertEqual(result["status"], "stored")
        self.assertIsNone(self.log_line["deviceToStoreMs"])

    def test_rf11_stored_log_has_latencies(self):
        self.record(vent_payload())
        self.assertEqual(self.log_line["log"], "DATA_STORED")
        self.assertEqual(self.log_line["ruleToStoreMs"], STORED_MS - RULE_TS_MS)
        self.assertEqual(self.log_line["deviceToStoreMs"], STORED_MS - DEVICE_TS_MS)
        self.assertEqual(self.log_line["seq"], 1532)

    def test_rf11_gas_pct_limits_are_inclusive(self):
        self.record(vent_payload(gas_pct=0))
        self.record(vent_payload(gas_pct=100.0, gas_mv=5500))
        self.assertEqual(len(self.table.items), 2)

    # --- RF12: actuator events keep their origin ------------------------

    def test_rf12_window_event_keeps_origin_and_event_key(self):
        self.record(vent_payload(event="window_changed", window="open",
                                 servo_angle=90, mode="manual", origin="voice"))
        item = self.table.items[0]
        self.assertEqual(item["recordType"], "event")
        self.assertEqual(item["origin"], "voice")
        self.assertEqual(item["window"], "open")
        self.assertEqual(item["eventKey"], "smartloft-739264-vent#window_changed")

    def test_rf12_cloud_mode_change_is_an_event(self):
        self.record(vent_payload(event="mode_changed", origin="cloud"))
        item = self.table.items[0]
        self.assertEqual(item["origin"], "cloud")
        self.assertEqual(item["eventKey"], "smartloft-739264-vent#mode_changed")

    def test_rf12_gas_alarm_event_key_feeds_c1(self):
        self.record(vent_payload(event="gas_alarm_on", gas_alarm=True, origin="edge"))
        self.assertEqual(self.table.items[0]["eventKey"],
                         "smartloft-739264-vent#gas_alarm_on")

    def test_rf12_presence_event_key(self):
        self.record(lights_payload(event="presence_detected", presence=True,
                                   origin="boot"))
        self.assertEqual(self.table.items[0]["eventKey"],
                         "smartloft-739264-lights#presence_detected")

    # --- RF11: invalid reports are discarded with a reason --------------

    def test_rf11_discards_foreign_thing(self):
        payload = vent_payload()
        payload["thingName"] = "monoambiente-739264"
        self.assert_discarded(payload, "bad_thing_name")

    def test_rf11_discards_unknown_place(self):
        payload = vent_payload()
        payload["thingName"] = "smartloft-739264-garage"
        self.assert_discarded(payload, "bad_thing_name")

    def test_rf11_discards_missing_timestamp(self):
        payload = vent_payload()
        del payload["timestamp"]
        self.assert_discarded(payload, "bad_timestamp")

    def test_rf11_discards_missing_reported(self):
        payload = vent_payload()
        del payload["reported"]
        self.assert_discarded(payload, "missing_reported")

    def test_rf11_discards_incomplete_vent_report(self):
        payload = vent_payload()
        del payload["reported"]["gas_low_pct"]
        self.assert_discarded(payload, "missing_gas_low_pct")

    def test_rf11_discards_incomplete_lights_report(self):
        payload = lights_payload()
        del payload["reported"]["light_bedroom"]
        self.assert_discarded(payload, "missing_light_bedroom")

    def test_rf11_discards_gas_pct_out_of_range(self):
        self.assert_discarded(vent_payload(gas_pct=100.1), "bad_gas_pct")
        self.assert_discarded(vent_payload(gas_pct=-0.1), "bad_gas_pct")

    def test_rf11_discards_gas_pct_as_text(self):
        self.assert_discarded(vent_payload(gas_pct="8.4"), "bad_gas_pct")

    def test_rf11_discards_gas_mv_out_of_range(self):
        self.assert_discarded(vent_payload(gas_mv=5501), "bad_gas_mv")

    def test_rf11_discards_bool_as_number(self):
        self.assert_discarded(vent_payload(seq=True), "bad_seq")

    def test_rf11_discards_negative_seq(self):
        self.assert_discarded(vent_payload(seq=-1), "bad_seq")

    def test_rf11_discards_bad_window(self):
        self.assert_discarded(vent_payload(window="ajar"), "bad_window")

    def test_rf11_discards_bad_mode(self):
        self.assert_discarded(vent_payload(mode="eco"), "bad_mode")

    def test_rf11_discards_threshold_out_of_range(self):
        self.assert_discarded(vent_payload(gas_high_pct=100), "bad_gas_high_pct")
        self.assert_discarded(vent_payload(gas_low_pct=0), "bad_gas_low_pct")

    def test_rf11_discards_low_not_below_high(self):
        self.assert_discarded(vent_payload(gas_high_pct=20, gas_low_pct=20),
                              "low_not_below_high")

    def test_rf11_discards_event_of_the_other_board(self):
        self.assert_discarded(vent_payload(event="light_changed"), "bad_event")

    def test_rf11_discards_unknown_origin(self):
        self.assert_discarded(lights_payload(origin="hacker"), "bad_origin")

    def test_rf11_discards_bad_light_state(self):
        self.assert_discarded(lights_payload(light_kitchen="dim"), "bad_light_kitchen")

    def test_rf11_discards_presence_as_text(self):
        self.assert_discarded(lights_payload(presence="yes"), "bad_presence")

    def test_rf11_discarded_log_names_thing_and_event(self):
        self.assert_discarded(vent_payload(window="ajar"), "bad_window")
        self.assertEqual(self.log_line["thingName"], "smartloft-739264-vent")
        self.assertEqual(self.log_line["event"], "heartbeat")

    def test_rf11_discards_non_object_payload(self):
        self.assert_discarded("not json", "payload_not_object")

    def test_rf11_validation_does_not_modify_the_payload(self):
        payload = vent_payload()
        original = copy.deepcopy(payload)
        self.record(payload)
        self.assertEqual(payload, original)


if __name__ == "__main__":
    unittest.main()
