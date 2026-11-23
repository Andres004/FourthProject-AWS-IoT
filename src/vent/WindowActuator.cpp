/**
 * @file WindowActuator.cpp
 * @brief Window servo: timed move and confirmation.
 */
#include "WindowActuator.h"

#include <Arduino.h>

#include "EventLog.h"

void WindowActuator::begin() {
  servo_.setPeriodHertz(config::window::PWM_FREQUENCY_HZ);
  servo_.attach(config::pins::SERVO_SIGNAL, config::window::PULSE_MIN_US,
                config::window::PULSE_MAX_US);
  servo_.write(positionAngle(Position::kClosed));
}

void WindowActuator::update(uint32_t nowMs) {
  // Signed difference: a move started during this loop iteration has
  // moveStartMs_ later than nowMs, which must not look like a long wait.
  const int32_t elapsedMs = static_cast<int32_t>(nowMs - moveStartMs_);
  if (moving_ && elapsedMs >= static_cast<int32_t>(config::window::SETTLE_TIME_MS)) {
    moving_ = false;
    position_ = target_;
    EventLog::recordf("ACTUATOR_DONE", "window=%s angle=%d",
                      positionName(position_), positionAngle(position_));
    requestReport(config::vent_events::WINDOW_CHANGED,
                  config::vent_events::PRIORITY_WINDOW, moveOrigin_);
  }
}

void WindowActuator::fillReported(JsonObject reported) const {
  reported[config::shadow_doc::KEY_WINDOW] = positionName(position_);
  reported[config::shadow_doc::KEY_SERVO_ANGLE] = positionAngle(position_);
}

bool WindowActuator::moveTo(bool open, const char* origin) {
  const Position target = open ? Position::kOpen : Position::kClosed;
  if (moving_ && target == target_) {
    return false;  // Already on its way; the report goes out when it ends.
  }
  if (!moving_ && target == position_) {
    return false;
  }
  moveOrigin_ = origin;
  startMove(target);
  return true;
}

const char* WindowActuator::positionName(Position position) {
  return position == Position::kOpen ? config::shadow_doc::WINDOW_OPEN
                                     : config::shadow_doc::WINDOW_CLOSED;
}

int WindowActuator::positionAngle(Position position) {
  return position == Position::kOpen ? config::window::OPEN_ANGLE_DEG
                                     : config::window::CLOSED_ANGLE_DEG;
}

void WindowActuator::startMove(Position target) {
  target_ = target;
  moving_ = true;
  moveStartMs_ = millis();
  servo_.write(positionAngle(target_));
  EventLog::recordf("ACTUATOR_START", "window=%s origin=%s",
                    positionName(target_), moveOrigin_);
}
