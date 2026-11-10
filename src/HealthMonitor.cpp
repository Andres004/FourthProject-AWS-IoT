#include "HealthMonitor.h"

#include <Arduino.h>
#include <WiFi.h>
#include <esp_system.h>
#include <esp_task_wdt.h>

#include "EventLog.h"
#include "config.h"

namespace {
constexpr uint32_t MS_PER_S = 1000;
constexpr bool PANIC_ON_TIMEOUT = true;  // Restart instead of only logging
}  // namespace

void HealthMonitor::begin() {
  EventLog::recordf("RESET_REASON", "reason=%s", resetReasonName());

  // Reconfigures the task watchdog that ESP-IDF already started, and adds
  // the Arduino loop task to it.
  esp_task_wdt_init(config::health::WATCHDOG_TIMEOUT_S, PANIC_ON_TIMEOUT);
  esp_task_wdt_add(nullptr);
}

void HealthMonitor::update(uint32_t nowMs, uint32_t wifiDrops,
                           uint32_t shadowDrops) {
  esp_task_wdt_reset();

  if (firstLoop_) {
    firstLoop_ = false;
    lastLogMs_ = nowMs;
  } else {
    const uint32_t loopMs = nowMs - lastLoopMs_;
    if (loopMs > maxLoopMs_) {
      maxLoopMs_ = loopMs;
    }
  }
  lastLoopMs_ = nowMs;

  if (nowMs - lastLogMs_ < config::health::LOG_PERIOD_MS) {
    return;
  }
  lastLogMs_ = nowMs;

  const int rssi = WiFi.status() == WL_CONNECTED ? WiFi.RSSI() : 0;
  EventLog::recordf(
      "HEALTH",
      "uptime_s=%lu heap=%lu min_heap=%lu rssi=%d wifi_drops=%lu "
      "mqtt_drops=%lu max_loop_ms=%lu",
      static_cast<unsigned long>(nowMs / MS_PER_S),
      static_cast<unsigned long>(ESP.getFreeHeap()),
      static_cast<unsigned long>(ESP.getMinFreeHeap()), rssi,
      static_cast<unsigned long>(wifiDrops),
      static_cast<unsigned long>(shadowDrops),
      static_cast<unsigned long>(maxLoopMs_));
  maxLoopMs_ = 0;  // Each line reports the worst loop of its own period.
}

const char* HealthMonitor::resetReasonName() {
  switch (esp_reset_reason()) {
    case ESP_RST_POWERON:
      return "power_on";
    case ESP_RST_EXT:
      return "external_pin";
    case ESP_RST_SW:
      return "software";
    case ESP_RST_PANIC:
      return "panic";
    case ESP_RST_INT_WDT:
      return "interrupt_watchdog";
    case ESP_RST_TASK_WDT:
      return "task_watchdog";
    case ESP_RST_WDT:
      return "other_watchdog";
    case ESP_RST_DEEPSLEEP:
      return "deep_sleep";
    case ESP_RST_BROWNOUT:
      return "brownout";
    case ESP_RST_SDIO:
      return "sdio";
    default:
      return "unknown";
  }
}
