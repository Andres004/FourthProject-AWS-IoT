"""Unit tests of the skill backend, without AWS and without Alexa.

DynamoDB, AWS IoT and AWS IoT Data are replaced by in-memory fakes, and each
test sends a real Alexa request envelope to lambda_handler. Every test name
starts with the requirement it verifies.

Usage, from the project root (needs lambda/package, see the AWS guide):
    python -m unittest discover -s lambda/tests -v
"""
import io
import json
import logging
import os
import sys
import types
import unittest
from pathlib import Path

LAMBDA_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAMBDA_DIR))
sys.path.insert(1, str(LAMBDA_DIR / "package"))  # ask_sdk_core

os.environ.update(
    IOT_ENDPOINT="test-ats.iot.us-east-2.amazonaws.com",
    IOT_REGION="us-east-2",
    TABLE_NAME="user_thing",
)
# boto3 is provided by the Lambda runtime; the tests never reach AWS.
sys.modules.setdefault(
    "boto3",
    types.SimpleNamespace(
        resource=lambda *a, **k: types.SimpleNamespace(Table=lambda name: None),
        client=lambda *a, **k: None,
    ),
)

import lambda_function as skill  # noqa: E402

USER_A = "amzn1.ask.account.USER_A"
USER_B = "amzn1.ask.account.USER_B"
CODE_1 = "739264"
CODE_2 = "518306"
THING_1 = "monoambiente-739264"
THING_2 = "monoambiente-518306"
NOW_S = 1_762_700_000  # Shadow server time used by the fake


class NotFound(Exception):
    """Plays the role of ResourceNotFoundException."""


class FakeTable:
    def __init__(self):
        self.items = {}

    def get_item(self, Key):
        item = self.items.get(Key["userId"])
        return {"Item": dict(item)} if item else {}

    def put_item(self, Item):
        self.items[Item["userId"]] = dict(Item)

    def delete_item(self, Key):
        self.items.pop(Key["userId"], None)


class FakeIot:
    exceptions = types.SimpleNamespace(ResourceNotFoundException=NotFound)

    def __init__(self, thing_names):
        self.thing_names = set(thing_names)
        self.failure = None

    def describe_thing(self, thingName):
        if self.failure:
            raise self.failure
        if thingName not in self.thing_names:
            raise NotFound(thingName)
        return {"thingName": thingName}


class FakeClock:
    """Monotonic clock that only advances when the code sleeps."""

    def __init__(self):
        self.now = 0.0

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


class FakeIotData:
    """In-memory Shadows plus a simulated ESP32.

    After a desired update, the simulated device copies "desired" into
    "reported" once the Lambda has read the Shadow device_reads times.
    device_reads = None plays an ESP32 that never answers.
    """

    exceptions = types.SimpleNamespace(ResourceNotFoundException=NotFound)

    def __init__(self):
        self.shadows = {}
        self.updates = []
        self.device_reads = 2
        self.reads_since_update = 0

    def put_shadow(self, thing, reported=None, desired=None, age_s=10):
        stamp = {"timestamp": NOW_S - age_s}
        self.shadows[thing] = {
            "state": {"reported": reported or {}, "desired": desired or {}},
            "metadata": {"reported": {k: stamp for k in (reported or {})}},
            "version": 40,
            "timestamp": NOW_S,
        }

    def get_thing_shadow(self, thingName):
        if thingName not in self.shadows:
            raise NotFound(thingName)
        self.reads_since_update += 1
        if (
            self.updates
            and self.device_reads is not None
            and self.reads_since_update >= self.device_reads
        ):
            state = self.shadows[thingName]["state"]
            state.setdefault("reported", {}).update(state.get("desired", {}))
        body = json.dumps(self.shadows[thingName]).encode("utf-8")
        return {"payload": io.BytesIO(body)}

    def update_thing_shadow(self, thingName, payload):
        update = json.loads(payload)
        self.updates.append((thingName, update))
        shadow = self.shadows.setdefault(
            thingName, {"state": {}, "version": 0, "timestamp": NOW_S}
        )
        desired = shadow["state"].setdefault("desired", {})
        desired.update(update["state"]["desired"])
        shadow["version"] += 1
        self.reads_since_update = 0
        body = json.dumps({"version": shadow["version"]}).encode("utf-8")
        return {"payload": io.BytesIO(body)}


