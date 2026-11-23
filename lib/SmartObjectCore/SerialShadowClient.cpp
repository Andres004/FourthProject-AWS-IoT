#include "SerialShadowClient.h"

#include <Arduino.h>

#include "EventLog.h"

void SerialShadowClient::begin() {
  EventLog::record("LOCAL_TEST_MODE send a delta line: {\"state\":{...}}");
  notifySynced();
}

void SerialShadowClient::update(uint32_t nowMs) {
  (void)nowMs;

  while (Serial.available() > 0) {
    const char received = static_cast<char>(Serial.read());

    if (received != '\n' && received != '\r') {
      if (lineLength_ < sizeof(line_)) {
        line_[lineLength_] = received;
      }
      ++lineLength_;
      continue;
    }

    if (lineLength_ > sizeof(line_)) {
      EventLog::record("JSON_ERROR reason=line_too_long");
    } else if (lineLength_ > 0) {
      handleDelta(reinterpret_cast<const uint8_t*>(line_), lineLength_);
    }
    lineLength_ = 0;
  }
}

bool SerialShadowClient::isConnected() const {
  return true;
}

bool SerialShadowClient::publishReported(const char* payload) {
  EventLog::recordf("LOCAL_REPORT", "%s", payload);
  return true;
}
