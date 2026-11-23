#pragma once

#include <stdint.h>

/**
 * @brief Shows the connection state on a LED.
 *
 * The LED is only an indicator, never one of the smart object's actuators.
 * Fast blink: no WiFi. Slow blink: WiFi without Shadow link. Steady: online.
 */
class StatusLed {
 public:
  /** Configures the LED pin. */
  void begin();

  /** Updates the LED pattern from the current connection state. */
  void update(uint32_t nowMs, bool wifiConnected, bool shadowConnected);

 private:
  void write(bool on);

  bool on_ = false;
  uint32_t lastToggleMs_ = 0;
};
