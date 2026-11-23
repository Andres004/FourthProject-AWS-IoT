/**
 * @file SmartObjectApp.h
 * @brief Infrastructure shared by both SmartLoft boards.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "DeviceComponent.h"
#include "HealthMonitor.h"
#include "ShadowClientSettings.h"
#include "ShadowReporter.h"
#include "StatusLed.h"
#include "TimeSync.h"
#include "WifiManager.h"

#ifdef LOCAL_TEST_MODE
#include "SerialShadowClient.h"
#else
#include "ShadowClient.h"
#endif

/**
 * @brief Owns WiFi, NTP, health log, status LED, the Shadow link and the
 * reporter, and drives a board's components through them.
 *
 * Each firmware only declares its components and its connection settings;
 * the setup and loop sequence is written once here, so it is not duplicated
 * between the vent and lights firmwares. In the *_local_test builds the
 * Shadow link is the Serial Monitor instead of AWS IoT Core.
 */
class SmartObjectApp {
 public:
  /** Everything that differs between the two boards' connections. */
  struct Settings {
    const char* wifiSsid;
    const char* wifiPassword;
    ShadowClientSettings shadow;
  };

  /**
   * @param settings Connection data; its strings must outlive the app.
   * @param components Sensors and actuators of the board, in report order.
   * @param componentCount Number of entries in components.
   */
  SmartObjectApp(const Settings& settings, DeviceComponent* const* components,
                 size_t componentCount);

  /** Starts the log, the components and the connections. Call in setup(). */
  void begin();

  /** Advances every part without blocking. Call in every loop(). */
  void update(uint32_t nowMs);

 private:
  void applyDesired(JsonObjectConst desired);

  DeviceComponent* const* components_;
  size_t componentCount_;
  WifiManager wifi_;
  TimeSync timeSync_;
  HealthMonitor health_;
  StatusLed statusLed_;
#ifdef LOCAL_TEST_MODE
  SerialShadowClient shadow_;
#else
  ShadowClient shadow_;
#endif
  ShadowReporter reporter_;
};
