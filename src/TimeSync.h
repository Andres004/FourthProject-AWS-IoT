#pragma once

#include <stdint.h>

/**
 * @brief Keeps a UTC clock synchronized with NTP, without blocking.
 *
 * The clock is only used for evidence: it lets the device logs be compared
 * with the Lambda logs in CloudWatch to measure the end-to-end response time.
 * The control logic never depends on it.
 */
class TimeSync {
 public:
  /** Starts SNTP the first time WiFi is up and reports when time is valid. */
  void update(bool wifiConnected);

  /**
   * Reads the current UTC time.
   * @param[out] epochMs Milliseconds since 1970-01-01T00:00:00Z.
   * @return false while the clock has not been synchronized yet.
   */
  static bool nowUtcMs(int64_t& epochMs);

 private:
  bool started_ = false;
  bool synced_ = false;
};
