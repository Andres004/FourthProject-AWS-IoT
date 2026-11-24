"""Unit tests of smartloft_skill_lambda, without AWS and without Alexa.

DynamoDB, AWS IoT and AWS IoT Data are in-memory fakes, and each test sends a
real Alexa request envelope to lambda_handler. Every test name starts with
the requirement it verifies.

Usage, from the project root (needs ask-sdk-core in lambda/skill/package):
    python -m pip install -r lambda/skill/requirements.txt -t lambda/skill/package
    python -m unittest discover -s lambda/tests -v
"""
import importlib.util
import io
import json
import logging
import sys
import types
import unittest
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1] / "skill"
sys.path.insert(0, str(SKILL_DIR / "package"))  # ask_sdk_core

_SPEC = importlib.util.spec_from_file_location(
    "skill_lambda_function", SKILL_DIR / "lambda_function.py")
skill = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(skill)

USER_A = "amzn1.ask.account.USER_A"
USER_B = "amzn1.ask.account.USER_B"
CODE_1 = "739264"
CODE_2 = "518306"
VENT_1 = "smartloft-739264-vent"
LIGHTS_1 = "smartloft-739264-lights"
VENT_2 = "smartloft-518306-vent"
LIGHTS_2 = "smartloft-518306-lights"
NOW_S = 1_795_862_400  # Shadow server time used by the fake

VENT_REPORTED = {
    "gas_pct": 4.4, "gas_mv": 237, "gas_alarm": False, "warming_up": False,
    "window": "closed", "servo_angle": 0, "mode": "manual",
    "gas_high_pct": 15, "gas_low_pct": 8,
}
LIGHTS_REPORTED = {
    "light_kitchen": "off", "light_living": "off", "light_dining": "off",
    "light_bathroom": "off", "light_bedroom": "off", "presence": False,
}


class NotFound(Exception):
    """Plays the role of ResourceNotFoundException."""


class FakeUserTable:
    """smartloft-user-thing: PK userId, SK place."""

    def __init__(self):
        self.items = {}

    def query(self, KeyConditionExpression, ExpressionAttributeValues):
        user = ExpressionAttributeValues[":user"]
        return {"Items": [dict(item) for (u, _), item in self.items.items() if u == user]}

    def put_item(self, Item):
        self.items[(Item["userId"], Item["place"])] = dict(Item)

    def delete_item(self, Key):
        self.items.pop((Key["userId"], Key["place"]), None)


class FakeIot:
    exceptions = types.SimpleNamespace(ResourceNotFoundException=NotFound)

    def __init__(self, names):
        self.names = set(names)

    def describe_thing(self, thingName):
        if thingName not in self.names:
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
    """In-memory Shadows plus simulated boards.

    After a desired update, the simulated board copies "desired" (except
    cmd_origin) into "reported" once the Lambda has read the Shadow
    device_reads times. device_reads = None plays a board that never answers.
    """

    exceptions = types.SimpleNamespace(ResourceNotFoundException=NotFound)

    def __init__(self):
        self.shadows = {}
        self.updates = []
        self.device_reads = 2
        self.reads_since_update = 0

    def put_shadow(self, name, reported, desired=None, age_s=10):
        stamp = {"timestamp": NOW_S - age_s}
        self.shadows[name] = {
            "state": {"reported": dict(reported), "desired": dict(desired or {})},
            "metadata": {"reported": {k: stamp for k in reported}},
            "version": 40,
            "timestamp": NOW_S,
        }

    def get_thing_shadow(self, thingName):
        if thingName not in self.shadows:
            raise NotFound(thingName)
        self.reads_since_update += 1
        if (self.updates and self.device_reads is not None
                and self.reads_since_update >= self.device_reads):
            state = self.shadows[thingName]["state"]
            applied = {k: v for k, v in state["desired"].items() if k != "cmd_origin"}
            state["reported"].update(applied)
        body = json.dumps(self.shadows[thingName]).encode("utf-8")
        return {"payload": io.BytesIO(body)}

    def update_thing_shadow(self, thingName, payload):
        update = json.loads(payload)
        self.updates.append((thingName, update))
        shadow = self.shadows.setdefault(
            thingName, {"state": {"reported": {}, "desired": {}}, "version": 0,
                        "timestamp": NOW_S})
        shadow["state"]["desired"].update(update["state"]["desired"])
        shadow["version"] += 1
        self.reads_since_update = 0
        return {"payload": io.BytesIO(json.dumps({"version": shadow["version"]}).encode())}


