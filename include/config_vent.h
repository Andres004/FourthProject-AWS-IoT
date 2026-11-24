/**
 * @file config_vent.h
 * @brief Constants of board 1 (ventilation): pins, Shadow keys and window servo.
 *
 * Board: ESP32 DOIT DevKit V1 (30 pins). Gas sensor and edge-logic constants
 * are added with GasSensor and VentilationController (steps D5 and D6).
 */
#pragma once

#include <stdint.h>

#include "config_common.h"

namespace config {

/** Identity of this board inside the smart home. */
namespace board {
constexpr char THING_SUFFIX[] = "-vent";  // Thing: smartloft-<LINK_CODE>-vent
}  // namespace board

/** ESP32 GPIO numbers (technical guide section 7.1). */
namespace pins {
constexpr uint8_t SERVO_SIGNAL = 13;  // SG90 PWM signal, cable "SERVO"
constexpr uint8_t GAS_SENSOR = 34;    // MQ-2 AO through the 10k/15k divider (ADC1), cable "MQ2"
constexpr uint8_t GAS_LED = 32;       // Gas indicator LED (D32 -> LED -> 220 ohm -> GND)
constexpr uint8_t BUZZER = 25;        // Reserved, not connected and not used yet
}  // namespace pins

/** Shadow document contract of the -vent Thing (technical guide section 5.3). */
namespace shadow_doc {
constexpr char KEY_WINDOW[] = "window";            // desired and reported: string
constexpr char KEY_SERVO_ANGLE[] = "servo_angle";  // reported: integer [deg]
constexpr char WINDOW_OPEN[] = "open";             // Valid value of KEY_WINDOW
constexpr char WINDOW_CLOSED[] = "closed";         // Valid value of KEY_WINDOW
constexpr char KEY_GAS_PCT[] = "gas_pct";          // reported: number 0.0-100.0 [% of supply]
constexpr char KEY_GAS_MV[] = "gas_mv";            // reported: integer 0-5000, AO voltage [mV]
constexpr char KEY_GAS_ALARM[] = "gas_alarm";      // reported: boolean
constexpr char KEY_WARMING_UP[] = "warming_up";    // reported: boolean
constexpr char KEY_MODE[] = "mode";                // desired and reported: string
constexpr char KEY_GAS_HIGH_PCT[] = "gas_high_pct";  // desired and reported: integer 1-99
constexpr char KEY_GAS_LOW_PCT[] = "gas_low_pct";    // desired and reported: integer 1-99
constexpr char MODE_AUTO[] = "auto";               // Valid value of KEY_MODE
constexpr char MODE_MANUAL[] = "manual";           // Valid value of KEY_MODE
}  // namespace shadow_doc

/**
 * MQ-2 analog front end and sampling (technical guide sections 5.8 and 7.2).
 * gas_pct is a relative index (AO voltage / MQ-2 supply x 100), NOT ppm.
 */
namespace gas {
constexpr float DIVIDER_R_TOP_OHM = 10000.0f;     // AO -> GPIO34 resistor [ohm]
constexpr float DIVIDER_R_BOTTOM_OHM = 15000.0f;  // GPIO34 -> GND resistor [ohm]
// Pin voltage = AO voltage * gain = 15k / (10k + 15k) = 0.6 [-]
constexpr float DIVIDER_GAIN =
    DIVIDER_R_BOTTOM_OHM / (DIVIDER_R_TOP_OHM + DIVIDER_R_BOTTOM_OHM);
// MQ-2 supply: external 5 V / 2 A source, measured WITHOUT load (5.337 V at
// the jack, UNI-T UT890D, 23/11). Same value as tools/mq2_probe, so the
// thresholds of the calibration (A10) mean the same here. The loaded value
// is still pending (no multimeter).
constexpr float SUPPLY_MV = 5340.0f;            // [mV]
constexpr uint32_t SAMPLE_PERIOD_MS = 50;       // Between ADC reads [ms]
constexpr uint32_t AVERAGE_WINDOW_MS = 1000;    // Averaging window; one reading per window [ms]
// Time after power-up without alarms or automatic actions (rule E2). A10/M4:
// a cold start after 15 min off showed no transient; 60 s is kept as margin.
constexpr uint32_t WARMUP_MS = 60000;           // [ms]
// A reading that moves this much from the last reported one sends gas_changed.
constexpr float REPORT_DELTA_PCT = 3.0f;        // [percentage points]
constexpr uint32_t AO_MAX_MV = 5000;            // Upper bound of gas_mv [mV]
constexpr float PERCENT_SCALE = 100.0f;         // Ratio -> percent [-]
constexpr float PERCENT_MAX = 100.0f;           // Upper bound of gas_pct [%]
constexpr float DECIMAL_SCALE = 10.0f;          // gas_pct is reported with 1 decimal [-]
constexpr float ROUNDING_OFFSET = 0.5f;         // Round to nearest when casting [-]
}  // namespace gas

/**
 * Defaults of the automatic logic, used when the NVS is empty (first boot).
 * Thresholds from the MQ-2 calibration (A10 / M5): clean air < 4.4 % (ADC
 * floor, 720 flat samples); 11 lighter-gas cycles peaked at 9-73 %. The
 * 7-point band is larger than the noise, so the alarm does not oscillate.
 */
namespace vent_defaults {
constexpr bool MODE_AUTO = true;      // true: "auto", false: "manual"
constexpr uint8_t GAS_HIGH_PCT = 15;  // Alarm on at gas_pct >= this [%]
constexpr uint8_t GAS_LOW_PCT = 8;    // Alarm off at gas_pct <= this [%]
constexpr uint8_t THRESHOLD_MIN_PCT = 1;   // Lowest valid threshold [%]
constexpr uint8_t THRESHOLD_MAX_PCT = 99;  // Highest valid threshold [%]
}  // namespace vent_defaults

/**
 * Simulated gas readings, only in vent_local_test (test B02): sending
 * {"state":{"sim_gas_pct":45}} replaces the ADC reading and ends the warm-up,
 * so the hysteresis can be tested without smoke; a negative value goes back
 * to the real sensor. Production builds ignore this key.
 */
namespace gas_simulation {
constexpr char KEY_SIM_GAS_PCT[] = "sim_gas_pct";  // number 0-100, or < 0 to stop
}  // namespace gas_simulation

/**
 * Gas indicator LED on D32: off = normal air, on = gas alarm, slow blink =
 * sensor warming up. It shows the edge decision even when the window does
 * not move (manual mode) and works offline; it is not an actuator.
 */
namespace gas_led {
constexpr uint32_t WARMUP_BLINK_HALF_PERIOD_MS = 1000;  // Slow blink while warming up [ms]
}  // namespace gas_led

/** NVS (Preferences) storage of mode and thresholds (rule E3). */
namespace settings_store {
constexpr char NAMESPACE[] = "smartloft";  // Preferences namespace (max 15 chars)
constexpr char KEY_MODE_AUTO[] = "mode_auto";  // bool
constexpr char KEY_GAS_HIGH[] = "gas_high";    // uint8_t [%]
constexpr char KEY_GAS_LOW[] = "gas_low";      // uint8_t [%]
}  // namespace settings_store

/**
 * Events of the -vent Thing and their report priority (higher wins when two
 * events fall inside the minimum report interval).
 */
namespace vent_events {
constexpr char GAS_ALARM_ON[] = "gas_alarm_on";
constexpr char GAS_ALARM_OFF[] = "gas_alarm_off";
constexpr char WINDOW_CHANGED[] = "window_changed";
constexpr char MODE_CHANGED[] = "mode_changed";
constexpr char THRESHOLDS_CHANGED[] = "thresholds_changed";
constexpr char GAS_CHANGED[] = "gas_changed";

constexpr uint8_t PRIORITY_GAS_ALARM = 50;   // gas_alarm_on / gas_alarm_off
constexpr uint8_t PRIORITY_WINDOW = 40;      // window_changed
constexpr uint8_t PRIORITY_MODE = 30;        // mode_changed
constexpr uint8_t PRIORITY_THRESHOLDS = 20;  // thresholds_changed
constexpr uint8_t PRIORITY_GAS_CHANGED = 10; // gas_changed
}  // namespace vent_events

/** SG90 servo that moves the window. */
namespace window {
constexpr int PWM_FREQUENCY_HZ = 50;      // Standard servo frequency [Hz]
constexpr int PULSE_MIN_US = 500;         // Pulse width at 0 deg [us]
constexpr int PULSE_MAX_US = 2400;        // Pulse width at 180 deg [us]
constexpr int CLOSED_ANGLE_DEG = 0;       // Window closed; calibrate on the model [deg]
constexpr int OPEN_ANGLE_DEG = 90;        // Window open; calibrate on the model [deg]
constexpr uint32_t SETTLE_TIME_MS = 400;  // Time allowed to finish a move [ms]
}  // namespace window

}  // namespace config
