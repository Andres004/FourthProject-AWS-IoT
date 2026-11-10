"""Alexa skill backend for the smart studio apartment door.

The skill never talks to the ESP32. It resolves the Thing linked to the Alexa
user in DynamoDB, then reads the "reported" section of its Device Shadow or
writes the "desired" section. Every request ends with one JSON log line in
CloudWatch, used as evidence in the tests.
"""
import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone

import boto3
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
IOT_ENDPOINT = os.environ["IOT_ENDPOINT"]
IOT_REGION = os.environ["IOT_REGION"]
TABLE_NAME = os.environ["TABLE_NAME"]

# Linking: Thing name = prefix + six-digit code, as printed by the ESP32.
THING_NAME_PREFIX = "monoambiente-"
LINK_CODE_LENGTH = 6

# Shadow contract shared with the firmware (include/config.h).
DOOR_ATTRIBUTE = "door"
PRESENCE_ATTRIBUTE = "presence"
DOOR_OPEN = "open"
DOOR_CLOSED = "closed"

# The ESP32 reports at least every 60 s (heartbeat). Without a report for
# 2.5 heartbeats the device is considered offline, with margin for one lost
# message and the MQTT reconnection time.
OFFLINE_AFTER_S = 150
SECONDS_PER_MINUTE = 60

USER_HASH_LENGTH = 10  # Logged instead of the full Alexa userId.
MS_PER_S = 1000

NOT_LINKED_SPEECH = (
    "Todavía no tienes una casa vinculada. "
    "Di: vincula mi casa con el código, seguido de los seis dígitos."
)
NO_DATA_SPEECH = "Todavía no hay datos reportados por tu casa."
REPROMPT_SPEECH = "¿Qué quieres hacer?"
HELP_SPEECH = (
    "Puedes vincular tu casa con un código, abrir o cerrar la puerta, "
    "preguntar el estado de la puerta o si hay alguien en la entrada."
)


def now_ms():
    """Returns the current UTC time in milliseconds since the epoch."""
    return int(time.time() * MS_PER_S)


def say_digits(code):
    """Returns SSML that reads a link code digit by digit."""
    return f'<say-as interpret-as="digits">{code}</say-as>'


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
        self.desired = state.get("desired", {})
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
        """True when the device reported within OFFLINE_AFTER_S."""
        return self.age_s is not None and self.age_s <= OFFLINE_AFTER_S

    def offline_note(self):
        """Returns a warning about stale data, or an empty string."""
        if self.online or self.age_s is None:
            return ""
        return (
            f" Ojo: tu casa no se reporta desde hace {describe_age(self.age_s)},"
            " así que este dato puede no estar actualizado."
        )


class LinkRepository:
    """Stores the relation between Alexa users and Things (DynamoDB)."""

    def __init__(self, table):
        self._table = table

    def find_thing(self, user_id):
        """Returns the Thing linked to the user, or None."""
        item = self._table.get_item(Key={"userId": user_id}).get("Item")
        return item["thingName"] if item else None

    def save(self, user_id, thing_name):
        """Creates or replaces the link of the user."""
        self._table.put_item(
            Item={
                "userId": user_id,
                "thingName": thing_name,
                "fechaVinculacion": datetime.now(timezone.utc).isoformat(),
            }
        )

    def delete(self, user_id):
        """Removes the link of the user."""
        self._table.delete_item(Key={"userId": user_id})


class ThingGateway:
    """Reads and updates Things in AWS IoT Core."""

    def __init__(self, iot_client, iot_data_client):
        self._iot = iot_client
        self._iot_data = iot_data_client

    def exists(self, thing_name):
        """Returns True when the Thing is registered in AWS IoT Core."""
        try:
            self._iot.describe_thing(thingName=thing_name)
            return True
        except self._iot.exceptions.ResourceNotFoundException:
            return False

    def get_state(self, thing_name):
        """Returns the ShadowState, or None if the Shadow does not exist."""
        try:
            response = self._iot_data.get_thing_shadow(thingName=thing_name)
        except self._iot_data.exceptions.ResourceNotFoundException:
            return None
        return ShadowState(json.loads(response["payload"].read()))

    def set_desired_door(self, thing_name, door_state):
        """Writes the door position in "desired" and returns the version."""
        payload = {"state": {"desired": {DOOR_ATTRIBUTE: door_state}}}
        response = self._iot_data.update_thing_shadow(
            thingName=thing_name, payload=json.dumps(payload)
        )
        return json.loads(response["payload"].read()).get("version")


