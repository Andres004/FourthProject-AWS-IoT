/**
 * @file SettingsStore.h
 * @brief Keeps mode and thresholds in the ESP32 NVS (rule E3).
 */
#pragma once

#include <Preferences.h>

#include "VentSettings.h"

/**
 * @brief Loads and saves VentSettings with Preferences.
 *
 * If the board restarts without Internet, rule E1 keeps working with the
 * last mode and thresholds applied instead of the compiled defaults. Values
 * are written only when they change, to avoid wearing the flash.
 */
class SettingsStore {
 public:
  /**
   * Reads the stored settings.
   * @param[out] settings Stored values, or the defaults when the NVS is
   * empty or holds invalid values.
   * @return true when valid stored values were found.
   */
  bool load(VentSettings& settings);

  /** Writes the settings that differ from the stored ones. */
  void save(const VentSettings& settings);

 private:
  Preferences preferences_;
};
