/**
 * @file VentilationController.cpp
 * @brief Alarm hysteresis, rule E1 and validation of voice/Cloud commands.
 */
#include "VentilationController.h"

#include <string.h>

#include "EventLog.h"
#include "config_vent.h"

namespace doc = config::shadow_doc;
namespace ev = config::vent_events;
namespace report_doc = config::report_doc;

VentilationController::VentilationController(const GasSensor& gas,
                                             WindowActuator& window,
                                             SettingsStore& store)
    : gas_(gas), window_(window), store_(store) {}

void VentilationController::begin() {
  store_.load(settings_);  // Falls back to the defaults on the first boot.
}

void VentilationController::update(uint32_t nowMs) {
  (void)nowMs;
  if (gas_.isWarmingUp() || !gas_.hasReading()) {
    return;  // E2: no alarm and no automatic action while warming up.
  }
  updateAlarm();
  if (settings_.mode == VentMode::kAuto) {
    enforceEdgeRule();
  }
}

void VentilationController::fillReported(JsonObject reported) const {
  reported[doc::KEY_GAS_ALARM] = gasAlarm_;
  reported[doc::KEY_MODE] = settings_.modeName();
  reported[doc::KEY_GAS_HIGH_PCT] = settings_.gasHighPct;
  reported[doc::KEY_GAS_LOW_PCT] = settings_.gasLowPct;
}

void VentilationController::applyDesired(JsonObjectConst desired,
                                         DesiredSource source) {
  const char* origin = commandOrigin(desired, source);
  // Mode first, so "manual + open the window" in one document is accepted.
  const bool modeSeen = applyMode(desired, origin);
  const bool thresholdsSeen = applyThresholds(desired, origin);
  const bool windowSeen = applyWindow(desired, origin);
  if (modeSeen || thresholdsSeen || windowSeen) {
    markDesiredConsumed(report_doc::KEY_CMD_ORIGIN);
  }
}

bool VentilationController::applyMode(JsonObjectConst desired,
                                      const char* origin) {
  JsonVariantConst value = desired[doc::KEY_MODE];
  if (value.isNull()) {
    return false;
  }
  const char* requested = value.as<const char*>();
  VentMode mode;
  if (requested != nullptr && strcmp(requested, doc::MODE_AUTO) == 0) {
    mode = VentMode::kAuto;
  } else if (requested != nullptr && strcmp(requested, doc::MODE_MANUAL) == 0) {
    mode = VentMode::kManual;
  } else {
    EventLog::recordf("INVALID_VALUE", "mode=%s",
                      requested != nullptr ? requested : "<not a string>");
    requestConfirmation();
    return true;
  }

  if (mode == settings_.mode) {
    requestConfirmation();  // Already in that mode; the report clears the delta.
    return true;
  }
  settings_.mode = mode;
  store_.save(settings_);  // E3
  if (mode == VentMode::kAuto) {
    // A pending window command must not undo what E1 decides from now on.
    markDesiredConsumed(doc::KEY_WINDOW);
  }
  EventLog::recordf("MODE_APPLIED", "mode=%s origin=%s", settings_.modeName(),
                    origin);
  requestReport(ev::MODE_CHANGED, ev::PRIORITY_MODE, origin);
  return true;
}

