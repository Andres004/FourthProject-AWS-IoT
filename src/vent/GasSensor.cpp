/**
 * @file GasSensor.cpp
 * @brief MQ-2 sampling, averaging, warm-up and gas_changed reports.
 */
#include "GasSensor.h"

#include <Arduino.h>
#include <math.h>

#include "EventLog.h"
#include "config_vent.h"

namespace gas = config::gas;

void GasSensor::begin() {
  pinMode(config::pins::GAS_SENSOR, INPUT);
  analogSetPinAttenuation(config::pins::GAS_SENSOR, ADC_11db);
  startMs_ = millis();
  resetWindow(startMs_);
  EventLog::recordf("GAS_WARMUP_START", "warmup_ms=%lu supply_mv=%.0f",
                    static_cast<unsigned long>(gas::WARMUP_MS), gas::SUPPLY_MV);
}

void GasSensor::update(uint32_t nowMs) {
  if (nowMs - lastSampleMs_ >= gas::SAMPLE_PERIOD_MS) {
    lastSampleMs_ = nowMs;
    const uint32_t pinMv = analogReadMilliVolts(config::pins::GAS_SENSOR);
    sumPinMv_ += pinMv;
    if (pinMv < minPinMv_) {
      minPinMv_ = pinMv;
    }
    if (pinMv > maxPinMv_) {
      maxPinMv_ = pinMv;
    }
    ++count_;
  }

  if (nowMs - windowStartMs_ >= gas::AVERAGE_WINDOW_MS && count_ > 0) {
    closeWindow(nowMs);
  }
}

void GasSensor::fillReported(JsonObject reported) const {
  namespace doc = config::shadow_doc;
  reported[doc::KEY_GAS_PCT] = gasPct_;
  reported[doc::KEY_GAS_MV] = aoMv_;
  reported[doc::KEY_WARMING_UP] = warmingUp_;
}

void GasSensor::closeWindow(uint32_t nowMs) {
  const uint32_t pinMv = static_cast<uint32_t>(sumPinMv_ / count_);
  aoMv_ = pinToAoMv(pinMv);
  gasPct_ = aoMvToPct(aoMv_);
  if (simulated_) {
    gasPct_ = simPct_;
    aoMv_ = static_cast<uint32_t>(simPct_ * gas::SUPPLY_MV / gas::PERCENT_SCALE +
                                  gas::ROUNDING_OFFSET);
  }
  hasReading_ = true;

  EventLog::recordf("GAS_SAMPLE",
                    "pin_mv=%lu ao_mv=%lu gas_pct=%.1f min_mv=%lu max_mv=%lu "
                    "n=%u warming_up=%d simulated=%d",
                    static_cast<unsigned long>(pinMv),
                    static_cast<unsigned long>(aoMv_), gasPct_,
                    static_cast<unsigned long>(pinToAoMv(minPinMv_)),
                    static_cast<unsigned long>(pinToAoMv(maxPinMv_)), count_,
                    warmingUp_ ? 1 : 0, simulated_ ? 1 : 0);
  resetWindow(nowMs);

  namespace ev = config::vent_events;
  if (warmingUp_) {
    if (!simulated_ && nowMs - startMs_ < gas::WARMUP_MS) {
      return;  // Readings during warm-up are not reliable: no gas_changed.
    }
    warmingUp_ = false;
    lastRequestedPct_ = gasPct_;
    EventLog::recordf("GAS_READY", "gas_pct=%.1f", gasPct_);
    requestReport(ev::GAS_CHANGED, ev::PRIORITY_GAS_CHANGED);
    return;
  }

  if (fabsf(gasPct_ - lastRequestedPct_) >= gas::REPORT_DELTA_PCT) {
    lastRequestedPct_ = gasPct_;
    requestReport(ev::GAS_CHANGED, ev::PRIORITY_GAS_CHANGED);
  }
}

#ifdef LOCAL_TEST_MODE
void GasSensor::applyDesired(JsonObjectConst desired, DesiredSource source) {
  (void)source;
  JsonVariantConst value = desired[config::gas_simulation::KEY_SIM_GAS_PCT];
  if (value.isNull()) {
    return;
  }
  const float pct = value.as<float>();
  simulated_ = pct >= 0.0f;
  simPct_ = pct > gas::PERCENT_MAX ? gas::PERCENT_MAX : pct;
  EventLog::recordf("GAS_SIMULATION", "active=%d gas_pct=%.1f",
                    simulated_ ? 1 : 0, simPct_);
}
#endif

void GasSensor::resetWindow(uint32_t nowMs) {
  windowStartMs_ = nowMs;
  sumPinMv_ = 0;
  minPinMv_ = UINT32_MAX;
  maxPinMv_ = 0;
  count_ = 0;
}

uint32_t GasSensor::pinToAoMv(uint32_t pinMv) {
  const uint32_t aoMv =
      static_cast<uint32_t>(pinMv / gas::DIVIDER_GAIN + gas::ROUNDING_OFFSET);
  return aoMv > gas::AO_MAX_MV ? gas::AO_MAX_MV : aoMv;
}

float GasSensor::aoMvToPct(uint32_t aoMv) {
  float pct = aoMv * gas::PERCENT_SCALE / gas::SUPPLY_MV;
  if (pct > gas::PERCENT_MAX) {
    pct = gas::PERCENT_MAX;
  }
  // One decimal is enough for a relative index and keeps reports short.
  return floorf(pct * gas::DECIMAL_SCALE + gas::ROUNDING_OFFSET) /
         gas::DECIMAL_SCALE;
}