def envelope(user_id, request):
    request.setdefault("requestId", "amzn1.echo-api.request.test")
    request.setdefault("timestamp", "2026-11-24T12:00:00Z")
    request.setdefault("locale", "es-US")
    return {
        "version": "1.0",
        "session": {
            "new": False,
            "sessionId": "amzn1.echo-api.session.test",
            "application": {"applicationId": "amzn1.ask.skill.test"},
            "user": {"userId": user_id},
        },
        "context": {"System": {
            "application": {"applicationId": "amzn1.ask.skill.test"},
            "user": {"userId": user_id},
            "apiEndpoint": "https://api.amazonalexa.com",
        }},
        "request": request,
    }


def intent(user_id, name, **slots):
    """slots: name -> spoken value, or (spoken value, resolved id)."""
    built = {}
    for slot_name, value in slots.items():
        slot = {"name": slot_name, "confirmationStatus": "NONE"}
        if isinstance(value, tuple):
            spoken, resolved = value
            slot["value"] = spoken
            slot["resolutions"] = {"resolutionsPerAuthority": [{
                "authority": "amzn1.er-authority.echo-sdk.test",
                "status": {"code": "ER_SUCCESS_MATCH"},
                "values": [{"value": {"name": spoken, "id": resolved}}],
            }]}
        elif value is not None:
            slot["value"] = value
        built[slot_name] = slot
    return envelope(user_id, {
        "type": "IntentRequest",
        "intent": {"name": name, "confirmationStatus": "NONE", "slots": built},
    })


class SkillTestCase(unittest.TestCase):
    def setUp(self):
        self.table = FakeUserTable()
        self.iot = FakeIot([VENT_1, LIGHTS_1, VENT_2, LIGHTS_2])
        self.iot_data = FakeIotData()
        self.clock = FakeClock()
        skill.links = skill.LinkRepository(self.table)
        skill.things = skill.ThingGateway(self.iot, self.iot_data,
                                          clock=self.clock.time, sleep=self.clock.sleep)

    def call(self, event):
        """Runs the skill and returns (speech, log record)."""
        with self.assertLogs(skill.logger, logging.INFO) as logs:
            response = skill.lambda_handler(event, None)
        records = [json.loads(line.split(":", 2)[2]) for line in logs.output
                   if "SKILL_REQUEST" in line]
        self.assertEqual(len(records), 1, "one log line per request")
        return response["response"]["outputSpeech"]["ssml"], records[0]

    def link(self, user_id=USER_A, code=CODE_1):
        skill.links.save(user_id, code)

    def home(self, vent=None, lights=None, age_s=10, vent_desired=None):
        self.link()
        self.iot_data.put_shadow(VENT_1, dict(VENT_REPORTED, **(vent or {})),
                                 desired=vent_desired, age_s=age_s)
        self.iot_data.put_shadow(LIGHTS_1, dict(LIGHTS_REPORTED, **(lights or {})),
                                 age_s=age_s)

    def desired_of(self, name):
        return self.iot_data.shadows[name]["state"]["desired"]


