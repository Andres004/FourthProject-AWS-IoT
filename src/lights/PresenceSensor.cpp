/**
 * @file PresenceSensor.cpp
 * @brief PIR polling, warm-up, hold time and presence events.
 */
#include "PresenceSensor.h"

#include <Arduino.h>

#include "EventLog.h"
#include "config_lights.h"

void PresenceSensor::begin() {
  // The pull-down keeps the input LOW if the sensor gets disconnected.
  pinMode(config::pins::PIR_OUTPUT, INPUT_PULLDOWN);
  startMs_ = millis();
}

void PresenceSensor::update(uint32_t nowMs) {
  if (!warmedUp_) {
    if (nowMs - startMs_ < config::pir::WARMUP_MS) {
      return;
    }
    warmedUp_ = true;
    EventLog::record("PIR_READY");
  }

  if (nowMs - lastPollMs_ < config::pir::POLL_PERIOD_MS) {
    return;
  }
  lastPollMs_ = nowMs;

  if (digitalRead(config::pins::PIR_OUTPUT) == HIGH) {
    lastMotionMs_ = nowMs;
    setPresence(true);
  } else if (presence_ &&
             nowMs - lastMotionMs_ >= config::pir::PRESENCE_HOLD_MS) {
    setPresence(false);
  }
}

void PresenceSensor::fillReported(JsonObject reported) const {
  reported[config::shadow_doc::KEY_PRESENCE] = presence_;
}

void PresenceSensor::setPresence(bool presence) {
  if (presence == presence_) {
    return;
  }
  presence_ = presence;
  namespace ev = config::lights_events;
  if (presence_) {
    EventLog::record("PRESENCE_DETECTED");
    requestReport(ev::PRESENCE_DETECTED, ev::PRIORITY_PRESENCE_DETECTED);
  } else {
    EventLog::record("PRESENCE_CLEARED");
    requestReport(ev::PRESENCE_CLEARED, ev::PRIORITY_PRESENCE_CLEARED);
  }
}
