"""Alexa skill backend of SmartLoft (technical guide 5.6, 5.10 and 5.12).

The skill never talks to the boards. It resolves the two Things linked to the
Alexa user in DynamoDB (one per place: "vent" and "lights"), then reads the
"reported" section of their Shadows or writes the "desired" section, always
with cmd_origin = "voice". Every request ends with one JSON log line
SKILL_REQUEST in CloudWatch, used as evidence in the tests.

Coexistence with the automatic rule E1 (guide 5.6): in auto mode the voice
does not move the window; while the gas alarm is on the window cannot be
closed; thresholds must be 1-99 with low < high. The board applies the same
rules again (defence in depth).
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone

from ask_sdk_core.dispatch_components import (
    AbstractExceptionHandler,
    AbstractRequestHandler,
    AbstractRequestInterceptor,
    AbstractResponseInterceptor,
)
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import get_slot, is_intent_name, is_request_type

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Deployment settings, from the Lambda environment variables.
IOT_ENDPOINT = os.environ.get("IOT_ENDPOINT", "")
IOT_REGION = os.environ.get("IOT_REGION", "us-east-2")
USER_TABLE = os.environ.get("USER_TABLE", "smartloft-user-thing")

# Linking: Thing name = prefix + six-digit home code + "-" + place.
THING_NAME_PREFIX = "smartloft-"
LINK_CODE_LENGTH = 6
PLACE_VENT = "vent"
PLACE_LIGHTS = "lights"
PLACES = (PLACE_VENT, PLACE_LIGHTS)

# Shadow contract shared with the firmware (include/config_*.h).
KEY_CMD_ORIGIN = "cmd_origin"
ORIGIN_VOICE = "voice"
KEY_WINDOW = "window"
WINDOW_OPEN = "open"
WINDOW_CLOSED = "closed"
KEY_MODE = "mode"
MODE_AUTO = "auto"
MODE_MANUAL = "manual"
KEY_GAS_PCT = "gas_pct"
KEY_GAS_ALARM = "gas_alarm"
KEY_WARMING_UP = "warming_up"
KEY_GAS_HIGH = "gas_high_pct"
KEY_GAS_LOW = "gas_low_pct"
KEY_PRESENCE = "presence"
LIGHT_ON = "on"
LIGHT_OFF = "off"
THRESHOLD_MIN = 1
THRESHOLD_MAX = 99

# Slot ids (interaction model) -> Shadow keys and spoken names.
ZONE_ALL = "all"
ZONES = {
    "kitchen": ("light_kitchen", "la cocina"),
    "living": ("light_living", "la sala"),
    "dining": ("light_dining", "el comedor"),
    "bathroom": ("light_bathroom", "el baño"),
    "bedroom": ("light_bedroom", "la habitación"),
}
LEVELS = {"high": (KEY_GAS_HIGH, "alto"), "low": (KEY_GAS_LOW, "bajo")}
MODE_NAMES = {MODE_AUTO: "automático", MODE_MANUAL: "manual"}

# Spoken words -> slot ids, used when Alexa sends no entity resolution.
SLOT_SYNONYMS = {
    "zone": {
        "cocina": "kitchen", "sala": "living", "sala de estar": "living",
        "living": "living", "comedor": "dining", "baño": "bathroom",
        "habitación": "bedroom", "dormitorio": "bedroom", "cuarto": "bedroom",
        "todas": ZONE_ALL, "toda la casa": ZONE_ALL, "todas las luces": ZONE_ALL,
    },
    "mode": {"automático": MODE_AUTO, "auto": MODE_AUTO, "manual": MODE_MANUAL},
    "level": {"alto": "high", "de alarma": "high", "bajo": "low", "de cierre": "low"},
}

# The boards report at least every 60 s (heartbeat). Without a report for
# 2.5 heartbeats the board is considered offline (P3 RF11).
OFFLINE_AFTER_S = 150
SECONDS_PER_MINUTE = 60

# After a command the Lambda waits for the board to confirm it in "reported".
# The limit equals the declared response time and stays below the Lambda
# timeout and the 8 s Alexa limit.
CONFIRM_TIMEOUT_S = 3.0
CONFIRM_POLL_S = 0.25

USER_HASH_LENGTH = 10  # Logged instead of the full Alexa userId.
MS_PER_S = 1000

NOT_LINKED_SPEECH = (
    "Todavía no tienes una casa vinculada. "
    "Di: vincula mi casa con el código, seguido de los seis dígitos."
)
NO_DATA_SPEECH = "Todavía no hay datos reportados por tu casa."
REPROMPT_SPEECH = "¿Qué quieres hacer?"
HELP_SPEECH = (
    "Puedes encender o apagar las luces de cada zona, abrir o cerrar la "
    "ventana en modo manual, preguntar si hay gas, cambiar el modo de la "
    "ventilación o sus umbrales, y preguntar si hay alguien en la entrada."
)
OFFLINE_QUEUED_SPEECH = (
    "Envié la orden, pero tu casa está desconectada. "
    "Se aplicará apenas vuelva a conectarse."
)


def now_ms():
    """Returns the current UTC time in milliseconds since the epoch."""
    return int(time.time() * MS_PER_S)


def say_digits(code):
    """Returns SSML that reads a link code digit by digit."""
    return f'<say-as interpret-as="digits">{code}</say-as>'


def say_pct(value):
    """Returns a percentage with at most one decimal and a decimal comma."""
    rounded = round(float(value), 1)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:.1f}".replace(".", ",")


def of_zone(spoken):
    """Returns "de la cocina" / "del comedor" (de + el contracts to del)."""
    return "del " + spoken[3:] if spoken.startswith("el ") else "de " + spoken


def describe_age(age_s):
    """Returns a spoken description of how long ago something happened."""
    minutes = age_s // SECONDS_PER_MINUTE
    if minutes < 1:
        return f"{age_s} segundos"
    if minutes == 1:
        return "un minuto"
    return f"{minutes} minutos"


class ShadowState:
    """Read-only view of a Shadow document returned by GetThingShadow."""

    def __init__(self, document):
        state = document.get("state", {})
        self.reported = state.get("reported", {})
        self.desired = state.get("desired", {}) or {}
        self.version = document.get("version")
        self.age_s = self._report_age(document)

    @staticmethod
    def _report_age(document):
        """Seconds since the newest reported attribute, or None."""
        metadata = document.get("metadata", {}).get("reported", {})
        stamps = [
            entry["timestamp"]
            for entry in metadata.values()
            if isinstance(entry, dict) and "timestamp" in entry
        ]
        server_time = document.get("timestamp")
        if not stamps or server_time is None:
            return None
        return max(0, server_time - max(stamps))

    @property
    def online(self):
        """True when the board reported within OFFLINE_AFTER_S."""
        return self.age_s is not None and self.age_s <= OFFLINE_AFTER_S

    def offline_note(self):
        """Returns a warning about stale data, or an empty string."""
        if self.online or self.age_s is None:
            return ""
        return (
            f" Ojo: tu casa no se reporta desde hace {describe_age(self.age_s)},"
            " así que este dato puede no estar actualizado."
        )

    def wanted(self, key):
        """The value the board will end with: pending desired, else reported."""
        return self.desired.get(key, self.reported.get(key))


class LinkRepository:
    """Stores which Things belong to each Alexa user (smartloft-user-thing).

    One item per place: PK userId, SK place, plus thingName, homeCode and
    linkedAt.
    """

    def __init__(self, table):
        self._table = table

    def find_things(self, user_id):
        """Returns {place: thingName} for the user (empty when not linked)."""
        response = self._table.query(
            KeyConditionExpression="userId = :user",
            ExpressionAttributeValues={":user": user_id},
        )
        return {item["place"]: item["thingName"] for item in response.get("Items", [])}

    def save(self, user_id, code):
        """Creates or replaces the two items of the user."""
        linked_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for place in PLACES:
            self._table.put_item(Item={
                "userId": user_id,
                "place": place,
                "thingName": thing_name(code, place),
                "homeCode": code,
                "linkedAt": linked_at,
            })

    def delete(self, user_id):
        """Removes every item of the user."""
        for place in PLACES:
            self._table.delete_item(Key={"userId": user_id, "place": place})


class ThingGateway:
    """Reads and updates Things in AWS IoT Core."""

    def __init__(self, iot_client, iot_data_client, clock=time.monotonic,
                 sleep=time.sleep):
        self._iot = iot_client
        self._iot_data = iot_data_client
        self._clock = clock
        self._sleep = sleep

    def exists(self, name):
        """Returns True when the Thing is registered in AWS IoT Core."""
        try:
            self._iot.describe_thing(thingName=name)
            return True
        except self._iot.exceptions.ResourceNotFoundException:
            return False

    def get_state(self, name):
        """Returns the ShadowState, or None if the Shadow does not exist."""
        try:
            response = self._iot_data.get_thing_shadow(thingName=name)
        except self._iot_data.exceptions.ResourceNotFoundException:
            return None
        return ShadowState(json.loads(response["payload"].read()))

    def set_desired(self, name, attributes):
        """Writes attributes in "desired" with cmd_origin = voice; returns the version."""
        desired = dict(attributes, **{KEY_CMD_ORIGIN: ORIGIN_VOICE})
        response = self._iot_data.update_thing_shadow(
            thingName=name, payload=json.dumps({"state": {"desired": desired}})
        )
        return json.loads(response["payload"].read()).get("version")

    def wait_for(self, name, expected):
        """Polls "reported" until every key has its expected value.

        Returns True when the board confirmed within CONFIRM_TIMEOUT_S.
        """
        deadline = self._clock() + CONFIRM_TIMEOUT_S
        while True:
            state = self.get_state(name)
            if state is not None and all(
                state.reported.get(key) == value for key, value in expected.items()
            ):
                return True
            if self._clock() >= deadline:
                return False
            self._sleep(CONFIRM_POLL_S)


links = None   # LinkRepository, created on the first request
things = None  # ThingGateway, created on the first request


def init_services():
    """Creates the AWS clients once per Lambda container."""
    global links, things
    if links is not None and things is not None:
        return
    import boto3  # Provided by the Lambda runtime

    links = LinkRepository(boto3.resource("dynamodb").Table(USER_TABLE))
    endpoint = f"https://{IOT_ENDPOINT}" if IOT_ENDPOINT else None
    things = ThingGateway(
        boto3.client("iot", region_name=IOT_REGION),
        boto3.client("iot-data", region_name=IOT_REGION, endpoint_url=endpoint),
    )


def thing_name(code, place):
    return f"{THING_NAME_PREFIX}{code}-{place}"


def get_user_id(handler_input):
    """Returns the Alexa user identifier of the request."""
    return handler_input.request_envelope.context.system.user.user_id


def audit(handler_input):
    """Returns the per-request dictionary written to the log line."""
    return handler_input.attributes_manager.request_attributes


def respond(handler_input, speech):
    """Builds a response that keeps the session open."""
    return handler_input.response_builder.speak(speech).ask(REPROMPT_SPEECH).response


def slot_value(handler_input, name):
    """Returns the raw spoken value of a slot, or None."""
    slot = get_slot(handler_input, name)
    return slot.value if slot is not None and slot.value else None


def slot_id(handler_input, name):
    """Returns the id of a custom slot value (entity resolution), or None."""
    slot = get_slot(handler_input, name)
    if slot is None or not slot.value:
        return None
    resolutions = getattr(slot, "resolutions", None)
    for authority in getattr(resolutions, "resolutions_per_authority", None) or []:
        code = getattr(authority.status.code, "value", authority.status.code)
        if code == "ER_SUCCESS_MATCH" and authority.values:
            return authority.values[0].value.id
    return SLOT_SYNONYMS.get(name, {}).get(slot.value.strip().lower())


def parse_link_code(raw_code):
    """Returns a valid six-digit link code without a leading zero, or None."""
    if raw_code is None or not raw_code.isdigit():
        return None
    if len(raw_code) != LINK_CODE_LENGTH or raw_code.startswith("0"):
        return None
    return raw_code


class LinkedHandler(AbstractRequestHandler):
    """Base handler for intents that need the user's Things."""

    intent_name = None
    place = None  # Which Thing the intent works on

    def can_handle(self, handler_input):
        return is_intent_name(self.intent_name)(handler_input)

    def handle(self, handler_input):
        record = audit(handler_input)
        linked = links.find_things(get_user_id(handler_input))
        name = linked.get(self.place)
        record["thing"] = name
        if name is None:
            record["result"] = "not_linked"
            return respond(handler_input, NOT_LINKED_SPEECH)
        return respond(handler_input, self.handle_thing(handler_input, name, record))

    def handle_thing(self, handler_input, name, record):
        """Executes the intent, fills the log record and returns the speech."""
        raise NotImplementedError