class LinkingTests(SkillTestCase):
    def test_link_valid_code_stores_one_item_per_place(self):
        speech, record = self.call(intent(USER_A, "LinkThing", code=CODE_1))
        self.assertIn("quedó vinculada", speech)
        self.assertEqual(self.table.items[(USER_A, "vent")]["thingName"], VENT_1)
        self.assertEqual(self.table.items[(USER_A, "lights")]["thingName"], LIGHTS_1)
        self.assertEqual(self.table.items[(USER_A, "vent")]["homeCode"], CODE_1)
        self.assertRegex(self.table.items[(USER_A, "lights")]["linkedAt"], r"^\d{4}-\d\d-\d\dT")
        self.assertEqual(record["result"], "linked")

    def test_link_unknown_code_is_rejected(self):
        speech, record = self.call(intent(USER_A, "LinkThing", code="111111"))
        self.assertIn("No encontré", speech)
        self.assertEqual(self.table.items, {})
        self.assertEqual(record["result"], "thing_not_found")

    def test_link_invalid_code_is_rejected(self):
        speech, record = self.call(intent(USER_A, "LinkThing", code="12345"))
        self.assertIn("seis dígitos", speech)
        self.assertEqual(record["result"], "invalid_code")

    def test_link_change_replaces_both_items(self):
        self.link(USER_A, CODE_1)
        speech, record = self.call(intent(USER_A, "LinkThing", code=CODE_2))
        self.assertIn("cambié", speech)
        self.assertEqual(self.table.items[(USER_A, "vent")]["thingName"], VENT_2)
        self.assertEqual(self.table.items[(USER_A, "lights")]["thingName"], LIGHTS_2)
        self.assertEqual(record["result"], "changed")

    def test_two_users_keep_their_own_things(self):
        self.link(USER_A, CODE_1)
        self.link(USER_B, CODE_2)
        self.assertEqual(skill.links.find_things(USER_A)["lights"], LIGHTS_1)
        self.assertEqual(skill.links.find_things(USER_B)["lights"], LIGHTS_2)

    def test_unlink_removes_both_items(self):
        self.link()
        speech, record = self.call(intent(USER_A, "UnlinkThing"))
        self.assertIn("desvinculada", speech)
        self.assertEqual(self.table.items, {})
        self.assertEqual(record["result"], "unlinked")

    def test_command_without_link_asks_to_link(self):
        speech, record = self.call(intent(USER_A, "TurnOnLight", zone=("cocina", "kitchen")))
        self.assertIn("vincula mi casa", speech)
        self.assertEqual(record["result"], "not_linked")


class LightTests(SkillTestCase):
    def test_turn_on_one_light_writes_desired_with_voice_origin(self):
        self.home()
        speech, record = self.call(intent(USER_A, "TurnOnLight", zone=("cocina", "kitchen")))
        self.assertEqual(self.iot_data.updates, [(LIGHTS_1, {"state": {"desired": {
            "light_kitchen": "on", "cmd_origin": "voice"}}})])
        self.assertIn("la luz de la cocina quedó encendida", speech)
        self.assertEqual(record["result"], "confirmed")
        self.assertIsNotNone(record["confirm_ms"])

    def test_turn_off_all_lights(self):
        self.home(lights={k: "on" for k in LIGHTS_REPORTED if k.startswith("light_")})
        speech, _ = self.call(intent(USER_A, "TurnOffLight", zone=("todas", "all")))
        desired = self.iot_data.updates[0][1]["state"]["desired"]
        self.assertEqual({k for k, v in desired.items() if v == "off"},
                         {"light_kitchen", "light_living", "light_dining",
                          "light_bathroom", "light_bedroom"})
        self.assertIn("todas las luces quedaron apagadas", speech)

    def test_synonym_without_resolution_is_understood(self):
        self.home()
        self.call(intent(USER_A, "TurnOnLight", zone="dormitorio"))
        desired = self.iot_data.updates[0][1]["state"]["desired"]
        self.assertEqual(desired["light_bedroom"], "on")

    def test_light_already_on_does_not_write(self):
        self.home(lights={"light_kitchen": "on"})
        speech, record = self.call(intent(USER_A, "TurnOnLight", zone=("cocina", "kitchen")))
        self.assertIn("ya está encendida", speech)
        self.assertEqual(self.iot_data.updates, [])
        self.assertEqual(record["result"], "already")

    def test_unknown_zone_is_explained(self):
        self.home()
        speech, record = self.call(intent(USER_A, "TurnOnLight", zone="garaje"))
        self.assertIn("No reconocí la zona", speech)
        self.assertEqual(record["result"], "unknown_zone")

    def test_board_that_does_not_confirm(self):
        self.home()
        self.iot_data.device_reads = None
        speech, record = self.call(intent(USER_A, "TurnOnLight", zone=("sala", "living")))
        self.assertIn("todavía no recibo la confirmación", speech)
        self.assertEqual(record["result"], "sent_unconfirmed")

    def test_offline_board_queues_the_command(self):
        self.home(age_s=600)
        speech, record = self.call(intent(USER_A, "TurnOnLight", zone=("baño", "bathroom")))
        self.assertIn("desconectada", speech)
        self.assertEqual(self.desired_of(LIGHTS_1)["light_bathroom"], "on")
        self.assertEqual(record["result"], "queued_offline")

    def test_which_lights_are_on(self):
        self.home(lights={"light_kitchen": "on", "light_bedroom": "on"})
        speech, _ = self.call(intent(USER_A, "GetLightState"))
        self.assertIn("Están encendidas las luces de la cocina y la habitación", speech)

    def test_state_of_one_light(self):
        self.home(lights={"light_dining": "on"})
        speech, _ = self.call(intent(USER_A, "GetLightState", zone=("comedor", "dining")))
        self.assertIn("La luz del comedor está encendida", speech)

    def test_one_light_on_uses_del(self):
        self.home(lights={"light_dining": "on"})
        speech, _ = self.call(intent(USER_A, "GetLightState"))
        self.assertIn("Está encendida la luz del comedor", speech)

    def test_turn_on_dining_uses_del(self):
        self.home()
        speech, _ = self.call(intent(USER_A, "TurnOnLight", zone=("comedor", "dining")))
        self.assertIn("la luz del comedor quedó encendida", speech)

    def test_presence(self):
        self.home(lights={"presence": True})
        speech, record = self.call(intent(USER_A, "GetPresence"))
        self.assertIn("se detecta a alguien", speech)
        self.assertEqual(record["result"], "presence=True")


