/**
 * @file PresenceSensor.h
 * @brief AM312 PIR at the entrance; informative only, it drives nothing.
 */
#pragma once

#include "DeviceComponent.h"

/**
 * @brief Detects a person at the entrance with an AM312 PIR sensor.
 *
 * A PIR detects movement, not stillness, so presence stays active for a hold
 * time after the last detected movement. Readings are ignored during warm-up.
 * Each edge is reported as presence_detected / presence_cleared.
 */
class PresenceSensor : public DeviceComponent {
 public:
  /** Configures the input pin and starts the warm-up period. */
  void begin() override;

  /** Polls the sensor and updates the presence state. */
  void update(uint32_t nowMs) override;

  /** Adds "presence". */
  void fillReported(JsonObject reported) const override;

 private:
  void setPresence(bool presence);

  bool warmedUp_ = false;
  bool presence_ = false;
  uint32_t startMs_ = 0;
  uint32_t lastPollMs_ = 0;
  uint32_t lastMotionMs_ = 0;
};