def send_command(name, state, attributes, record):
    """Writes desired, waits for the confirmation and returns a result code.

    Result: "queued_offline", "confirmed" or "sent_unconfirmed".
    """
    record["version"] = things.set_desired(name, attributes)
    record["desired_set_utc_ms"] = now_ms()
    if state is not None and not state.online:
        record["result"] = "queued_offline"
        return record["result"]
    if things.wait_for(name, attributes):
        record["confirmed_utc_ms"] = now_ms()
        record["result"] = "confirmed"
    else:
        record["result"] = "sent_unconfirmed"
    return record["result"]


UNCONFIRMED_SPEECH = (
    "Envié la orden, pero todavía no recibo la confirmación. "
    "Pregúntame en unos segundos."
)


# ---------------------------------------------------------------- lights

class LightCommandHandler(LinkedHandler):
    """Turns one zone, or all of them, on or off (voice only, guide 5.4)."""

    place = PLACE_LIGHTS
    target = None
    adjective = None  # "encendida" / "apagada"

    def handle_thing(self, handler_input, name, record):
        zone = slot_id(handler_input, "zone")
        record["zone"] = zone
        if zone != ZONE_ALL and zone not in ZONES:
            record["result"] = "unknown_zone"
            return ("No reconocí la zona. Puedes decir cocina, sala, comedor, "
                    "baño, habitación o todas.")
        every = zone == ZONE_ALL
        zones = list(ZONES) if every else [zone]
        attributes = {ZONES[z][0]: self.target for z in zones}
        if every:
            where, are, ended, adjective = ("Todas las luces", "están", "quedaron",
                                            self.adjective + "s")
        else:
            where, are, ended, adjective = (f"La luz {of_zone(ZONES[zone][1])}", "está",
                                            "quedó", self.adjective)

        state = things.get_state(name)
        if state is not None and state.online and all(
            state.reported.get(key) == self.target and state.wanted(key) == self.target
            for key in attributes
        ):
            record["result"] = "already"
            return f"{where} ya {are} {adjective}."

        result = send_command(name, state, attributes, record)
        if result == "queued_offline":
            return OFFLINE_QUEUED_SPEECH
        if result == "sent_unconfirmed":
            return UNCONFIRMED_SPEECH
        return f"Listo, {where[0].lower() + where[1:]} {ended} {adjective}."