class WindowTests(SkillTestCase):
    def test_open_window_in_manual_mode(self):
        self.home()
        speech, record = self.call(intent(USER_A, "OpenWindow"))
        self.assertEqual(self.iot_data.updates, [(VENT_1, {"state": {"desired": {
            "window": "open", "cmd_origin": "voice"}}})])
        self.assertIn("la ventana está abierta", speech)
        self.assertEqual(record["result"], "confirmed")

    def test_window_command_in_auto_mode_is_rejected(self):
        self.home(vent={"mode": "auto"})
        speech, record = self.call(intent(USER_A, "OpenWindow"))
        self.assertIn("modo automático", speech)
        self.assertIn("activa el modo manual", speech)
        self.assertEqual(self.iot_data.updates, [])
        self.assertEqual(record["result"], "rejected_auto_mode")

    def test_pending_auto_mode_also_rejects_the_window(self):
        self.home(vent_desired={"mode": "auto"})
        _, record = self.call(intent(USER_A, "CloseWindow"))
        self.assertEqual(record["result"], "rejected_auto_mode")

    def test_close_window_during_gas_alarm_is_rejected(self):
        self.home(vent={"gas_alarm": True, "gas_pct": 22.5, "window": "open"})
        speech, record = self.call(intent(USER_A, "CloseWindow"))
        self.assertIn("No puedo cerrarla", speech)
        self.assertIn("22,5 por ciento", speech)
        self.assertIn("umbral de 15", speech)
        self.assertEqual(self.iot_data.updates, [])
        self.assertEqual(record["result"], "rejected_gas_alarm")

    def test_open_window_during_gas_alarm_is_allowed(self):
        self.home(vent={"gas_alarm": True, "gas_pct": 22.5})
        _, record = self.call(intent(USER_A, "OpenWindow"))
        self.assertEqual(record["result"], "confirmed")

    def test_window_state_with_pending_order(self):
        self.home(vent_desired={"window": "open"})
        speech, record = self.call(intent(USER_A, "GetWindowState"))
        self.assertIn("La ventana está cerrada", speech)
        self.assertIn("orden pendiente para abrirla", speech)
        self.assertEqual(record["pending"], "open")


