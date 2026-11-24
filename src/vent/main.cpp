/**
 * @file main.cpp
 * @brief Board 1 (ventilation): declares its components and runs them.
 *
 * MQ-2 gas sensor, window servo, the ventilation controller (modes and edge
 * rules E1-E3) and the gas indicator LED on D32. The shared setup and loop
 * live in SmartObjectApp.
 */
#include <Arduino.h>

#include "GasIndicatorLed.h"
#include "GasSensor.h"
#include "SettingsStore.h"
#include "SmartObjectApp.h"
#include "VentilationController.h"
#include "WindowActuator.h"
#include "config_vent.h"
#include "secrets_vent.h"

namespace {

GasSensor gasSensor;
WindowActuator window;
SettingsStore settingsStore;
VentilationController ventilation(gasSensor, window, settingsStore);
GasIndicatorLed gasLed(gasSensor, ventilation);

// Add new sensors and actuators of this board here. The controller goes
// after the gas sensor, so each loop decides with the newest reading, and
// the indicator goes last, so it shows that decision in the same loop.
DeviceComponent* const components[] = {&gasSensor, &window, &ventilation,
                                       &gasLed};
constexpr size_t COMPONENT_COUNT = sizeof(components) / sizeof(components[0]);

const SmartObjectApp::Settings settings = {
    secrets::WIFI_SSID,
    secrets::WIFI_PASSWORD,
    {secrets::AWS_IOT_ENDPOINT, secrets::ROOT_CA, secrets::DEVICE_CERTIFICATE,
     secrets::DEVICE_PRIVATE_KEY, config::board::THING_SUFFIX},
    // GPIO32 of this board is the gas indicator, not a connection LED.
    config::status_led::NO_LED,
};

SmartObjectApp app(settings, components, COMPONENT_COUNT);

}  // namespace

void setup() {
  app.begin();
}

void loop() {
  app.update(millis());
}
