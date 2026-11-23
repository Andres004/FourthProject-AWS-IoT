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
}  // namespace pins

/** Shadow document contract of the -vent Thing (technical guide section 5.3). */
namespace shadow_doc {
constexpr char KEY_WINDOW[] = "window";            // desired and reported: string
constexpr char KEY_SERVO_ANGLE[] = "servo_angle";  // reported: integer [deg]
constexpr char WINDOW_OPEN[] = "open";             // Valid value of KEY_WINDOW
constexpr char WINDOW_CLOSED[] = "closed";         // Valid value of KEY_WINDOW
}  // namespace shadow_doc

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