class GasTests(SkillTestCase):
    def test_normal_air(self):
        self.home()
        speech, record = self.call(intent(USER_A, "GetGasLevel"))
        self.assertIn("el aire está normal", speech)
        self.assertIn("4,4 por ciento", speech)
        self.assertEqual(record["result"], "gas_alarm=False")

    def test_gas_alarm(self):
        self.home(vent={"gas_alarm": True, "gas_pct": 40.0, "window": "open"})
        speech, _ = self.call(intent(USER_A, "GetGasLevel"))
        self.assertIn("hay alarma de gas", speech)
        self.assertIn("40 por ciento", speech)
        self.assertIn("La ventana está abierta", speech)

    def test_warming_up(self):
        self.home(vent={"warming_up": True})
        speech, record = self.call(intent(USER_A, "GetGasLevel"))
        self.assertIn("se está calentando", speech)
        self.assertEqual(record["result"], "warming_up")

    def test_offline_note(self):
        self.home(age_s=600)
        speech, _ = self.call(intent(USER_A, "GetGasLevel"))
        self.assertIn("no se reporta desde hace 10 minutos", speech)


class ModeAndThresholdTests(SkillTestCase):
    def test_set_auto_mode(self):
        self.home()
        speech, record = self.call(intent(USER_A, "SetMode", mode=("automático", "auto")))
        self.assertEqual(self.iot_data.updates[0][1]["state"]["desired"],
                         {"mode": "auto", "cmd_origin": "voice"})
        self.assertIn("modo automático", speech)
        self.assertEqual(record["result"], "confirmed")

    def test_mode_already_set(self):
        self.home()
        speech, record = self.call(intent(USER_A, "SetMode", mode=("manual", "manual")))
        self.assertIn("ya está en modo manual", speech)
        self.assertEqual(record["result"], "already")

    def test_get_mode_with_pending_cloud_change(self):
        self.home(vent_desired={"mode": "auto", "cmd_origin": "cloud"})
        speech, _ = self.call(intent(USER_A, "GetMode"))
        self.assertIn("modo manual", speech)
        self.assertIn("pendiente para pasar a modo automático", speech)

    def test_set_high_threshold(self):
        self.home()
        speech, record = self.call(intent(USER_A, "SetThreshold",
                                          level=("alto", "high"), value="20"))
        self.assertEqual(self.iot_data.updates[0][1]["state"]["desired"],
                         {"gas_high_pct": 20, "cmd_origin": "voice"})
        self.assertIn("umbral alto quedó en 20", speech)
        self.assertEqual(record["result"], "confirmed")

    def test_threshold_out_of_range(self):
        self.home()
        speech, record = self.call(intent(USER_A, "SetThreshold",
                                          level=("alto", "high"), value="150"))
        self.assertIn("entre 1 y 99", speech)
        self.assertEqual(self.iot_data.updates, [])
        self.assertEqual(record["result"], "out_of_range")

    def test_low_must_stay_below_high(self):
        self.home()
        speech, record = self.call(intent(USER_A, "SetThreshold",
                                          level=("bajo", "low"), value="15"))
        self.assertIn("tiene que ser menor que el alto", speech)
        self.assertEqual(record["result"], "low_not_below_high")

    def test_get_thresholds(self):
        self.home()
        speech, _ = self.call(intent(USER_A, "GetThresholds"))
        self.assertIn("se activa en 15 por ciento", speech)
        self.assertIn("baja a 8 por ciento", speech)


class GeneralTests(SkillTestCase):
    def test_launch_without_link(self):
        speech, _ = self.call(envelope(USER_A, {"type": "LaunchRequest"}))
        self.assertIn("Bienvenido", speech)
        self.assertIn("vincula mi casa", speech)

    def test_fallback(self):
        speech, record = self.call(intent(USER_A, "AMAZON.FallbackIntent"))
        self.assertIn("No entendí", speech)
        self.assertEqual(record["result"], "not_understood")

    def test_log_line_hides_user_id(self):
        self.home()
        _, record = self.call(intent(USER_A, "GetMode"))
        self.assertNotIn("USER_A", json.dumps(record))
        self.assertEqual(len(record["user"]), 10)


if __name__ == "__main__":
    unittest.main()
