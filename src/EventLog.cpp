#include "EventLog.h"

#include <Arduino.h>
#include <stdarg.h>

#include "config.h"

void EventLog::begin() {
  Serial.begin(config::serial_log::BAUD_RATE);
}

void EventLog::record(const char* event) {
  Serial.printf("[%lu] %s\n", static_cast<unsigned long>(millis()), event);
}

void EventLog::recordf(const char* event, const char* format, ...) {
  char details[config::serial_log::MAX_DETAILS_LENGTH];

  va_list arguments;
  va_start(arguments, format);
  vsnprintf(details, sizeof(details), format, arguments);
  va_end(arguments);

  Serial.printf("[%lu] %s %s\n", static_cast<unsigned long>(millis()), event,
                details);
}