class TurnOnLightHandler(LightCommandHandler):
    intent_name = "TurnOnLight"
    target = LIGHT_ON
    adjective = "encendida"


class TurnOffLightHandler(LightCommandHandler):
    intent_name = "TurnOffLight"
    target = LIGHT_OFF
    adjective = "apagada"


class GetLightStateHandler(LinkedHandler):
    """Reports one zone, or which lights are on."""

    intent_name = "GetLightState"
    place = PLACE_LIGHTS

    def handle_thing(self, handler_input, name, record):
        state = things.get_state(name)
        if state is None or not any(key in state.reported for key, _ in ZONES.values()):
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        zone = slot_id(handler_input, "zone")
        record["zone"] = zone
        if zone in ZONES:
            key, spoken = ZONES[zone]
            value = state.reported.get(key)
            record["result"] = f"{key}={value}"
            word = "encendida" if value == LIGHT_ON else "apagada"
            return f"La luz {of_zone(spoken)} está {word}." + state.offline_note()

        on = [spoken for key, spoken in ZONES.values() if state.reported.get(key) == LIGHT_ON]
        record["result"] = f"lights_on={len(on)}"
        if not on:
            return "Todas las luces están apagadas." + state.offline_note()
        if len(on) == len(ZONES):
            return "Todas las luces están encendidas." + state.offline_note()
        listed = on[0] if len(on) == 1 else ", ".join(on[:-1]) + " y " + on[-1]
        if len(on) == 1:
            return f"Está encendida la luz {of_zone(on[0])}." + state.offline_note()
        return f"Están encendidas las luces de {listed}." + state.offline_note()


