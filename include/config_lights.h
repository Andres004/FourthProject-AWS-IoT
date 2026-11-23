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
}  // namespace shadow_doc

/** AM312 PIR presence sensor. */
namespace pir {
constexpr uint32_t POLL_PERIOD_MS = 50;       // Between digital reads [ms]
constexpr uint32_t WARMUP_MS = 30000;         // Output ignored after boot [ms]
constexpr uint32_t PRESENCE_HOLD_MS = 10000;  // Presence kept after last motion [ms]
}  // namespace pir

}  // namespace config
