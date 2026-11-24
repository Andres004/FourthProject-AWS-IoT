/**
 * @file config.h
 * @brief Constants of the MQ-2 calibration probe: pins, divider and timing.
 *
 * Every physical value matches the P4 hardware (board 1, ESP32 DOIT DevKit V1).
 */
#pragma once

#include <stdint.h>

namespace config {

/** ESP32 GPIO numbers. */
namespace pins {
constexpr uint8_t GAS_SENSOR = 34;   // MQ-2 AO through the 10k/15k divider (ADC1)
constexpr uint8_t MARK_BUTTON = 0;   // On-board BOOT button, active LOW
constexpr uint8_t STATUS_LED = 32;   // Gas LED on board 1; here it only pulses per sample
}  // namespace pins

/** Serial output. */
namespace serial_log {
constexpr uint32_t BAUD_RATE = 115200;  // Serial Monitor speed [baud]
}  // namespace serial_log

/** Analog front end between the MQ-2 AO pin and GPIO34. */
namespace gas {
constexpr float DIVIDER_R_TOP_OHM = 10000.0f;     // AO -> GPIO34 resistor [ohm]
constexpr float DIVIDER_R_BOTTOM_OHM = 15000.0f;  // GPIO34 -> GND resistor [ohm]
// Pin voltage = AO voltage * gain = 15k / (10k + 15k) = 0.6 [-]
constexpr float DIVIDER_GAIN =
    DIVIDER_R_BOTTOM_OHM / (DIVIDER_R_TOP_OHM + DIVIDER_R_BOTTOM_OHM);
// MQ-2 supply: external 5 V / 2 A adapter, measured 5.337 V without load
// (UNI-T UT890D, 23/11). The loaded value is still pending (no multimeter).
constexpr float SUPPLY_MV = 5340.0f;         // [mV]
constexpr uint32_t SAMPLE_PERIOD_MS = 50;    // Between ADC reads [ms]
constexpr uint32_t REPORT_PERIOD_MS = 1000;  // Averaging window and print period [ms]
constexpr float PERCENT_SCALE = 100.0f;      // Ratio -> percent [-]
constexpr float ROUNDING_OFFSET = 0.5f;      // Round to nearest when casting [-]
}  // namespace gas

/** BOOT button used to stamp moments in the log (smoke on, smoke off...). */
namespace mark {
constexpr uint32_t DEBOUNCE_MS = 300;  // Ignore presses closer than this [ms]
}  // namespace mark

/** Status LED pulse after each sample. */
namespace status_led {
constexpr uint32_t PULSE_MS = 30;  // LED on time after each printed sample [ms]
}  // namespace status_led

}  // namespace config