class GetPresenceHandler(LinkedHandler):
    """Answers with the reported presence at the entrance."""

    intent_name = "GetPresence"
    place = PLACE_LIGHTS

    def handle_thing(self, handler_input, name, record):
        state = things.get_state(name)
        presence = None if state is None else state.reported.get(KEY_PRESENCE)
        if presence is None:
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        record["result"] = f"presence={presence}"
        record["age_s"] = state.age_s
        speech = ("Sí, se detecta a alguien en la entrada." if presence
                  else "No, no se detecta a nadie en la entrada.")
        return speech + state.offline_note()


# ------------------------------------------------------------ ventilation

def vent_state_or_none(name, record):
    state = things.get_state(name)
    if state is None or KEY_MODE not in state.reported:
        record["result"] = "no_data"
        return None
    return state


class WindowCommandHandler(LinkedHandler):
    """Moves the window by voice, only in manual mode (guide 5.6)."""

    place = PLACE_VENT
    target = None
    action = None   # "abrir" / "cerrar"
    done = None     # "abierta" / "cerrada"

    def handle_thing(self, handler_input, name, record):
        state = vent_state_or_none(name, record)
        if state is None:
            return NO_DATA_SPEECH
        if state.wanted(KEY_MODE) != MODE_MANUAL:
            record["result"] = "rejected_auto_mode"
            return ("La ventilación está en modo automático. Si quieres manejar "
                    "la ventana, di: activa el modo manual.")
        if self.target == WINDOW_CLOSED and state.reported.get(KEY_GAS_ALARM):
            record["result"] = "rejected_gas_alarm"
            return (f"No puedo cerrarla: el índice de gas es "
                    f"{say_pct(state.reported.get(KEY_GAS_PCT, 0))} por ciento, por encima "
                    f"del umbral de {state.reported.get(KEY_GAS_HIGH)}.")
        if (state.online and state.reported.get(KEY_WINDOW) == self.target
                and state.wanted(KEY_WINDOW) == self.target):
            record["result"] = "already"
            return f"La ventana ya está {self.done}."

        result = send_command(name, state, {KEY_WINDOW: self.target}, record)
        if result == "queued_offline":
            return OFFLINE_QUEUED_SPEECH
        if result == "sent_unconfirmed":
            return UNCONFIRMED_SPEECH
        return f"Listo, la ventana está {self.done}."


