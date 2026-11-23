/**
 * @file WindowActuator.h
 * @brief SG90 servo that opens and closes the window of the model.
 */
#pragma once

#include <ESP32Servo.h>

#include "DeviceComponent.h"
#include "config_vent.h"

/**
 * @brief Servo-driven window controlled through the Shadow "window" attribute.
 *
 * The reported position changes only after the servo has had time to finish
 * its movement, so the Shadow never confirms a move that is still in progress.
 * An applied command clears desired.window and desired.cmd_origin in the next
 * report, so a stale desired value can never move the window again.
 */
class WindowActuator : public DeviceComponent {
 public:
  /** Attaches the servo and moves the window to the closed position. */
  void begin() override;

  /** Detects the end of a movement. */
  void update(uint32_t nowMs) override;

  /** Adds "window" and "servo_angle". */
  void fillReported(JsonObject reported) const override;

  /** Validates and applies the "window" attribute, when present. */
  void applyDesired(JsonObjectConst desired, DesiredSource source) override;

  /**
   * Starts moving the window, used by commands and by the automatic logic.
   * @param open true to open, false to close.
   * @param origin Who causes the move ("voice", "cloud", "edge", "boot").
   * @return false when the window is already there or already on its way.
   */
  bool moveTo(bool open, const char* origin);

  /** @return true when the window is open or opening. */
  bool isOpenOrOpening() const {
    return (moving_ ? target_ : position_) == Position::kOpen;
  }

  /** @return true while the servo has not finished its movement. */
  bool isMoving() const { return moving_; }

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
  const char* moveOrigin_ = config::report_doc::ORIGIN_BOOT;  // Cause of the current move
};
