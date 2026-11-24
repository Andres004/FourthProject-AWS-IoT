/**
 * @file main.cpp
 * @brief Board 2 (lights and entrance): declares its components and runs them.
 *
 * Five zone lights driven by voice and a PIR that is only queried and
 * logged. The shared setup and loop live in SmartObjectApp.
 */
#include <Arduino.h>

#include "PresenceSensor.h"
#include "SmartObjectApp.h"
#include "ZoneLight.h"
#include "config_lights.h"
#include "secrets_lights.h"

namespace {

namespace doc = config::shadow_doc;
namespace pins = config::pins;
namespace zones = config::zones;

ZoneLight kitchen(zones::KITCHEN, doc::KEY_LIGHT_KITCHEN, pins::LIGHT_KITCHEN);
ZoneLight living(zones::LIVING, doc::KEY_LIGHT_LIVING, pins::LIGHT_LIVING);
ZoneLight dining(zones::DINING, doc::KEY_LIGHT_DINING, pins::LIGHT_DINING);
ZoneLight bathroom(zones::BATHROOM, doc::KEY_LIGHT_BATHROOM, pins::LIGHT_BATHROOM);
ZoneLight bedroom(zones::BEDROOM, doc::KEY_LIGHT_BEDROOM, pins::LIGHT_BEDROOM);
PresenceSensor presence;

// Add new sensors and actuators of this board here.
DeviceComponent* const components[] = {&kitchen, &living,  &dining,
                                       &bathroom, &bedroom, &presence};
constexpr size_t COMPONENT_COUNT = sizeof(components) / sizeof(components[0]);

const SmartObjectApp::Settings settings = {
    secrets::WIFI_SSID,
    secrets::WIFI_PASSWORD,
    {secrets::AWS_IOT_ENDPOINT, secrets::ROOT_CA, secrets::DEVICE_CERTIFICATE,
     secrets::DEVICE_PRIVATE_KEY, config::board::THING_SUFFIX},
    config::pins::STATUS_LED,
};

SmartObjectApp app(settings, components, COMPONENT_COUNT);

}  // namespace

void setup() {
  app.begin();
}

void loop() {
  app.update(millis());
}
