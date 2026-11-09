/**
 * @file main.cpp
 * @brief Creates the firmware objects and connects them.
 */
#include <Arduino.h>

#include "DeviceComponent.h"
#include "DoorActuator.h"
#include "EventLog.h"
#include "PresenceSensor.h"
#include "ShadowReporter.h"
#include "StatusLed.h"
#include "WifiManager.h"
#include "config.h"

#ifdef LOCAL_TEST_MODE
#include "SerialShadowClient.h"
#else
#include "ShadowClient.h"
#endif

namespace {

WifiManager wifi;
StatusLed statusLed;
DoorActuator door;
PresenceSensor presence;

#ifdef LOCAL_TEST_MODE
SerialShadowClient shadow;
#else
ShadowClient shadow(wifi);
#endif

// Add new sensors and actuators here.
DeviceComponent* const components[] = {&door, &presence};
constexpr size_t COMPONENT_COUNT = sizeof(components) / sizeof(components[0]);

ShadowReporter reporter(shadow, components, COMPONENT_COUNT);

void applyDesiredToComponents(JsonObjectConst desired) {
  for (DeviceComponent* component : components) {
    component->applyDesired(desired);
  }
}

}  // namespace

void setup() {
  EventLog::begin();
  EventLog::record("BOOT");
  EventLog::recordf("LINK_CODE", "%lu",
                    static_cast<unsigned long>(config::device::LINK_CODE));

  statusLed.begin();
  for (DeviceComponent* component : components) {
    component->begin();
  }

  shadow.setHandlers(applyDesiredToComponents, [] { reporter.requestReport(); });
  wifi.begin();
  shadow.begin();
}

void loop() {
  const uint32_t nowMs = millis();

  wifi.update(nowMs);
  shadow.update(nowMs);
  for (DeviceComponent* component : components) {
    component->update(nowMs);
  }
  reporter.update(nowMs);
  statusLed.update(nowMs, wifi.isConnected(), shadow.isConnected());
}