bool VentilationController::applyThresholds(JsonObjectConst desired,
                                            const char* origin) {
  JsonVariantConst high = desired[doc::KEY_GAS_HIGH_PCT];
  JsonVariantConst low = desired[doc::KEY_GAS_LOW_PCT];
  if (high.isNull() && low.isNull()) {
    return false;
  }
  const bool typesOk = (high.isNull() || high.is<int>()) &&
                       (low.isNull() || low.is<int>());
  const int newHigh = high.isNull() ? settings_.gasHighPct : high.as<int>();
  const int newLow = low.isNull() ? settings_.gasLowPct : low.as<int>();
  if (!typesOk || !VentSettings::thresholdsValid(newLow, newHigh)) {
    EventLog::recordf("COMMAND_REJECTED",
                      "reason=invalid_thresholds gas_high_pct=%d gas_low_pct=%d",
                      newHigh, newLow);
    requestConfirmation();
    return true;
  }

  if (newHigh == settings_.gasHighPct && newLow == settings_.gasLowPct) {
    requestConfirmation();
    return true;
  }
  settings_.gasHighPct = static_cast<uint8_t>(newHigh);
  settings_.gasLowPct = static_cast<uint8_t>(newLow);
  store_.save(settings_);  // E3
  EventLog::recordf("THRESHOLDS_APPLIED",
                    "gas_high_pct=%u gas_low_pct=%u origin=%s",
                    settings_.gasHighPct, settings_.gasLowPct, origin);
  requestReport(ev::THRESHOLDS_CHANGED, ev::PRIORITY_THRESHOLDS, origin);
  return true;
}

bool VentilationController::applyWindow(JsonObjectConst desired,
                                        const char* origin) {
  JsonVariantConst value = desired[doc::KEY_WINDOW];
  if (value.isNull()) {
    return false;
  }
  // Accepted or not, the command is consumed: it must not stay in desired.
  markDesiredConsumed(doc::KEY_WINDOW);

  const char* requested = value.as<const char*>();
  bool open;
  if (requested != nullptr && strcmp(requested, doc::WINDOW_OPEN) == 0) {
    open = true;
  } else if (requested != nullptr && strcmp(requested, doc::WINDOW_CLOSED) == 0) {
    open = false;
  } else {
    EventLog::recordf("INVALID_VALUE", "window=%s",
                      requested != nullptr ? requested : "<not a string>");
    requestConfirmation();
    return true;
  }

  if (settings_.mode == VentMode::kAuto) {
    EventLog::recordf("COMMAND_REJECTED", "reason=auto_mode window=%s",
                      requested);
    requestConfirmation();
    return true;
  }
  if (!open && gasAlarm_) {
    EventLog::recordf("COMMAND_REJECTED",
                      "reason=gas_alarm window=closed gas_pct=%.1f "
                      "gas_high_pct=%u",
                      gas_.gasPct(), settings_.gasHighPct);
    requestConfirmation();
    return true;
  }

  if (!window_.moveTo(open, origin) && !window_.isMoving()) {
    requestConfirmation();  // Already there; the report clears the delta.
  }
  return true;
}

void VentilationController::updateAlarm() {
  const float gasPct = gas_.gasPct();
  const bool automatic = settings_.mode == VentMode::kAuto;
  // In "auto" the window follows the alarm, so its cause is the edge rule.
  const char* origin = automatic ? report_doc::ORIGIN_EDGE : nullptr;

  if (!gasAlarm_ && gasPct >= settings_.gasHighPct) {
    gasAlarm_ = true;
    EventLog::recordf("GAS_ALARM_ON", "gas_pct=%.1f gas_high_pct=%u mode=%s",
                      gasPct, settings_.gasHighPct, settings_.modeName());
    requestReport(ev::GAS_ALARM_ON, ev::PRIORITY_GAS_ALARM, origin);
  } else if (gasAlarm_ && gasPct <= settings_.gasLowPct) {
    gasAlarm_ = false;
    EventLog::recordf("GAS_ALARM_OFF", "gas_pct=%.1f gas_low_pct=%u mode=%s",
                      gasPct, settings_.gasLowPct, settings_.modeName());
    requestReport(ev::GAS_ALARM_OFF, ev::PRIORITY_GAS_ALARM, origin);
  }
}

void VentilationController::enforceEdgeRule() {
  // E1: in "auto" the window is open exactly while the alarm is on. Checked
  // on every loop, so it also applies right after switching to "auto".
  if (window_.moveTo(gasAlarm_, report_doc::ORIGIN_EDGE)) {
    EventLog::recordf("EDGE_ACTION", "window=%s gas_pct=%.1f",
                      gasAlarm_ ? doc::WINDOW_OPEN : doc::WINDOW_CLOSED,
                      gas_.gasPct());
  }
}
