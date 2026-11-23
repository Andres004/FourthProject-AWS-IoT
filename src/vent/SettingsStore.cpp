/**
 * @file SettingsStore.cpp
 * @brief NVS read and write of mode and thresholds.
 */
#include "SettingsStore.h"

#include "EventLog.h"
#include "config_vent.h"

namespace store = config::settings_store;

namespace {
constexpr bool READ_ONLY = true;
constexpr bool READ_WRITE = false;
}  // namespace

bool SettingsStore::load(VentSettings& settings) {
  settings = VentSettings();  // Defaults first.
  if (!preferences_.begin(store::NAMESPACE, READ_ONLY)) {
    EventLog::record("SETTINGS_DEFAULTS reason=empty_nvs");
    return false;  // The namespace does not exist yet: first boot.
  }
  const bool complete = preferences_.isKey(store::KEY_MODE_AUTO) &&
                        preferences_.isKey(store::KEY_GAS_HIGH) &&
                        preferences_.isKey(store::KEY_GAS_LOW);
  VentSettings stored;
  if (complete) {
    stored.mode = preferences_.getBool(store::KEY_MODE_AUTO) ? VentMode::kAuto
                                                             : VentMode::kManual;
    stored.gasHighPct = preferences_.getUChar(store::KEY_GAS_HIGH);
    stored.gasLowPct = preferences_.getUChar(store::KEY_GAS_LOW);
  }
  preferences_.end();

  if (!complete ||
      !VentSettings::thresholdsValid(stored.gasLowPct, stored.gasHighPct)) {
    EventLog::record("SETTINGS_DEFAULTS reason=invalid_nvs");
    return false;
  }
  settings = stored;
  EventLog::recordf("SETTINGS_LOADED", "mode=%s gas_high_pct=%u gas_low_pct=%u",
                    settings.modeName(), settings.gasHighPct, settings.gasLowPct);
  return true;
}

void SettingsStore::save(const VentSettings& settings) {
  if (!preferences_.begin(store::NAMESPACE, READ_WRITE)) {
    EventLog::record("SETTINGS_SAVE_FAILED");
    return;
  }
  const bool modeAuto = settings.mode == VentMode::kAuto;
  // Each put is skipped when the value is already stored (no flash write).
  if (!preferences_.isKey(store::KEY_MODE_AUTO) ||
      preferences_.getBool(store::KEY_MODE_AUTO) != modeAuto) {
    preferences_.putBool(store::KEY_MODE_AUTO, modeAuto);
  }
  if (!preferences_.isKey(store::KEY_GAS_HIGH) ||
      preferences_.getUChar(store::KEY_GAS_HIGH) != settings.gasHighPct) {
    preferences_.putUChar(store::KEY_GAS_HIGH, settings.gasHighPct);
  }
  if (!preferences_.isKey(store::KEY_GAS_LOW) ||
      preferences_.getUChar(store::KEY_GAS_LOW) != settings.gasLowPct) {
    preferences_.putUChar(store::KEY_GAS_LOW, settings.gasLowPct);
  }
  preferences_.end();
  EventLog::recordf("SETTINGS_SAVED", "mode=%s gas_high_pct=%u gas_low_pct=%u",
                    settings.modeName(), settings.gasHighPct, settings.gasLowPct);
}
