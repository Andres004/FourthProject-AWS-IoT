/**
 * @file ZoneLight.h
 * @brief One zone light (a white LED) controlled through its Shadow attribute.
 */
#pragma once

#include <stdint.h>

#include "DeviceComponent.h"

/**
 * @brief LED of one zone of the studio, driven by "light_<zone>".
 *
 * Lights are changed only by voice, so there is no conflict with automatic
 * logic: the light_<zone> value stays in desired (it is the user's setting,
 * restored after a restart through /get) and only desired.cmd_origin is
 * cleared once the command is applied (technical guide section 5.4).
 */
class ZoneLight : public DeviceComponent {
 public:
  /**
   * @param zoneName Name used in the logs, e.g. "kitchen".
   * @param shadowKey Shadow attribute, e.g. "light_kitchen".
   * @param pin GPIO that drives the LED.
   * The strings must outlive the object (use the constants of config_lights.h).
   */
  ZoneLight(const char* zoneName, const char* shadowKey, uint8_t pin);

  /** Configures the pin and starts with the light off. */
  void begin() override;

  /** Nothing to do over time: the LED changes only on commands. */
  void update(uint32_t nowMs) override;

  /** Adds "light_<zone>": "on" or "off". */
  void fillReported(JsonObject reported) const override;

  /** Validates and applies "light_<zone>", when present. */
  void applyDesired(JsonObjectConst desired, DesiredSource source) override;

 private:
  void write(bool on);

  const char* zoneName_;
  const char* shadowKey_;
  uint8_t pin_;
  bool on_ = false;
};