class OpenWindowHandler(WindowCommandHandler):
    intent_name = "OpenWindow"
    target = WINDOW_OPEN
    action = "abrir"
    done = "abierta"


class CloseWindowHandler(WindowCommandHandler):
    intent_name = "CloseWindow"
    target = WINDOW_CLOSED
    action = "cerrar"
    done = "cerrada"


class GetWindowStateHandler(LinkedHandler):
    intent_name = "GetWindowState"
    place = PLACE_VENT

    def handle_thing(self, handler_input, name, record):
        state = vent_state_or_none(name, record)
        window = None if state is None else state.reported.get(KEY_WINDOW)
        if window not in (WINDOW_OPEN, WINDOW_CLOSED):
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        record["result"] = f"window={window}"
        speech = "La ventana está abierta." if window == WINDOW_OPEN else "La ventana está cerrada."
        pending = state.desired.get(KEY_WINDOW)
        if pending in (WINDOW_OPEN, WINDOW_CLOSED) and pending != window:
            record["pending"] = pending
            speech += f" Hay una orden pendiente para {'abrirla' if pending == WINDOW_OPEN else 'cerrarla'}."
        return speech + state.offline_note()


class GetGasLevelHandler(LinkedHandler):
    intent_name = "GetGasLevel"
    place = PLACE_VENT

    def handle_thing(self, handler_input, name, record):
        state = vent_state_or_none(name, record)
        if state is None or KEY_GAS_PCT not in state.reported:
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        if state.reported.get(KEY_WARMING_UP):
            record["result"] = "warming_up"
            return ("El sensor se está calentando; todavía no hay lecturas "
                    "confiables." + state.offline_note())
        pct = state.reported[KEY_GAS_PCT]
        alarm = bool(state.reported.get(KEY_GAS_ALARM))
        record["result"] = f"gas_alarm={alarm}"
        record["gas_pct"] = pct
        if alarm:
            speech = (f"Sí, hay alarma de gas: el índice es {say_pct(pct)} por ciento, "
                      f"por encima del umbral de {state.reported.get(KEY_GAS_HIGH)}.")
            window = state.reported.get(KEY_WINDOW)
            speech += " La ventana está abierta." if window == WINDOW_OPEN else " La ventana está cerrada."
        else:
            speech = (f"No, el aire está normal: el índice de gas es {say_pct(pct)} por "
                      f"ciento, y la alarma se activa en {state.reported.get(KEY_GAS_HIGH)}.")
        return speech + state.offline_note()


