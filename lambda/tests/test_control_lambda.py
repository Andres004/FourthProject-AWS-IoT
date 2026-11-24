"""Unit tests of smartloft_control_lambda (rule C1), without AWS.

The event-index query and the IoT Data client are in-memory fakes, and the
clock is fixed. Every test name starts with the requirement it verifies.

Usage, from the project root:
    python -m unittest discover -s lambda/tests -v
"""
import importlib.util
import json
import logging
import unittest
from decimal import Decimal
from pathlib import Path

# Each Lambda has its own lambda_function.py, so load this one by path under
# a unique module name.
_SOURCE = Path(__file__).resolve().parents[1] / "control" / "lambda_function.py"
_SPEC = importlib.util.spec_from_file_location("control_lambda_function", _SOURCE)
control_lambda = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(control_lambda)

THING = "smartloft-739264-vent"
NOW_MS = 1795862400000
HOUR_MS = 3600 * 1000


class FakeEventTable:
    """Answers event-index queries from a list of stored items, in pages."""

    def __init__(self, items, page_size=2):
        self.items = items
        self.page_size = page_size
        self.queries = []

    def query(self, **kwargs):
        self.queries.append(kwargs)
        values = kwargs["ExpressionAttributeValues"]
        matches = [
            {"seq": Decimal(item["seq"]), "deviceTs": Decimal(item["deviceTs"])}
            for item in self.items
            if item["eventKey"] == values[":key"]
            and values[":from"] <= item["timestamp"] <= values[":to"]
        ]
        start = kwargs.get("ExclusiveStartKey", 0)
        page = {"Items": matches[start:start + self.page_size]}
        if start + self.page_size < len(matches):
            page["LastEvaluatedKey"] = start + self.page_size
        return page


class FakeIotData:
    """Keeps the shadow updates."""

    def __init__(self):
        self.updates = []

    def update_thing_shadow(self, thingName, payload):
        self.updates.append((thingName, json.loads(payload)))


def stored_alarm(seq, hours_ago, thing=THING):
    return {
        "eventKey": f"{thing}#gas_alarm_on",
        "timestamp": NOW_MS - int(hours_ago * HOUR_MS),
        "seq": seq,
        "deviceTs": NOW_MS - int(hours_ago * HOUR_MS) - 300,
    }


def alarm_payload(mode="manual", seq=100, thing=THING, event="gas_alarm_on"):
    return {
        "thingName": thing,
        "timestamp": NOW_MS,
        "reported": {
            "event": event, "mode": mode, "gas_alarm": True, "gas_pct": 22.5,
            "seq": seq, "device_ts": NOW_MS - 300, "origin": "edge",
        },
    }


