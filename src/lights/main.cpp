/**
 * @file main.cpp
 * @brief Board 2 (lights and entrance): declares its components and runs them.
 *
 * The five ZoneLight components are added in step D3; the shared setup and
 * loop live in SmartObjectApp.
 */
#include <Arduino.h>

#include "PresenceSensor.h"
#include "SmartObjectApp.h"
#include "config_lights.h"
#include "secrets_lights.h"

namespace {

PresenceSensor presence;

// Add new sensors and actuators of this board here.
DeviceComponent* const components[] = {&presence};
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
