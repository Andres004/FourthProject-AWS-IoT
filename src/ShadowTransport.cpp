#include "ShadowTransport.h"

#include <utility>

#include "EventLog.h"

namespace {

bool parseDocument(const uint8_t* payload, size_t length,
                   JsonDocument& document) {
  const DeserializationError error = deserializeJson(document, payload, length);
  if (error) {
    EventLog::recordf("JSON_ERROR", "reason=%s", error.c_str());
    return false;
  }
  return true;
}

}  // namespace

void ShadowTransport::setHandlers(DesiredHandler desiredHandler,
                                  SyncHandler syncHandler) {
  desiredHandler_ = std::move(desiredHandler);
  syncHandler_ = std::move(syncHandler);
}

void ShadowTransport::handleDelta(const uint8_t* payload, size_t length) {
  EventLog::recordf("DELTA_RX", "%.*s", static_cast<int>(length),
                    reinterpret_cast<const char*>(payload));

  JsonDocument document;
  if (!parseDocument(payload, length, document)) {
    return;
  }

  JsonObjectConst state = document["state"];
  if (state.isNull()) {
    EventLog::record("JSON_ERROR reason=missing_state");
    return;
  }
  if (desiredHandler_) {
    desiredHandler_(state);
  }
}

void ShadowTransport::handleGetAccepted(const uint8_t* payload, size_t length) {
  EventLog::record("GET_RX");

  JsonDocument document;
  if (!parseDocument(payload, length, document)) {
    return;
  }

  JsonObjectConst desired = document["state"]["desired"];
  if (!desired.isNull() && desiredHandler_) {
    desiredHandler_(desired);
  }
  notifySynced();
}

void ShadowTransport::notifySynced() {
  if (syncHandler_) {
    syncHandler_();
  }
}
