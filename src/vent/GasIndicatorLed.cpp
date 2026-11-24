/**
 * @file GasIndicatorLed.cpp
 * @brief LED patterns of the gas indicator.
 */
#include "GasIndicatorLed.h"

#include <Arduino.h>

#include "config_vent.h"

GasIndicatorLed::GasIndicatorLed(const GasSensor& gas,
                                 const VentilationController& ventilation)
    : gas_(gas), ventilation_(ventilation) {}

void GasIndicatorLed::begin() {
  pinMode(config::pins::GAS_LED, OUTPUT);
  write(false);
}

void GasIndicatorLed::update(uint32_t nowMs) {
  if (gas_.isWarmingUp()) {
    if (nowMs - lastToggleMs_ >= config::gas_led::WARMUP_BLINK_HALF_PERIOD_MS) {
      lastToggleMs_ = nowMs;
      write(!on_);
    }
    return;
  }
  const bool alarm = ventilation_.gasAlarm();
  if (alarm != on_) {
    write(alarm);
  }
}

void GasIndicatorLed::fillReported(JsonObject reported) const {
  (void)reported;
}

void GasIndicatorLed::write(bool on) {
  on_ = on;
  digitalWrite(config::pins::GAS_LED, on_ ? HIGH : LOW);
}