links = LinkRepository(boto3.resource("dynamodb").Table(TABLE_NAME))
things = ThingGateway(
    boto3.client("iot", region_name=IOT_REGION),
    boto3.client(
        "iot-data",
        region_name=IOT_REGION,
        endpoint_url="https://" + IOT_ENDPOINT,
    ),
)


def get_user_id(handler_input):
    """Returns the Alexa user identifier of the request (RF8)."""
    return handler_input.request_envelope.context.system.user.user_id


def audit(handler_input):
    """Returns the per-request dictionary written to the log line."""
    return handler_input.attributes_manager.request_attributes


def respond(handler_input, speech):
    """Builds a response that keeps the session open."""
    return (
        handler_input.response_builder.speak(speech)
        .ask(REPROMPT_SPEECH)
        .response
    )


def parse_link_code(raw_code):
    """Returns a valid six-digit link code without a leading zero, or None."""
    if raw_code is None or not raw_code.isdigit():
        return None
    if len(raw_code) != LINK_CODE_LENGTH or raw_code.startswith("0"):
        return None
    return raw_code


class LinkedThingHandler(AbstractRequestHandler):
    """Base handler for intents that require a linked Thing (RF8)."""

    def handle(self, handler_input):
        thing_name = links.find_thing(get_user_id(handler_input))
        audit(handler_input)["thing"] = thing_name
        if thing_name is None:
            audit(handler_input)["result"] = "not_linked"
            return respond(handler_input, NOT_LINKED_SPEECH)
        return respond(
            handler_input, self.handle_thing(thing_name, audit(handler_input))
        )

    def handle_thing(self, thing_name, record):
        """Executes the intent, fills the log record and returns the speech."""
        raise NotImplementedError


class DoorCommandHandler(LinkedThingHandler):
    """Writes a door position in "desired" (RF5)."""

    intent_name = None
    target = None
    already_speech = None
    moving_speech = None

    def can_handle(self, handler_input):
        return is_intent_name(self.intent_name)(handler_input)

    def handle_thing(self, thing_name, record):
        state = things.get_state(thing_name)
        if (
            state is not None
            and state.online
            and state.reported.get(DOOR_ATTRIBUTE) == self.target
            and state.desired.get(DOOR_ATTRIBUTE, self.target) == self.target
        ):
            record["result"] = "already"
            return self.already_speech

        record["version"] = things.set_desired_door(thing_name, self.target)
        record["desired_set_utc_ms"] = now_ms()
        if state is not None and not state.online:
            record["result"] = "queued_offline"
            return (
                "Envié la orden, pero tu casa está desconectada. "
                "Se aplicará apenas vuelva a conectarse."
            )
        record["result"] = "sent"
        return self.moving_speech


class OpenDoorHandler(DoorCommandHandler):
    intent_name = "OpenDoor"
    target = DOOR_OPEN
    already_speech = "La puerta ya está abierta."
    moving_speech = "Abriendo la puerta."


class CloseDoorHandler(DoorCommandHandler):
    intent_name = "CloseDoor"
    target = DOOR_CLOSED
    already_speech = "La puerta ya está cerrada."
    moving_speech = "Cerrando la puerta."


class GetPresenceHandler(LinkedThingHandler):
    """Answers with the reported presence (RF4)."""

    def can_handle(self, handler_input):
        return is_intent_name("GetPresence")(handler_input)

    def handle_thing(self, thing_name, record):
        state = things.get_state(thing_name)
        presence = None if state is None else state.reported.get(
            PRESENCE_ATTRIBUTE
        )
        if presence is None:
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        record["result"] = f"presence={presence}"
        record["age_s"] = state.age_s
        speech = (
            "Sí, se detecta a alguien en la entrada."
            if presence
            else "No, no se detecta a nadie en la entrada."
        )
        return speech + state.offline_note()


