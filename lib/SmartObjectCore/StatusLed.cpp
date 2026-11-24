/**
 * @file StatusLed.cpp
 * @brief Blink patterns of the connection LED.
 */
#include "StatusLed.h"

#include <Arduino.h>

#include "config_common.h"

StatusLed::StatusLed(int pin) : pin_(pin) {}

void StatusLed::begin() {
  if (pin_ == config::status_led::NO_LED) {
    return;
  }
  pinMode(pin_, OUTPUT);
  write(false);
}

void StatusLed::update(uint32_t nowMs, bool wifiConnected,
                       bool shadowConnected) {
  if (pin_ == config::status_led::NO_LED) {
    return;
  }
  if (wifiConnected && shadowConnected) {
    if (!on_) {
      write(true);
    }
    return;
  }

  const uint32_t halfPeriodMs = wifiConnected
                                    ? config::status_led::BLINK_SHADOW_DOWN_MS
                                    : config::status_led::BLINK_WIFI_DOWN_MS;
  if (nowMs - lastToggleMs_ >= halfPeriodMs) {
    lastToggleMs_ = nowMs;
    write(!on_);
  }
}

void StatusLed::write(bool on) {
  on_ = on;
  digitalWrite(pin_, on_ ? HIGH : LOW);
}
