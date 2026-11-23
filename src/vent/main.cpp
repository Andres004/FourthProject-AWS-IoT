/**
 * @file main.cpp
 * @brief Board 1 (ventilation): declares its components and runs them.
 *
 * MQ-2 gas sensor and window servo. The ventilation controller (modes and
 * rules E1-E3, step D6) is added next; the shared setup and loop live in
 * SmartObjectApp.
 */
#include <Arduino.h>

#include "GasSensor.h"
#include "SmartObjectApp.h"
#include "WindowActuator.h"
#include "config_vent.h"
#include "secrets_vent.h"

namespace {

GasSensor gasSensor;
WindowActuator window;

// Add new sensors and actuators of this board here.
DeviceComponent* const components[] = {&gasSensor, &window};
constexpr size_t COMPONENT_COUNT = sizeof(components) / sizeof(components[0]);

const SmartObjectApp::Settings settings = {
    secrets::WIFI_SSID,
    secrets::WIFI_PASSWORD,
    {secrets::AWS_IOT_ENDPOINT, secrets::ROOT_CA, secrets::DEVICE_CERTIFICATE,
     secrets::DEVICE_PRIVATE_KEY, config::board::THING_SUFFIX},
};

SmartObjectApp app(settings, components, COMPONENT_COUNT);

}  // namespace

void setup() {
  app.begin();
}

void loop() {
  app.update(millis());
}
