"""Alexa skill backend for the smart studio apartment door."""
import json
import logging
import os
from datetime import datetime, timezone

import boto3
from ask_sdk_core.dispatch_components import (
    AbstractExceptionHandler,
    AbstractRequestHandler,
)
from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.utils import get_slot_value, is_intent_name, is_request_type

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

IOT_ENDPOINT = os.environ["IOT_ENDPOINT"]
IOT_REGION = os.environ["IOT_REGION"]
TABLE_NAME = os.environ["TABLE_NAME"]

THING_NAME_PREFIX = "monoambiente-"
LINK_CODE_LENGTH = 6
DOOR_ATTRIBUTE = "door"
PRESENCE_ATTRIBUTE = "presence"
DOOR_OPEN = "open"
DOOR_CLOSED = "closed"

NOT_LINKED_SPEECH = (
    "Todavía no tienes una casa vinculada. "
    "Di: vincula mi casa con el código, seguido de los seis dígitos."
)
NO_DATA_SPEECH = "Todavía no hay datos reportados por tu casa."
REPROMPT_SPEECH = "¿Qué quieres hacer?"


class LinkRepository:
    """Stores the relation between Alexa users and Things."""

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

    def get_reported(self, thing_name):
        """Returns the reported state, or an empty dictionary."""
        try:
            response = self._iot_data.get_thing_shadow(thingName=thing_name)
        except self._iot_data.exceptions.ResourceNotFoundException:
            return {}
        document = json.loads(response["payload"].read())
        return document.get("state", {}).get("reported", {})

    def set_desired_door(self, thing_name, door_state):
        """Writes the requested door position in the desired state."""
        payload = {"state": {"desired": {DOOR_ATTRIBUTE: door_state}}}
        self._iot_data.update_thing_shadow(
            thingName=thing_name, payload=json.dumps(payload)
        )


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
    """Returns the Alexa user identifier of the request."""
    return handler_input.request_envelope.context.system.user.user_id


def respond(handler_input, speech):
    """Builds a response that keeps the session open."""
    return (
        handler_input.response_builder.speak(speech)
        .ask(REPROMPT_SPEECH)
        .response
    )


def parse_link_code(raw_code):
    """Returns a valid link code, or None."""
    if raw_code is None or not raw_code.isdigit():
        return None
    if len(raw_code) != LINK_CODE_LENGTH or raw_code.startswith("0"):
        return None
    return raw_code


class LinkedThingHandler(AbstractRequestHandler):
    """Base handler for intents that require a linked Thing."""

    def handle(self, handler_input):
        thing_name = links.find_thing(get_user_id(handler_input))
        if thing_name is None:
            return respond(handler_input, NOT_LINKED_SPEECH)
        return respond(handler_input, self.handle_thing(thing_name))

    def handle_thing(self, thing_name):
        """Executes the intent and returns the speech text."""
        raise NotImplementedError


class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        thing_name = links.find_thing(get_user_id(handler_input))
        if thing_name is None:
            return respond(handler_input, "Bienvenido. " + NOT_LINKED_SPEECH)
        return respond(
            handler_input,
            "Bienvenido. Puedes abrir o cerrar la puerta, "
            "o preguntar si hay alguien en la entrada.",
        )


class LinkThingHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("LinkThing")(handler_input)

    def handle(self, handler_input):
        code = parse_link_code(get_slot_value(handler_input, "code"))
        if code is None:
            return respond(
                handler_input,
                "El código debe tener seis dígitos y no empezar en cero.",
            )

        thing_name = THING_NAME_PREFIX + code
        if not things.exists(thing_name):
            return respond(
                handler_input, "No encontré ninguna casa con ese código."
            )

        links.save(get_user_id(handler_input), thing_name)
        return respond(handler_input, "Listo, tu casa quedó vinculada.")


class UnlinkThingHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("UnlinkThing")(handler_input)

    def handle(self, handler_input):
        links.delete(get_user_id(handler_input))
        return respond(handler_input, "Tu casa quedó desvinculada.")


class GetPresenceHandler(LinkedThingHandler):
    def can_handle(self, handler_input):
        return is_intent_name("GetPresence")(handler_input)

    def handle_thing(self, thing_name):
        presence = things.get_reported(thing_name).get(PRESENCE_ATTRIBUTE)
        if presence is None:
            return NO_DATA_SPEECH
        if presence:
            return "Sí, se detecta a alguien en la entrada."
        return "No, no se detecta a nadie en la entrada."


class OpenDoorHandler(LinkedThingHandler):
    def can_handle(self, handler_input):
        return is_intent_name("OpenDoor")(handler_input)

    def handle_thing(self, thing_name):
        things.set_desired_door(thing_name, DOOR_OPEN)
        return "Abriendo la puerta."


class CloseDoorHandler(LinkedThingHandler):
    def can_handle(self, handler_input):
        return is_intent_name("CloseDoor")(handler_input)

    def handle_thing(self, thing_name):
        things.set_desired_door(thing_name, DOOR_CLOSED)
        return "Cerrando la puerta."


class GetDoorStateHandler(LinkedThingHandler):
    def can_handle(self, handler_input):
        return is_intent_name("GetDoorState")(handler_input)

    def handle_thing(self, thing_name):
        door = things.get_reported(thing_name).get(DOOR_ATTRIBUTE)
        if door == DOOR_OPEN:
            return "La puerta está abierta."
        if door == DOOR_CLOSED:
            return "La puerta está cerrada."
        return NO_DATA_SPEECH


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        return respond(
            handler_input,
            "Puedes vincular tu casa con un código, abrir o cerrar la puerta, "
            "preguntar el estado de la puerta o si hay alguien en la entrada.",
        )


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        return respond(handler_input, "No entendí eso. Puedes pedir ayuda.")


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


class CatchAllExceptionHandler(AbstractExceptionHandler):
    def can_handle(self, handler_input, exception):
        return True

    def handle(self, handler_input, exception):
        logger.error(exception, exc_info=True)
        return respond(
            handler_input,
            "Hubo un problema al procesar tu pedido. Intenta de nuevo.",
        )


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
    FallbackIntentHandler(),
    CancelOrStopIntentHandler(),
    SessionEndedRequestHandler(),
):
    skill_builder.add_request_handler(request_handler)
skill_builder.add_exception_handler(CatchAllExceptionHandler())

lambda_handler = skill_builder.lambda_handler()
