/**
 * @file GasIndicatorLed.h
 * @brief LED on D32 that shows the gas state of board 1.
 */
#pragma once

#include <stdint.h>

#include "DeviceComponent.h"
#include "GasSensor.h"
#include "VentilationController.h"

/**
 * @brief Off = normal air, on = gas alarm, slow blink = sensor warming up.
 *
 * It makes the edge decision visible in the demo even when the window does
 * not move (manual mode), helps during the calibration and works without
 * Internet. It is an indicator, not an actuator: it reports nothing.
 */
class GasIndicatorLed : public DeviceComponent {
 public:
  GasIndicatorLed(const GasSensor& gas, const VentilationController& ventilation);

  /** Configures the pin, LED off. */
  void begin() override;

  /** Follows the warm-up and the alarm without blocking. */
  void update(uint32_t nowMs) override;

  /** The LED is not part of the Shadow document. */
  void fillReported(JsonObject reported) const override;

 private:
  void write(bool on);

  const GasSensor& gas_;
  const VentilationController& ventilation_;
  bool on_ = false;
  uint32_t lastToggleMs_ = 0;
};
