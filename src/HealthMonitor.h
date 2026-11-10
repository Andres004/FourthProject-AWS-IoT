#pragma once

#include <stdint.h>

/**
 * @brief Produces the stability evidence and protects against a stalled loop.
 *
 * At boot it logs why the chip restarted, so a brownout caused by the servo
 * or a watchdog reset is visible in the log. Then it logs one HEALTH line per
 * period with uptime, free heap, WiFi signal, link drops and the longest loop
 * iteration. A task watchdog restarts the chip if loop() stops running.
 */
class HealthMonitor {
 public:
  /** Logs the reset reason and arms the loop watchdog. */
  void begin();

  /**
   * Feeds the watchdog, tracks the loop duration and logs when due.
   * @param wifiDrops Times the WiFi link has been lost since boot.
   * @param shadowDrops Times the Shadow link has been lost since boot.
   */
  void update(uint32_t nowMs, uint32_t wifiDrops, uint32_t shadowDrops);

 private:
  static const char* resetReasonName();

  uint32_t lastLoopMs_ = 0;
  uint32_t maxLoopMs_ = 0;
  uint32_t lastLogMs_ = 0;
  bool firstLoop_ = true;
};
