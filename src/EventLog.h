#pragma once

/**
 * @brief Timestamped Serial log used as evidence for the NFR measurements.
 *
 * Every line has the format "[t_ms] EVENT details".
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