class SetModeHandler(LinkedHandler):
    intent_name = "SetMode"
    place = PLACE_VENT

    def handle_thing(self, handler_input, name, record):
        mode = slot_id(handler_input, "mode")
        record["mode"] = mode
        if mode not in MODE_NAMES:
            record["result"] = "unknown_mode"
            return "Los modos son automático y manual. ¿Cuál quieres?"
        state = vent_state_or_none(name, record)
        if state is None:
            return NO_DATA_SPEECH
        if state.online and state.reported.get(KEY_MODE) == mode and state.wanted(KEY_MODE) == mode:
            record["result"] = "already"
            return f"La ventilación ya está en modo {MODE_NAMES[mode]}."
        result = send_command(name, state, {KEY_MODE: mode}, record)
        if result == "queued_offline":
            return OFFLINE_QUEUED_SPEECH
        if result == "sent_unconfirmed":
            return UNCONFIRMED_SPEECH
        speech = f"Listo, la ventilación está en modo {MODE_NAMES[mode]}."
        if mode == MODE_MANUAL:
            speech += " Ahora puedes abrir o cerrar la ventana con la voz."
        else:
            speech += " La ventana se moverá sola según el gas."
        return speech


class GetModeHandler(LinkedHandler):
    intent_name = "GetMode"
    place = PLACE_VENT

    def handle_thing(self, handler_input, name, record):
        state = vent_state_or_none(name, record)
        if state is None:
            return NO_DATA_SPEECH
        mode = state.reported.get(KEY_MODE)
        record["result"] = f"mode={mode}"
        speech = f"La ventilación está en modo {MODE_NAMES.get(mode, mode)}."
        pending = state.desired.get(KEY_MODE)
        if pending in MODE_NAMES and pending != mode:
            speech += f" Hay una orden pendiente para pasar a modo {MODE_NAMES[pending]}."
        return speech + state.offline_note()


