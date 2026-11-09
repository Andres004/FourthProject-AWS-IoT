#include "StatusLed.h"

#include <Arduino.h>

#include "config.h"

void StatusLed::begin() {
  pinMode(config::pins::STATUS_LED, OUTPUT);
  write(false);
}

void StatusLed::update(uint32_t nowMs, bool wifiConnected,
                       bool shadowConnected) {
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
  digitalWrite(config::pins::STATUS_LED, on_ ? HIGH : LOW);
}
