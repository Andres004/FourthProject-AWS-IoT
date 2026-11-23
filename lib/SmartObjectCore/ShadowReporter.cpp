#include "ShadowReporter.h"

#include <ArduinoJson.h>

#include "EventLog.h"

ShadowReporter::ShadowReporter(ShadowTransport& transport,
                               DeviceComponent* const* components,
                               size_t componentCount)
    : transport_(transport),
      components_(components),
      componentCount_(componentCount) {}

void ShadowReporter::update(uint32_t nowMs) {
  collectComponentRequests();

  if (!transport_.isConnected()) {
    return;  // A pending report stays pending until the link returns.
  }

  const uint32_t elapsedMs = nowMs - lastReportMs_;
  if (elapsedMs < config::report::MIN_REPORT_INTERVAL_MS) {
    return;
  }

  if (reportPending_) {
    reportPending_ = !publish(nowMs, "event");
  } else if (elapsedMs >= config::report::HEARTBEAT_PERIOD_MS) {
    publish(nowMs, "heartbeat");
  }
}

void ShadowReporter::requestReport() {
  reportPending_ = true;
}

void ShadowReporter::collectComponentRequests() {
  for (size_t i = 0; i < componentCount_; ++i) {
    if (components_[i]->consumeReportRequest()) {
      reportPending_ = true;
    }
  }
}

bool ShadowReporter::publish(uint32_t nowMs, const char* reason) {
  // A failed attempt also waits for the minimum interval before retrying.
  lastReportMs_ = nowMs;

  JsonDocument document;
  JsonObject reported = document["state"]["reported"].to<JsonObject>();
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->fillReported(reported);
  }

  if (document.overflowed() || measureJson(document) >= sizeof(payload_)) {
    EventLog::record("REPORT_TOO_LARGE");
    return false;
  }
  serializeJson(document, payload_, sizeof(payload_));

  if (!transport_.publishReported(payload_)) {
    EventLog::record("REPORT_TX_FAILED");
    return false;
  }
  EventLog::recordf("REPORT_TX", "reason=%s %s", reason, payload_);
  return true;
}
