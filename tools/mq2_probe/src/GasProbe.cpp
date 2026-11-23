/**
 * @file GasProbe.cpp
 * @brief Implementation of the non-blocking MQ-2 sampler.
 */
#include "GasProbe.h"

#include <Arduino.h>

#include "config.h"

void GasProbe::begin() {
  pinMode(config::pins::GAS_SENSOR, INPUT);
  analogSetPinAttenuation(config::pins::GAS_SENSOR, ADC_11db);
  resetWindow(millis());
}

bool GasProbe::update(uint32_t nowMs, GasWindow& out) {
  if (nowMs - lastSampleMs_ >= config::gas::SAMPLE_PERIOD_MS) {
    lastSampleMs_ = nowMs;
    // analogReadMilliVolts applies the factory eFuse calibration of the ADC.
    const uint32_t pinMv = analogReadMilliVolts(config::pins::GAS_SENSOR);
    sumPinMv_ += pinMv;
    if (pinMv < minPinMv_) minPinMv_ = pinMv;
    if (pinMv > maxPinMv_) maxPinMv_ = pinMv;
    ++count_;
  }

  if (nowMs - windowStartMs_ < config::gas::REPORT_PERIOD_MS || count_ == 0) {
    return false;
  }

  out.pinMv = static_cast<uint32_t>(sumPinMv_ / count_);
  out.aoMv = pinToAoMv(out.pinMv);
  out.aoPct = out.aoMv * config::gas::PERCENT_SCALE / config::gas::SUPPLY_MV;
  out.minAoMv = pinToAoMv(minPinMv_);
  out.maxAoMv = pinToAoMv(maxPinMv_);
  out.samples = count_;
  resetWindow(nowMs);
  return true;
}

uint32_t GasProbe::pinToAoMv(uint32_t pinMv) {
  return static_cast<uint32_t>(pinMv / config::gas::DIVIDER_GAIN +
                               config::gas::ROUNDING_OFFSET);
}

void GasProbe::resetWindow(uint32_t nowMs) {
  windowStartMs_ = nowMs;
  sumPinMv_ = 0;
  minPinMv_ = UINT32_MAX;
  maxPinMv_ = 0;
  count_ = 0;
}
