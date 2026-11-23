/**
 * @file config_lights.h
 * @brief Constants of board 2 (lights and entrance): pins, PIR and Shadow keys.
 *
 * Board: ESP32-DevKitC (38 pins). The five zone lights are added with
 * ZoneLight (step D3); their pins are already fixed here.
 */
#pragma once

#include <stdint.h>

#include "config_common.h"

namespace config {

/** Identity of this board inside the smart home. */
namespace board {
constexpr char THING_SUFFIX[] = "-lights";  // Thing: smartloft-<LINK_CODE>-lights
}  // namespace board

/** ESP32 GPIO numbers (technical guide section 7.1). */
namespace pins {
constexpr uint8_t LIGHT_KITCHEN = 22;   // Cable "L-COC"
constexpr uint8_t LIGHT_LIVING = 21;    // Cable "L-SAL"
constexpr uint8_t LIGHT_DINING = 23;    // Cable "L-COM" (was "L-ENT")
constexpr uint8_t LIGHT_BATHROOM = 19;  // Cable "L-BAN"
constexpr uint8_t LIGHT_BEDROOM = 18;   // Cable "L-HAB"
constexpr uint8_t PIR_OUTPUT = 26;      // AM312 digital output (3.3 V, active HIGH)
}  // namespace pins

/** Shadow document contract of the -lights Thing (technical guide section 5.4). */
namespace shadow_doc {
constexpr char KEY_PRESENCE[] = "presence";  // reported: boolean
// One flat attribute per zone, desired and reported, value LIGHT_ON/LIGHT_OFF.
constexpr char KEY_LIGHT_KITCHEN[] = "light_kitchen";
constexpr char KEY_LIGHT_LIVING[] = "light_living";
constexpr char KEY_LIGHT_DINING[] = "light_dining";
constexpr char KEY_LIGHT_BATHROOM[] = "light_bathroom";
constexpr char KEY_LIGHT_BEDROOM[] = "light_bedroom";
constexpr char LIGHT_ON[] = "on";    // Valid value of every KEY_LIGHT_*
constexpr char LIGHT_OFF[] = "off";  // Valid value of every KEY_LIGHT_*
}  // namespace shadow_doc

/** Zone names used in the logs (zone=... in LIGHT_APPLIED). */
namespace zones {
constexpr char KITCHEN[] = "kitchen";
constexpr char LIVING[] = "living";
constexpr char DINING[] = "dining";
constexpr char BATHROOM[] = "bathroom";
constexpr char BEDROOM[] = "bedroom";
}  // namespace zones

/** White LEDs that represent the zone lights (220 ohm, active HIGH). */
namespace light {
constexpr bool ACTIVE_HIGH = true;  // GPIO HIGH turns the LED on
}  // namespace light

/**
 * Events of the -lights Thing and their report priority (higher wins when
 * two events fall inside the minimum report interval).
 */
namespace lights_events {
constexpr char LIGHT_CHANGED[] = "light_changed";
constexpr char PRESENCE_DETECTED[] = "presence_detected";  // Rising edge of presence
constexpr char PRESENCE_CLEARED[] = "presence_cleared";    // Falling edge of presence

constexpr uint8_t PRIORITY_LIGHT = 30;              // light_changed
constexpr uint8_t PRIORITY_PRESENCE_DETECTED = 20;  // presence_detected
constexpr uint8_t PRIORITY_PRESENCE_CLEARED = 10;   // presence_cleared
}  // namespace lights_events

/** AM312 PIR presence sensor. */
namespace pir {
constexpr uint32_t POLL_PERIOD_MS = 50;       // Between digital reads [ms]
constexpr uint32_t WARMUP_MS = 30000;         // Output ignored after boot [ms]
constexpr uint32_t PRESENCE_HOLD_MS = 10000;  // Presence kept after last motion [ms]
}  // namespace pir

}  // namespace config
