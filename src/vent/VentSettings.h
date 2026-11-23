/**
 * @file VentSettings.h
 * @brief Mode and thresholds of the automatic ventilation logic.
 */
#pragma once

#include <stdint.h>

#include "config_vent.h"

/** Ventilation mode (technical guide section 5.5). */
enum class VentMode {
  kAuto,    ///< The board opens and closes the window by gas (rule E1)
  kManual,  ///< The window moves only by voice
};

/** Parameters that the user changes by voice and the board keeps in NVS. */
struct VentSettings {
  VentMode mode = config::vent_defaults::MODE_AUTO ? VentMode::kAuto
                                                   : VentMode::kManual;
  uint8_t gasHighPct = config::vent_defaults::GAS_HIGH_PCT;  ///< Alarm on [%]
  uint8_t gasLowPct = config::vent_defaults::GAS_LOW_PCT;    ///< Alarm off [%]

  /** @return true when both thresholds are 1-99 and low < high. */
  static bool thresholdsValid(int lowPct, int highPct) {
    namespace def = config::vent_defaults;
    return lowPct >= def::THRESHOLD_MIN_PCT && highPct <= def::THRESHOLD_MAX_PCT &&
           lowPct < highPct;
  }

  /** @return Shadow value of the mode ("auto" or "manual"). */
  const char* modeName() const {
    return mode == VentMode::kAuto ? config::shadow_doc::MODE_AUTO
                                   : config::shadow_doc::MODE_MANUAL;
  }
};
