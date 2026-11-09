#pragma once

#include <ESP32Servo.h>

#include "DeviceComponent.h"

/**
 * @brief Servo-driven door controlled through the Shadow "door" attribute.
 *
 * The reported position changes only after the servo has had time to finish
 * its movement, so the Shadow never confirms a move that is still in progress.
 */
class DoorActuator : public DeviceComponent {
 public:
  /** Attaches the servo and moves the door to the closed position. */
  void begin() override;

  /** Detects the end of a movement. */
  void update(uint32_t nowMs) override;

  /** Adds "door" and "servo_angle". */
  void fillReported(JsonObject reported) const override;

  /** Validates and applies the "door" attribute, when present. */
  void applyDesired(JsonObjectConst desired) override;

 private:
  enum class Position { kClosed, kOpen };

  static const char* positionName(Position position);
  static int positionAngle(Position position);

  void startMove(Position target);

  Servo servo_;
  Position position_ = Position::kClosed;
  Position target_ = Position::kClosed;
  bool moving_ = false;
  uint32_t moveStartMs_ = 0;
};
