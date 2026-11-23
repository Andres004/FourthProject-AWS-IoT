/**
 * @file GasProbe.h
 * @brief Non-blocking MQ-2 sampler that averages the ADC over a fixed window.
 */
#pragma once

#include <stdint.h>

/** One averaged window of MQ-2 readings, expressed at the AO pin. */
struct GasWindow {
  uint32_t pinMv;    ///< Mean voltage measured at GPIO34 [mV]
  uint32_t aoMv;     ///< Mean AO voltage rebuilt through the divider [mV]
  float aoPct;       ///< Mean AO voltage / MQ-2 supply voltage [%]
  uint32_t minAoMv;  ///< Lowest single AO sample in the window [mV]
  uint32_t maxAoMv;  ///< Highest single AO sample in the window [mV]
  uint16_t samples;  ///< ADC reads averaged in the window
};

/**
 * @brief Reads the MQ-2 analog output every SAMPLE_PERIOD_MS using millis()
 * and closes an averaged window every REPORT_PERIOD_MS.
 */
class GasProbe {
 public:
  /** Configures the ADC pin (11 dB attenuation, about 0-3.1 V range). */
  void begin();

  /**
   * @brief Takes a sample when due; never blocks.
   * @param nowMs Current millis().
   * @param out Filled with the finished window when the method returns true.
   * @return true when a full window has just been closed.
   */
  bool update(uint32_t nowMs, GasWindow& out);

 private:
  /** Converts a GPIO34 voltage into the AO voltage before the divider. */
  static uint32_t pinToAoMv(uint32_t pinMv);

  /** Clears the accumulators for a new window. */
  void resetWindow(uint32_t nowMs);

  uint32_t lastSampleMs_ = 0;
  uint32_t windowStartMs_ = 0;
  uint64_t sumPinMv_ = 0;
  uint32_t minPinMv_ = UINT32_MAX;
  uint32_t maxPinMv_ = 0;
  uint16_t count_ = 0;
};
