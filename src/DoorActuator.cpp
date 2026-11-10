#include "DoorActuator.h"

#include <Arduino.h>
#include <string.h>

#include "EventLog.h"
#include "config.h"

void DoorActuator::begin() {
  servo_.setPeriodHertz(config::door::PWM_FREQUENCY_HZ);
  servo_.attach(config::pins::SERVO_SIGNAL, config::door::PULSE_MIN_US,
                config::door::PULSE_MAX_US);
  servo_.write(positionAngle(Position::kClosed));
}

void DoorActuator::update(uint32_t nowMs) {
  // Signed difference: a move started during this loop iteration has
  // moveStartMs_ later than nowMs, which must not look like a long wait.
  const int32_t elapsedMs = static_cast<int32_t>(nowMs - moveStartMs_);
  if (moving_ && elapsedMs >= static_cast<int32_t>(config::door::SETTLE_TIME_MS)) {
    moving_ = false;
    position_ = target_;
    EventLog::recordf("ACTUATOR_DONE", "door=%s angle=%d",
                      positionName(position_), positionAngle(position_));
    requestReport();
  }
}

void DoorActuator::fillReported(JsonObject reported) const {
  reported[config::shadow_doc::KEY_DOOR] = positionName(position_);
  reported[config::shadow_doc::KEY_SERVO_ANGLE] = positionAngle(position_);
}

void DoorActuator::applyDesired(JsonObjectConst desired) {
  JsonVariantConst value = desired[config::shadow_doc::KEY_DOOR];
  if (value.isNull()) {
    return;
  }

  const char* requested = value.as<const char*>();
  Position target;
  if (requested != nullptr &&
      strcmp(requested, config::shadow_doc::DOOR_OPEN) == 0) {
    target = Position::kOpen;
  } else if (requested != nullptr &&
             strcmp(requested, config::shadow_doc::DOOR_CLOSED) == 0) {
    target = Position::kClosed;
  } else {
    EventLog::recordf("INVALID_VALUE", "door=%s",
                      requested != nullptr ? requested : "<not a string>");
    return;
  }

  if (moving_ && target == target_) {
    return;  // Already on its way; the report goes out when the move ends.
  }
  if (!moving_ && target == position_) {
    requestReport();  // Nothing to move; confirming clears the delta.
    return;
  }
  startMove(target);
}

const char* DoorActuator::positionName(Position position) {
  return position == Position::kOpen ? config::shadow_doc::DOOR_OPEN
                                     : config::shadow_doc::DOOR_CLOSED;
}

int DoorActuator::positionAngle(Position position) {
  return position == Position::kOpen ? config::door::OPEN_ANGLE_DEG
                                     : config::door::CLOSED_ANGLE_DEG;
}

void DoorActuator::startMove(Position target) {
  target_ = target;
  moving_ = true;
  moveStartMs_ = millis();
  servo_.write(positionAngle(target_));
  EventLog::recordf("ACTUATOR_START", "door=%s", positionName(target_));
}