class ControlLambdaTest(unittest.TestCase):

    def run_c1(self, stored_items, payload):
        self.table = FakeEventTable(stored_items)
        self.iot = FakeIotData()
        control = control_lambda.GasControl(
            control_lambda.AlarmCounter(self.table),
            control_lambda.ShadowWriter(self.iot),
            lambda: NOW_MS,
        )
        with self.assertLogs(control_lambda.logger, logging.INFO) as logs:
            result = control.handle(payload)
        self.log_line = json.loads(logs.records[-1].getMessage())
        return result

    def assert_forced_auto(self):
        self.assertEqual(self.iot.updates, [
            (THING, {"state": {"desired": {"mode": "auto", "cmd_origin": "cloud"}}}),
        ])

    # --- RF13: C1 forces auto mode -------------------------------------

    def test_rf13_third_alarm_in_manual_forces_auto(self):
        stored = [stored_alarm(10, 5), stored_alarm(40, 2)]
        result = self.run_c1(stored, alarm_payload())

        self.assertEqual(result, {"action": "force_auto",
                                  "reason": "limit_reached", "count": 3})
        self.assert_forced_auto()
        self.assertEqual(self.log_line["log"], "CONTROL_DECISION")
        self.assertEqual(self.log_line["action"], "force_auto")
        self.assertEqual(self.log_line["count"], 3)

    def test_rf13_second_alarm_does_nothing(self):
        result = self.run_c1([stored_alarm(10, 5)], alarm_payload())
        self.assertEqual(result, {"action": "none", "reason": "below_limit",
                                  "count": 2})
        self.assertEqual(self.iot.updates, [])

    def test_rf13_current_alarm_already_stored_counts_once(self):
        # The data rule stored the current alarm before this Lambda queried.
        current = {"eventKey": f"{THING}#gas_alarm_on", "timestamp": NOW_MS,
                   "seq": 100, "deviceTs": NOW_MS - 300}
        result = self.run_c1([stored_alarm(10, 5), current], alarm_payload())
        self.assertEqual(result["count"], 2)
        self.assertEqual(self.iot.updates, [])

    def test_rf13_duplicate_stored_alarm_counts_once(self):
        # A retried invocation of the data Lambda may store the same report twice.
        stored = [stored_alarm(10, 5), stored_alarm(10, 5)]
        result = self.run_c1(stored, alarm_payload())
        self.assertEqual(result["count"], 2)

    def test_rf13_alarms_older_than_window_are_ignored(self):
        stored = [stored_alarm(10, 30), stored_alarm(40, 25), stored_alarm(70, 1)]
        result = self.run_c1(stored, alarm_payload())
        self.assertEqual(result["count"], 2)
        self.assertEqual(self.iot.updates, [])

    def test_rf13_alarms_of_other_things_are_ignored(self):
        other = "smartloft-518306-vent"
        stored = [stored_alarm(10, 5, other), stored_alarm(40, 2, other)]
        result = self.run_c1(stored, alarm_payload())
        self.assertEqual(result["count"], 1)

    def test_rf13_reads_every_page_of_the_query(self):
        stored = [stored_alarm(seq, 1) for seq in range(1, 6)]  # 3 pages of 2
        result = self.run_c1(stored, alarm_payload())
        self.assertEqual(result["count"], 6)
        self.assertEqual(len(self.table.queries), 3)

    def test_rf13_c1_fires_again_after_user_returns_to_manual(self):
        # Guide V5: designed behaviour, documented in the report.
        stored = [stored_alarm(10, 6), stored_alarm(40, 4), stored_alarm(70, 2)]
        result = self.run_c1(stored, alarm_payload(seq=120))
        self.assertEqual(result["action"], "force_auto")
        self.assertEqual(result["count"], 4)

    def test_rf13_query_uses_index_and_reserved_word_alias(self):
        self.run_c1([], alarm_payload())
        query = self.table.queries[0]
        self.assertEqual(query["IndexName"], "event-index")
        self.assertEqual(query["ExpressionAttributeNames"], {"#ts": "timestamp"})
        self.assertEqual(query["ExpressionAttributeValues"][":from"],
                         NOW_MS - 24 * HOUR_MS)

    # --- RF13: C1 only acts in manual mode, on vent alarms ---------------

    def test_rf13_auto_mode_does_nothing_and_skips_the_query(self):
        stored = [stored_alarm(10, 5), stored_alarm(40, 2)]
        result = self.run_c1(stored, alarm_payload(mode="auto"))
        self.assertEqual(result, {"action": "none", "reason": "auto_mode",
                                  "count": None})
        self.assertEqual(self.table.queries, [])
        self.assertEqual(self.iot.updates, [])

    def test_rf13_ignores_lights_thing(self):
        result = self.run_c1([], alarm_payload(thing="smartloft-739264-lights"))
        self.assertEqual(result["reason"], "not_vent_thing")

    def test_rf13_ignores_other_events(self):
        result = self.run_c1([], alarm_payload(event="gas_alarm_off"))
        self.assertEqual(result["reason"], "not_gas_alarm_on")
        self.assertEqual(self.iot.updates, [])

    def test_rf13_limit_comes_from_environment_default(self):
        self.assertEqual(control_lambda.GAS_EVENTS_LIMIT, 3)
        self.assertEqual(control_lambda.GAS_EVENTS_WINDOW_H, 24)


if __name__ == "__main__":
    unittest.main()
