/**
 * @file VentilationController.h
 * @brief Modes, thresholds and edge rules E1-E3 of the ventilation board.
 */
#pragma once

#include <stdint.h>

#include "DeviceComponent.h"
#include "GasSensor.h"
#include "SettingsStore.h"
#include "VentSettings.h"
#include "WindowActuator.h"

/**
 * @brief Owns mode, thresholds and gas_alarm, and decides who moves the window.
 *
 * Edge rules (technical guide section 5.5):
 * - E1: in "auto", gas_alarm turns on at gas_pct >= gas_high_pct and off at
 *   gas_pct <= gas_low_pct (hysteresis); the window follows the alarm, with
 *   origin "edge". It works without Internet.
 * - E2: while the sensor warms up there is no alarm and no automatic action.
 * - E3: mode and thresholds are saved in the NVS when applied, so E1 keeps
 *   the last values after a restart without Internet.
 *
 * Voice / automatic coexistence (section 5.6), applied again here as defense
 * in depth after the skill: desired.window is rejected in "auto", "close the
 * window" is rejected while gas_alarm is on, and invalid thresholds are
 * rejected. desired.window and desired.cmd_origin are always consumed (deleted
 * by the next report), and switching to "auto" also deletes desired.window,
 * so a stale command can never undo what E1 did. Mode and thresholds stay in
 * desired as the user's settings.
 *
 * In "manual" the gas is still measured and gas_alarm is still reported, so
 * the Cloud rule C1 can count the alarms.
 */
class VentilationController : public DeviceComponent {
 public:
  VentilationController(const GasSensor& gas, WindowActuator& window,
                        SettingsStore& store);

  /** Loads mode and thresholds from the NVS (E3). */
  void begin() override;

  /** Evaluates the alarm hysteresis and, in "auto", rule E1. */
  void update(uint32_t nowMs) override;

  /** Adds "gas_alarm", "mode", "gas_high_pct" and "gas_low_pct". */
  void fillReported(JsonObject reported) const override;

  /** Applies "mode", "gas_high_pct", "gas_low_pct" and "window", in that order. */
  void applyDesired(JsonObjectConst desired, DesiredSource source) override;

 private:
  bool applyMode(JsonObjectConst desired, const char* origin);
  bool applyThresholds(JsonObjectConst desired, const char* origin);
  bool applyWindow(JsonObjectConst desired, const char* origin);
  void updateAlarm();
  void enforceEdgeRule();

  const GasSensor& gas_;
  WindowActuator& window_;
  SettingsStore& store_;
  VentSettings settings_;
  bool gasAlarm_ = false;
};
