/**
 * @file GasSensor.h
 * @brief MQ-2 gas and smoke sensor read through the 10k/15k divider on GPIO34.
 */
#pragma once

#include <stdint.h>

#include "DeviceComponent.h"

/**
 * @brief Non-blocking MQ-2 reader that publishes a 1 s averaged index.
 *
 * Samples the ADC every SAMPLE_PERIOD_MS with analogReadMilliVolts() (factory
 * eFuse calibration, 11 dB attenuation) and closes an averaged window every
 * AVERAGE_WINDOW_MS. From the window it rebuilds the AO voltage before the
 * divider (gas_mv) and the relative index gas_pct = AO / supply x 100, which
 * is NOT a concentration in ppm. Based on tools/mq2_probe (GasProbe).
 *
 * During WARMUP_MS after power-up it reports warming_up = true and the rest
 * of the firmware must not raise alarms (rule E2). After warm-up it asks for
 * a gas_changed report when gas_pct moves REPORT_DELTA_PCT or more from the
 * last value it asked to report.
 */
class GasSensor : public DeviceComponent {
 public:
  /** Configures the ADC pin and starts the warm-up period. */
  void begin() override;

  /** Samples when due and closes the averaging window; never blocks. */
  void update(uint32_t nowMs) override;

  /** Adds "gas_pct", "gas_mv" and "warming_up". */
  void fillReported(JsonObject reported) const override;

  /** @return Latest averaged index [% of supply], 0 before the first window. */
  float gasPct() const { return gasPct_; }

  /** @return true until the sensor heater has had WARMUP_MS to stabilize. */
  bool isWarmingUp() const { return warmingUp_; }

  /** @return true once at least one averaged window is available. */
  bool hasReading() const { return hasReading_; }

 private:
  void closeWindow(uint32_t nowMs);
  void resetWindow(uint32_t nowMs);
  static uint32_t pinToAoMv(uint32_t pinMv);
  static float aoMvToPct(uint32_t aoMv);

  uint32_t startMs_ = 0;
  uint32_t lastSampleMs_ = 0;
  uint32_t windowStartMs_ = 0;
  uint64_t sumPinMv_ = 0;
  uint32_t minPinMv_ = UINT32_MAX;
  uint32_t maxPinMv_ = 0;
  uint16_t count_ = 0;

  bool warmingUp_ = true;
  bool hasReading_ = false;
  uint32_t aoMv_ = 0;
  float gasPct_ = 0.0f;
  float lastRequestedPct_ = 0.0f;  // gas_pct of the last gas_changed request
};
