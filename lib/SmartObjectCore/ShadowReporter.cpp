/**
 * @file ShadowReporter.cpp
 * @brief Report policy: event choice, seq, device_ts and desired clean-up.
 */
#include "ShadowReporter.h"

#include <ArduinoJson.h>

#include "EventLog.h"
#include "TimeSync.h"

namespace doc = config::report_doc;

ShadowReporter::ShadowReporter(ShadowTransport& transport,
                               DeviceComponent* const* components,
                               size_t componentCount)
    : transport_(transport),
      components_(components),
      componentCount_(componentCount) {}

void ShadowReporter::update(uint32_t nowMs) {
  collectComponentRequests();

  const uint32_t elapsedMs = nowMs - lastReportMs_;
  if (elapsedMs < config::report::MIN_REPORT_INTERVAL_MS) {
    return;
  }
  if (!reportPending_ && elapsedMs < config::report::HEARTBEAT_PERIOD_MS) {
    return;
  }

  // Attempted even while offline: seq must advance (contract V2) and the
  // log shows which reports were lost. A failed report is not retried; the
  // resync after reconnecting publishes the full state again.
  publish(nowMs);
  resetPending();
}

void ShadowReporter::requestReport() {
  reportPending_ = true;
}

void ShadowReporter::collectComponentRequests() {
  ReportRequest request;
  for (size_t i = 0; i < componentCount_; ++i) {
    if (components_[i]->consumeReportRequest(request)) {
      mergeRequest(request);
    }
  }
}

void ShadowReporter::mergeRequest(const ReportRequest& request) {
  if (pendingEvent_ == nullptr || request.priority > pendingPriority_) {
    pendingEvent_ = request.event;
    pendingPriority_ = request.priority;
  }
  if (request.origin != nullptr) {
    lastOrigin_ = request.origin;
  }
  reportPending_ = true;
}

bool ShadowReporter::publish(uint32_t nowMs) {
  // A failed attempt also waits for the minimum interval before the next.
  lastReportMs_ = nowMs;
  ++seq_;

  const char* event = !bootReported_          ? doc::EVENT_BOOT
                      : pendingEvent_ != nullptr ? pendingEvent_
                                                 : doc::EVENT_HEARTBEAT;
  int64_t deviceTs = doc::DEVICE_TS_UNKNOWN;
  TimeSync::nowUtcMs(deviceTs);  // Leaves 0 while the clock is not set.

  JsonDocument document;
  JsonObject state = document["state"].to<JsonObject>();
  JsonObject reported = state["reported"].to<JsonObject>();
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->fillReported(reported);
  }
  reported[doc::KEY_EVENT] = event;
  reported[doc::KEY_ORIGIN] = lastOrigin_;
  reported[doc::KEY_SEQ] = seq_;
  reported[doc::KEY_DEVICE_TS] = deviceTs;

  JsonObject desired = state["desired"].to<JsonObject>();
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->fillConsumedDesired(desired);
  }
  if (desired.size() == 0) {
    state.remove("desired");
  }

  if (document.overflowed() || measureJson(document) >= sizeof(payload_)) {
    EventLog::recordf("REPORT_TOO_LARGE", "seq=%lu event=%s",
                      static_cast<unsigned long>(seq_), event);
    return false;
  }
  serializeJson(document, payload_, sizeof(payload_));

  if (!transport_.isConnected() || !transport_.publishReported(payload_)) {
    EventLog::recordf("REPORT_TX_FAILED", "seq=%lu event=%s",
                      static_cast<unsigned long>(seq_), event);
    return false;
  }
  EventLog::recordf("REPORT_TX", "seq=%lu event=%s origin=%s %s",
                    static_cast<unsigned long>(seq_), event, lastOrigin_,
                    payload_);

  bootReported_ = true;
  for (size_t i = 0; i < componentCount_; ++i) {
    components_[i]->clearConsumedDesired();  // The Shadow deletes them now.
  }
  return true;
}

void ShadowReporter::resetPending() {
  reportPending_ = false;
  pendingEvent_ = nullptr;
  pendingPriority_ = doc::PRIORITY_HEARTBEAT;
}