class GetDoorStateHandler(LinkedThingHandler):
    """Answers with the reported door position (RF6)."""

    def can_handle(self, handler_input):
        return is_intent_name("GetDoorState")(handler_input)

    def handle_thing(self, thing_name, record):
        state = things.get_state(thing_name)
        door = None if state is None else state.reported.get(DOOR_ATTRIBUTE)
        if door not in (DOOR_OPEN, DOOR_CLOSED):
            record["result"] = "no_data"
            return NO_DATA_SPEECH
        record["result"] = f"door={door}"
        record["age_s"] = state.age_s

        speech = (
            "La puerta está abierta."
            if door == DOOR_OPEN
            else "La puerta está cerrada."
        )
        pending = state.desired.get(DOOR_ATTRIBUTE)
        if pending in (DOOR_OPEN, DOOR_CLOSED) and pending != door:
            record["pending"] = pending
            verb = "abrirla" if pending == DOOR_OPEN else "cerrarla"
            speech += f" Hay una orden pendiente para {verb}."
        return speech + state.offline_note()


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        thing_name = links.find_thing(get_user_id(handler_input))
        audit(handler_input)["thing"] = thing_name
        if thing_name is None:
            return respond(handler_input, "Bienvenido. " + NOT_LINKED_SPEECH)
        return respond(
            handler_input,
            "Bienvenido. Puedes abrir o cerrar la puerta, "
            "o preguntar si hay alguien en la entrada.",
        )


class LinkThingHandler(AbstractRequestHandler):
    """Links, or changes the link of, the user's Thing (RF7, RF9)."""

    def can_handle(self, handler_input):
        return is_intent_name("LinkThing")(handler_input)

    def handle(self, handler_input):
        record = audit(handler_input)
        slot = get_slot(handler_input, "code")
        raw_code = slot.value if slot else None
        code = parse_link_code(raw_code)
        if code is None:
            record["result"] = "invalid_code"
            record["code"] = raw_code
            return respond(
                handler_input,
                "El código debe tener seis dígitos y no empezar en cero.",
            )

        thing_name = THING_NAME_PREFIX + code
        record["thing"] = thing_name
        if not things.exists(thing_name):
            record["result"] = "thing_not_found"
            return respond(
                handler_input,
                f"No encontré ninguna casa con el código {say_digits(code)}. "
                "Revisa el código e inténtalo otra vez.",
            )

        user_id = get_user_id(handler_input)
        previous = links.find_thing(user_id)
        if previous == thing_name:
            record["result"] = "already_linked"
            return respond(
                handler_input,
                f"Tu casa ya estaba vinculada con el código {say_digits(code)}.",
            )

        links.save(user_id, thing_name)
        if previous is None:
            record["result"] = "linked"
            speech = (
                f"Listo, tu casa con el código {say_digits(code)} "
                "quedó vinculada."
            )
        else:
            record["result"] = "changed"
            record["previous"] = previous
            speech = f"Listo, cambié tu vinculación al código {say_digits(code)}."
        return respond(handler_input, speech)


class UnlinkThingHandler(AbstractRequestHandler):
    """Removes the user's link (RF9)."""

    def can_handle(self, handler_input):
        return is_intent_name("UnlinkThing")(handler_input)

    def handle(self, handler_input):
        record = audit(handler_input)
        user_id = get_user_id(handler_input)
        thing_name = links.find_thing(user_id)
        record["thing"] = thing_name
        if thing_name is None:
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
        return is_intent_name("AMAZON.CancelIntent")(
            handler_input
        ) or is_intent_name("AMAZON.StopIntent")(handler_input)

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
        return respond(
            handler_input,
            "Hubo un problema al procesar tu pedido. Intenta de nuevo.",
        )


class RequestTimer(AbstractRequestInterceptor):
    """Stores when the Lambda started handling the request."""

    def process(self, handler_input):
        audit(handler_input)["start_utc_ms"] = now_ms()


def log_request(handler_input):
    """Writes one JSON line per request to CloudWatch."""
    record = audit(handler_input)
    request = handler_input.request_envelope.request
    intent = getattr(request, "intent", None)
    user_hash = hashlib.sha256(
        get_user_id(handler_input).encode("utf-8")
    ).hexdigest()[:USER_HASH_LENGTH]
    end = now_ms()
    line = {
        "event": "SKILL_REQUEST",
        "request": request.object_type,
        "intent": intent.name if intent else None,
        "user": user_hash,
        "alexa_timestamp": str(request.timestamp),
        "lambda_ms": end - record.get("start_utc_ms", end),
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
    GetPresenceHandler(),
    OpenDoorHandler(),
    CloseDoorHandler(),
    GetDoorStateHandler(),
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
