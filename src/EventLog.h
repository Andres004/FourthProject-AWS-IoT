#pragma once

/**
 * @brief Timestamped Serial log used as evidence for the NFR measurements.
 *
 * Every line has the format "[t_ms|UTC] EVENT details", where t_ms is the
 * time since boot and UTC is the NTP time with milliseconds, or "-" while
 * the clock is not synchronized yet. Example:
 * "[48211|2026-11-09T21:05:07.123Z] DELTA_RX version=57 {...}".
 */
class EventLog {
 public:
  /** Opens the Serial port. Call once, before any other method. */
  static void begin();

  /** Writes an event without details. */
  static void record(const char* event);

  /** Writes an event with printf-style details. */
  static void recordf(const char* event, const char* format, ...)
      __attribute__((format(printf, 2, 3)));
};
