#include "EventLog.h"

#include <Arduino.h>
#include <stdarg.h>
#include <time.h>

#include "TimeSync.h"
#include "config_common.h"

namespace {

constexpr int64_t MS_PER_S = 1000;
constexpr size_t UTC_TEXT_LENGTH = 32;  // "2026-11-09T21:05:07.123Z" + margin

/** Writes the line prefix: "[t_ms|UTC] " or "[t_ms|-] " before NTP sync. */
void printPrefix() {
  char utc[UTC_TEXT_LENGTH] = "-";

  int64_t epochMs = 0;
  if (TimeSync::nowUtcMs(epochMs)) {
    const time_t seconds = static_cast<time_t>(epochMs / MS_PER_S);
    struct tm parts;
    gmtime_r(&seconds, &parts);
    const size_t used = strftime(utc, sizeof(utc), "%Y-%m-%dT%H:%M:%S", &parts);
    snprintf(utc + used, sizeof(utc) - used, ".%03dZ",
             static_cast<int>(epochMs % MS_PER_S));
  }

  Serial.printf("[%lu|%s] ", static_cast<unsigned long>(millis()), utc);
}

}  // namespace

void EventLog::begin() {
  Serial.begin(config::serial_log::BAUD_RATE);
}

void EventLog::record(const char* event) {
  printPrefix();
  Serial.println(event);
}

void EventLog::recordf(const char* event, const char* format, ...) {
  char details[config::serial_log::MAX_DETAILS_LENGTH];

  va_list arguments;
  va_start(arguments, format);
  vsnprintf(details, sizeof(details), format, arguments);
  va_end(arguments);

  printPrefix();
  Serial.printf("%s %s\n", event, details);
}