def envelope(user_id, request):
    """Builds a minimal Alexa request envelope."""
    request.setdefault("requestId", "amzn1.echo-api.request.test")
    request.setdefault("timestamp", "2026-11-09T21:00:00Z")
    request.setdefault("locale", "es-US")
    return {
        "version": "1.0",
        "session": {
            "new": False,
            "sessionId": "amzn1.echo-api.session.test",
            "application": {"applicationId": "amzn1.ask.skill.test"},
            "user": {"userId": user_id},
        },
        "context": {
            "System": {
                "application": {"applicationId": "amzn1.ask.skill.test"},
                "user": {"userId": user_id},
                "apiEndpoint": "https://api.amazonalexa.com",
            }
        },
        "request": request,
    }


def intent(user_id, name, code=None):
    slots = {}
    if code is not None or name == "LinkThing":
        slots["code"] = {"name": "code", "confirmationStatus": "NONE"}
        if code is not None:
            slots["code"]["value"] = code
    return envelope(
        user_id,
        {
            "type": "IntentRequest",
            "intent": {"name": name, "confirmationStatus": "NONE", "slots": slots},
        },
    )


class SkillTestCase(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        self.iot = FakeIot([THING_1, THING_2])
        self.iot_data = FakeIotData()
        self.clock = FakeClock()
        skill.links = skill.LinkRepository(self.table)
        skill.things = skill.ThingGateway(
            self.iot, self.iot_data, clock=self.clock.time, sleep=self.clock.sleep
        )

    def call(self, event):
        """Runs the skill and returns (speech, log record)."""
        with self.assertLogs(skill.logger, logging.INFO) as logs:
            response = skill.lambda_handler(event, None)
        records = [
            json.loads(line.split(":", 2)[2])
            for line in logs.output
            if "SKILL_REQUEST" in line
        ]
        self.assertEqual(len(records), 1, "one log line per request")
        speech = response["response"]["outputSpeech"]["ssml"]
        return speech, records[0]

    def link(self, user_id, thing_name):
        self.table.put_item(Item={"userId": user_id, "thingName": thing_name})


class LinkingTests(SkillTestCase):
    def test_rf7_link_valid_code_stores_link_with_date(self):
        speech, record = self.call(intent(USER_A, "LinkThing", CODE_1))
        self.assertIn("quedó vinculada", speech)
        self.assertIn('<say-as interpret-as="digits">739264</say-as>', speech)
        item = self.table.items[USER_A]
        self.assertEqual(item["thingName"], THING_1)
        self.assertRegex(item["fechaVinculacion"], r"^\d{4}-\d\d-\d\dT")
        self.assertEqual(record["result"], "linked")

    def test_rf7_link_persists_between_sessions(self):
        self.call(intent(USER_A, "LinkThing", CODE_1))
        self.iot_data.put_shadow(THING_1, reported={"door": "closed"})
        speech, _ = self.call(intent(USER_A, "GetDoorState"))
        self.assertIn("La puerta está cerrada", speech)

    def test_rf9_rejects_invalid_codes_without_saving(self):
        for code in ("?", "abc", "73926", "7392640", "012345", "73 9264"):
            with self.subTest(code=code):
                speech, record = self.call(intent(USER_A, "LinkThing", code))
                self.assertIn("seis dígitos", speech)
                self.assertEqual(record["result"], "invalid_code")
        speech, record = self.call(intent(USER_A, "LinkThing"))
        self.assertEqual(record["result"], "invalid_code")
        self.assertEqual(self.table.items, {})

    def test_rf9_rejects_thing_that_does_not_exist(self):
        speech, record = self.call(intent(USER_A, "LinkThing", "999999"))
        self.assertIn("No encontré ninguna casa", speech)
        self.assertEqual(record["result"], "thing_not_found")
        self.assertEqual(self.table.items, {})

    def test_rf9_change_link_replaces_previous_thing(self):
        self.link(USER_A, THING_1)
        speech, record = self.call(intent(USER_A, "LinkThing", CODE_2))
        self.assertIn("cambié tu vinculación", speech)
        self.assertEqual(self.table.items[USER_A]["thingName"], THING_2)
        self.assertEqual(record["previous"], THING_1)

    def test_rf9_same_code_again_reports_already_linked(self):
        self.link(USER_A, THING_1)
        speech, record = self.call(intent(USER_A, "LinkThing", CODE_1))
        self.assertIn("ya estaba vinculada", speech)
        self.assertEqual(record["result"], "already_linked")

    def test_rf9_unlink_deletes_link(self):
        self.link(USER_A, THING_1)
        speech, record = self.call(intent(USER_A, "UnlinkThing"))
        self.assertIn("quedó desvinculada", speech)
        self.assertNotIn(USER_A, self.table.items)
        speech, record = self.call(intent(USER_A, "UnlinkThing"))
        self.assertIn("No tienes ninguna casa vinculada", speech)

    def test_rf8_unlinked_user_is_guided_to_link(self):
        for name in ("GetPresence", "GetDoorState", "OpenDoor", "CloseDoor"):
            with self.subTest(intent=name):
                speech, record = self.call(intent(USER_A, name))
                self.assertIn("vincula mi casa con el código", speech)
                self.assertEqual(record["result"], "not_linked")
        self.assertEqual(self.iot_data.updates, [])

    def test_rf8_each_user_reaches_only_their_own_thing(self):
        self.link(USER_A, THING_1)
        self.link(USER_B, THING_2)
        self.iot_data.put_shadow(THING_1, reported={"door": "closed"})
        self.iot_data.put_shadow(THING_2, reported={"door": "closed"})
        self.call(intent(USER_A, "OpenDoor"))
        self.call(intent(USER_B, "CloseDoor"))
        self.assertEqual(
            self.iot_data.updates, [(THING_1, {"state": {"desired": {"door": "open"}}})]
        )


class QueryTests(SkillTestCase):
    def setUp(self):
        super().setUp()
        self.link(USER_A, THING_1)

    def test_rf4_presence_true_and_false(self):
        cases = ((True, "Sí, se detecta"), (False, "No, no se detecta"))
        for value, expected in cases:
            with self.subTest(presence=value):
                self.iot_data.put_shadow(THING_1, reported={"presence": value})
                speech, record = self.call(intent(USER_A, "GetPresence"))
                self.assertIn(expected, speech)
                self.assertNotIn("Ojo", speech)
                self.assertEqual(record["result"], f"presence={value}")

    def test_rf4_missing_attribute_or_shadow_says_no_data(self):
        speech, _ = self.call(intent(USER_A, "GetPresence"))
        self.assertIn("Todavía no hay datos", speech)
        self.iot_data.put_shadow(THING_1, reported={"door": "open"})
        speech, _ = self.call(intent(USER_A, "GetPresence"))
        self.assertIn("Todavía no hay datos", speech)

    def test_rf4_reads_reported_not_desired(self):
        self.iot_data.put_shadow(
            THING_1, reported={"door": "closed"}, desired={"door": "open"}
        )
        speech, record = self.call(intent(USER_A, "GetDoorState"))
        self.assertIn("La puerta está cerrada", speech)
        self.assertIn("orden pendiente para abrirla", speech)
        self.assertEqual(record["pending"], "open")

    def test_rf6_door_open_and_closed(self):
        for value, expected in (("open", "abierta"), ("closed", "cerrada")):
            with self.subTest(door=value):
                self.iot_data.put_shadow(
                    THING_1, reported={"door": value}, desired={"door": value}
                )
                speech, _ = self.call(intent(USER_A, "GetDoorState"))
                self.assertIn(f"La puerta está {expected}.", speech)
                self.assertNotIn("pendiente", speech)

    def test_rf11_offline_threshold_is_150_seconds(self):
        self.iot_data.put_shadow(THING_1, reported={"presence": False}, age_s=150)
        speech, _ = self.call(intent(USER_A, "GetPresence"))
        self.assertNotIn("Ojo", speech)
        self.iot_data.put_shadow(THING_1, reported={"presence": False}, age_s=151)
        speech, record = self.call(intent(USER_A, "GetPresence"))
        self.assertIn("no se reporta desde hace 2 minutos", speech)
        self.assertEqual(record["age_s"], 151)


class CommandTests(SkillTestCase):
    def setUp(self):
        super().setUp()
        self.link(USER_A, THING_1)

    def test_rf5_rf10_open_and_close_are_confirmed_by_device(self):
        self.iot_data.put_shadow(THING_1, reported={"door": "closed"})
        speech, record = self.call(intent(USER_A, "OpenDoor"))
        self.assertIn("Listo, la puerta está abierta", speech)
        self.assertEqual(record["result"], "confirmed")
        self.assertEqual(record["version"], 41)
        self.assertIsNotNone(record["confirm_ms"])
        self.assertGreaterEqual(record["confirm_ms"], 0)

        self.iot_data.put_shadow(THING_1, reported={"door": "open"})
        speech, _ = self.call(intent(USER_A, "CloseDoor"))
        self.assertIn("Listo, la puerta está cerrada", speech)
        self.assertEqual(
            [update for _, update in self.iot_data.updates],
            [
                {"state": {"desired": {"door": "open"}}},
                {"state": {"desired": {"door": "closed"}}},
            ],
        )

    def test_rf5_door_already_in_position_is_not_rewritten(self):
        self.iot_data.put_shadow(
            THING_1, reported={"door": "open"}, desired={"door": "open"}
        )
        speech, record = self.call(intent(USER_A, "OpenDoor"))
        self.assertIn("ya está abierta", speech)
        self.assertEqual(record["result"], "already")
        self.assertEqual(self.iot_data.updates, [])

    def test_rf5_cancels_pending_opposite_order(self):
        self.iot_data.put_shadow(
            THING_1, reported={"door": "closed"}, desired={"door": "open"}
        )
        speech, _ = self.call(intent(USER_A, "CloseDoor"))
        self.assertIn("Listo, la puerta está cerrada", speech)
        self.assertEqual(len(self.iot_data.updates), 1)

    def test_rf10_no_confirmation_within_3_s_is_reported(self):
        self.iot_data.put_shadow(THING_1, reported={"door": "closed"})
        self.iot_data.device_reads = None
        speech, record = self.call(intent(USER_A, "OpenDoor"))
        self.assertIn("todavía no recibo la confirmación", speech)
        self.assertEqual(record["result"], "sent_unconfirmed")
        self.assertIsNone(record["confirm_ms"])
        self.assertGreaterEqual(self.clock.now, skill.CONFIRM_TIMEOUT_S)
        self.assertLess(
            self.clock.now, skill.CONFIRM_TIMEOUT_S + skill.CONFIRM_POLL_S
        )

    def test_rf11_offline_command_is_queued_in_desired(self):
        self.iot_data.put_shadow(THING_1, reported={"door": "open"}, age_s=600)
        speech, record = self.call(intent(USER_A, "OpenDoor"))
        self.assertIn("tu casa está desconectada", speech)
        self.assertEqual(record["result"], "queued_offline")
        self.assertEqual(len(self.iot_data.updates), 1)
        self.assertEqual(self.clock.now, 0.0, "no waiting when offline")


class RobustnessTests(SkillTestCase):
    def test_rf8_launch_greets_linked_and_unlinked_users(self):
        speech, _ = self.call(envelope(USER_A, {"type": "LaunchRequest"}))
        self.assertIn("Todavía no tienes una casa vinculada", speech)
        self.link(USER_A, THING_1)
        speech, _ = self.call(envelope(USER_A, {"type": "LaunchRequest"}))
        self.assertIn("Puedes abrir o cerrar la puerta", speech)

    def test_unknown_intent_is_answered(self):
        speech, record = self.call(intent(USER_A, "AMAZON.FallbackIntent"))
        self.assertIn("No entendí eso", speech)
        speech, record = self.call(intent(USER_A, "AMAZON.NavigateHomeIntent"))
        self.assertEqual(record["result"], "not_understood")

    def test_rf4_rf9_aws_error_is_spoken_and_logged(self):
        self.iot.failure = RuntimeError("throttled")
        speech, record = self.call(intent(USER_A, "LinkThing", CODE_1))
        self.assertIn("Hubo un problema", speech)
        self.assertEqual(record["error"], "RuntimeError")

    def test_log_line_hides_user_id(self):
        _, record = self.call(intent(USER_A, "AMAZON.HelpIntent"))
        self.assertEqual(len(record["user"]), skill.USER_HASH_LENGTH)
        self.assertNotIn("USER_A", json.dumps(record))
        self.assertGreaterEqual(record["lambda_ms"], 0)


if __name__ == "__main__":
    unittest.main()
