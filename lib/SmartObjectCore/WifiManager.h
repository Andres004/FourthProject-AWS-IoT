#pragma once

#include <stdint.h>

/**
 * @brief Keeps the WiFi station connected without blocking the main loop.
 */
class WifiManager {
 public:
  /**
   * @param ssid Network name; must outlive this object.
   * @param password Network password; must outlive this object.
   */
  WifiManager(const char* ssid, const char* password);

  /** Configures the station and starts the first connection attempt. */
  void begin();

  /** Tracks the link state and retries periodically while disconnected. */
  void update(uint32_t nowMs);

  /** @return true while the station has an IP address. */
  bool isConnected() const;

  /** @return Times the link has been lost since boot. */
  uint32_t disconnections() const;

 private:
  void startConnection(uint32_t nowMs);

  const char* ssid_;
  const char* password_;
  bool connected_ = false;
  uint32_t disconnections_ = 0;
  uint32_t lastAttemptMs_ = 0;
};