class SetThresholdHandler(LinkedHandler):
    intent_name = "SetThreshold"
    place = PLACE_VENT

    def handle_thing(self, handler_input, name, record):
        level = slot_id(handler_input, "level")
        raw = slot_value(handler_input, "value")
        record["level"] = level
        record["value"] = raw
        if level not in LEVELS:
            record["result"] = "unknown_level"
            return "Dime si quieres cambiar el umbral alto o el bajo."
        if raw is None or not raw.isdigit() or not THRESHOLD_MIN <= int(raw) <= THRESHOLD_MAX:
            record["result"] = "out_of_range"
            return (f"El umbral tiene que ser un número entero entre {THRESHOLD_MIN} "
                    f"y {THRESHOLD_MAX} por ciento.")
        value = int(raw)
        state = vent_state_or_none(name, record)
        if state is None:
            return NO_DATA_SPEECH
        key, spoken = LEVELS[level]
        high = value if key == KEY_GAS_HIGH else state.wanted(KEY_GAS_HIGH)
        low = value if key == KEY_GAS_LOW else state.wanted(KEY_GAS_LOW)
        if high is not None and low is not None and low >= high:
            record["result"] = "low_not_below_high"
            return (f"El umbral bajo tiene que ser menor que el alto. Ahora el alto es "
                    f"{high} y el bajo quedaría en {low}.")
        if state.online and state.reported.get(key) == value and state.wanted(key) == value:
            record["result"] = "already"
            return f"El umbral {spoken} ya está en {value} por ciento."
        result = send_command(name, state, {key: value}, record)
        if result == "queued_offline":
            return OFFLINE_QUEUED_SPEECH
        if result == "sent_unconfirmed":
            return UNCONFIRMED_SPEECH
        return f"Listo, el umbral {spoken} quedó en {value} por ciento."


class GetThresholdsHandler(LinkedHandler):
    intent_name = "GetThresholds"
    place = PLACE_VENT

    def handle_thing(self, handler_input, name, record):
        state = vent_state_or_none(name, record)
        if state is None or KEY_GAS_HIGH not in state.reported:
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        high = state.reported[KEY_GAS_HIGH]
        low = state.reported.get(KEY_GAS_LOW)
        record["result"] = f"high={high},low={low}"
        return (f"La alarma de gas se activa en {high} por ciento y se apaga "
                f"cuando baja a {low} por ciento." + state.offline_note())


# -------------------------------------------------------- linking, others

class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        linked = links.find_things(get_user_id(handler_input))
        audit(handler_input)["thing"] = linked.get(PLACE_VENT)
        if not linked:
            return respond(handler_input, "Bienvenido. " + NOT_LINKED_SPEECH)
        return respond(handler_input,
                       "Bienvenido. Puedes manejar las luces, la ventana y la "
                       "ventilación, o preguntar si hay gas.")


class LinkThingHandler(AbstractRequestHandler):
    """Links, or changes the link of, the user's home (both Things)."""

    def can_handle(self, handler_input):
        return is_intent_name("LinkThing")(handler_input)

    def handle(self, handler_input):
        record = audit(handler_input)
        raw_code = slot_value(handler_input, "code")
        code = parse_link_code(raw_code)
        if code is None:
            record["result"] = "invalid_code"
            record["code"] = raw_code
            return respond(handler_input,
                           "El código debe tener seis dígitos y no empezar en cero.")

        names = {place: thing_name(code, place) for place in PLACES}
        record["thing"] = names[PLACE_VENT]
        missing = [name for name in names.values() if not things.exists(name)]
        if missing:
            record["result"] = "thing_not_found"
            record["missing"] = missing
            return respond(handler_input,
                           f"No encontré ninguna casa con el código {say_digits(code)}. "
                           "Revisa el código e inténtalo otra vez.")

        user_id = get_user_id(handler_input)
        previous = links.find_things(user_id)
        if previous == names:
            record["result"] = "already_linked"
            return respond(handler_input,
                           f"Tu casa ya estaba vinculada con el código {say_digits(code)}.")

        links.save(user_id, code)
        if not previous:
            record["result"] = "linked"
            speech = f"Listo, tu casa con el código {say_digits(code)} quedó vinculada."
        else:
            record["result"] = "changed"
            record["previous"] = previous.get(PLACE_VENT)
            speech = f"Listo, cambié tu vinculación al código {say_digits(code)}."
        return respond(handler_input, speech)


class UnlinkThingHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("UnlinkThing")(handler_input)

    def handle(self, handler_input):
        record = audit(handler_input)
        user_id = get_user_id(handler_input)
        linked = links.find_things(user_id)
        record["thing"] = linked.get(PLACE_VENT)
        if not linked:
            record["result"] = "not_linked"
            return respond(handler_input, "No tienes ninguna casa vinculada.")
        links.delete(user_id)
        record["result"] = "unlinked"
        return respond(handler_input, "Tu casa quedó desvinculada.")


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return respond(handler_input, HELP_SPEECH)


class CancelOrStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (is_intent_name("AMAZON.CancelIntent")(handler_input)
                or is_intent_name("AMAZON.StopIntent")(handler_input))

    def handle(self, handler_input):
        return handler_input.response_builder.speak("Hasta luego.").response


class SessionEndedRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


class UnhandledRequestHandler(AbstractRequestHandler):
    """Fallback, NavigateHome and any intent without its own handler."""

    def can_handle(self, handler_input):
        return True

    def handle(self, handler_input):
        audit(handler_input)["result"] = "not_understood"
        return respond(handler_input, "No entendí eso. " + HELP_SPEECH)


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        record = audit(handler_input)
        record["result"] = "error"
        record["error"] = type(exception).__name__
        log_request(handler_input)  # Response interceptors are skipped here.
        return respond(handler_input, "Hubo un problema al procesar tu pedido. Intenta de nuevo.")


class RequestTimer(AbstractRequestInterceptor):
    """Creates the AWS clients and stores when the Lambda started."""

    def process(self, handler_input):
        init_services()
        audit(handler_input)["start_utc_ms"] = now_ms()


def log_request(handler_input):
    """Writes one JSON line per request to CloudWatch."""
    record = audit(handler_input)
    request = handler_input.request_envelope.request
    intent = getattr(request, "intent", None)
    user_hash = hashlib.sha256(get_user_id(handler_input).encode("utf-8")).hexdigest()[:USER_HASH_LENGTH]
    end = now_ms()
    line = {
        "event": "SKILL_REQUEST",
        "request": request.object_type,
        "intent": intent.name if intent else None,
        "user": user_hash,
        "alexa_timestamp": str(request.timestamp),
        "lambda_ms": end - record.get("start_utc_ms", end),
        "confirm_ms": (
            record["confirmed_utc_ms"] - record["start_utc_ms"]
            if "confirmed_utc_ms" in record and "start_utc_ms" in record
            else None
        ),
        **record,
    }
    logger.info(json.dumps(line, default=str, ensure_ascii=False))


class RequestLogger(AbstractResponseInterceptor):
    """Logs every request that ends without an exception."""

    def process(self, handler_input, response):
        log_request(handler_input)


skill_builder = SkillBuilder()
for request_handler in (
    LaunchRequestHandler(),
    LinkThingHandler(),
    UnlinkThingHandler(),
    TurnOnLightHandler(),
    TurnOffLightHandler(),
    GetLightStateHandler(),
    GetPresenceHandler(),
    OpenWindowHandler(),
    CloseWindowHandler(),
    GetWindowStateHandler(),
    GetGasLevelHandler(),
    SetModeHandler(),
    GetModeHandler(),
    SetThresholdHandler(),
    GetThresholdsHandler(),
    HelpIntentHandler(),
    CancelOrStopIntentHandler(),
    SessionEndedRequestHandler(),
    UnhandledRequestHandler(),  # Must stay last.
):
    skill_builder.add_request_handler(request_handler)
skill_builder.add_exception_handler(CatchAllExceptionHandler())
skill_builder.add_global_request_interceptor(RequestTimer())
skill_builder.add_global_response_interceptor(RequestLogger())

lambda_handler = skill_builder.lambda_handler()
