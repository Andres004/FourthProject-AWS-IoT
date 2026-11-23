/**
 * @file ZoneLight.cpp
 * @brief Zone light: command validation, LED output and light_changed event.
 */
#include "ZoneLight.h"

#include <Arduino.h>
#include <string.h>

#include "EventLog.h"
#include "config_lights.h"

ZoneLight::ZoneLight(const char* zoneName, const char* shadowKey, uint8_t pin)
    : zoneName_(zoneName), shadowKey_(shadowKey), pin_(pin) {}

void ZoneLight::begin() {
  pinMode(pin_, OUTPUT);
  write(false);
}

void ZoneLight::update(uint32_t nowMs) {
  (void)nowMs;
}

void ZoneLight::fillReported(JsonObject reported) const {
  namespace doc = config::shadow_doc;
  reported[shadowKey_] = on_ ? doc::LIGHT_ON : doc::LIGHT_OFF;
}

void ZoneLight::applyDesired(JsonObjectConst desired, DesiredSource source) {
  namespace doc = config::shadow_doc;
  JsonVariantConst value = desired[shadowKey_];
  if (value.isNull()) {
    return;  // This command is for another component.
  }

  const char* requested = value.as<const char*>();
  bool on;
  if (requested != nullptr && strcmp(requested, doc::LIGHT_ON) == 0) {
    on = true;
  } else if (requested != nullptr && strcmp(requested, doc::LIGHT_OFF) == 0) {
    on = false;
  } else {
    EventLog::recordf("INVALID_VALUE", "%s=%s", shadowKey_,
                      requested != nullptr ? requested : "<not a string>");
    return;
  }

  markDesiredConsumed(config::report_doc::KEY_CMD_ORIGIN);
  if (on == on_) {
    requestConfirmation();  // Already in that state; the report clears the delta.
    return;
  }

  const char* origin = commandOrigin(desired, source);
  write(on);
  EventLog::recordf("LIGHT_APPLIED", "zone=%s state=%s origin=%s", zoneName_,
                    on_ ? doc::LIGHT_ON : doc::LIGHT_OFF, origin);
  requestReport(config::lights_events::LIGHT_CHANGED,
                config::lights_events::PRIORITY_LIGHT, origin);
}

void ZoneLight::write(bool on) {
  on_ = on;
  const bool level = on_ == config::light::ACTIVE_HIGH;
  digitalWrite(pin_, level ? HIGH : LOW);
}
