/**
 * @file StatusLed.h
 * @brief Optional LED that shows the WiFi / Shadow connection state.
 */
#pragma once

#include <stdint.h>

/**
 * @brief Shows the connection state on a LED.
 *
 * The LED is only an indicator, never one of the smart object's actuators.
 * Fast blink: no WiFi. Slow blink: WiFi without Shadow link. Steady: online.
 * A board without status LED passes config::status_led::NO_LED and every
 * method does nothing.
 */
class StatusLed {
 public:
  /** @param pin GPIO of the LED, or config::status_led::NO_LED. */
  explicit StatusLed(int pin);

  /** Configures the LED pin. */
  void begin();

  /** Updates the LED pattern from the current connection state. */
  void update(uint32_t nowMs, bool wifiConnected, bool shadowConnected);

 private:
  void write(bool on);

  int pin_;
  bool on_ = false;
  uint32_t lastToggleMs_ = 0;
};
