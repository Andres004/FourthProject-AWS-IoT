#include "ShadowTransport.h"

#include <utility>

#include "EventLog.h"
#include "config.h"

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
  JsonDocument document;
  if (!parseDocument(payload, length, document)) {
    return;
  }
  EventLog::recordf("DELTA_RX", "version=%lld %.*s",
                    document[config::shadow_api::KEY_VERSION].as<long long>(),
                    static_cast<int>(length),
                    reinterpret_cast<const char*>(payload));
  if (!acceptVersion(document, "delta")) {
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
  JsonDocument document;
  if (!parseDocument(payload, length, document)) {
    return;
  }
  EventLog::recordf("GET_RX", "version=%lld",
                    document[config::shadow_api::KEY_VERSION].as<long long>());
  // Always applied: after a reconnection it is the reference state, even if
  // its version equals the last delta seen.
  const int64_t version =
      document[config::shadow_api::KEY_VERSION].as<int64_t>();
  if (version > lastVersion_) {
    lastVersion_ = version;
  }

  JsonObjectConst desired = document["state"]["desired"];
  if (!desired.isNull() && desiredHandler_) {
    desiredHandler_(desired);
  }
  notifySynced();
}

bool ShadowTransport::acceptVersion(const JsonDocument& document,
                                    const char* source) {
  JsonVariantConst value = document[config::shadow_api::KEY_VERSION];
  if (value.isNull()) {
    return true;  // The local test transport sends deltas without version.
  }
  const int64_t version = value.as<int64_t>();
  if (version <= lastVersion_) {
    EventLog::recordf("STALE_IGNORED", "source=%s version=%lld last=%lld",
                      source, static_cast<long long>(version),
                      static_cast<long long>(lastVersion_));
    return false;
  }
  lastVersion_ = version;
  return true;
}

void ShadowTransport::notifySynced() {
  if (syncHandler_) {
    syncHandler_();
  }
}
