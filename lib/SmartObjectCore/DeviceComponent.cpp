/**
 * @file DeviceComponent.cpp
 * @brief Report requests, consumed desired keys and command origin.
 */
#include "DeviceComponent.h"

#include <string.h>

#include "EventLog.h"

namespace doc = config::report_doc;

bool DeviceComponent::consumeReportRequest(ReportRequest& request) {
  return requests_.popHighest(request);
}

void DeviceComponent::fillConsumedDesired(JsonObject desired) const {
  for (size_t i = 0; i < consumedCount_; ++i) {
    desired[consumedKeys_[i]] = nullptr;  // null deletes the key in the Shadow
  }
}

void DeviceComponent::requestReport(const char* event, uint8_t priority,
                                    const char* origin) {
  requests_.add(ReportRequest{event, priority, origin});
}

void DeviceComponent::requestConfirmation() {
  requestReport(doc::EVENT_HEARTBEAT, doc::PRIORITY_HEARTBEAT);
}

void DeviceComponent::markDesiredConsumed(const char* key) {
  for (size_t i = 0; i < consumedCount_; ++i) {
    if (strcmp(consumedKeys_[i], key) == 0) {
      return;  // Already pending deletion.
    }
  }
  if (consumedCount_ >= doc::MAX_CONSUMED_KEYS) {
    EventLog::recordf("CONSUMED_KEYS_FULL", "key=%s", key);
    return;
  }
  consumedKeys_[consumedCount_++] = key;
}

const char* DeviceComponent::commandOrigin(JsonObjectConst desired,
                                           DesiredSource source) {
  const char* origin = desired[doc::KEY_CMD_ORIGIN].as<const char*>();
  if (origin != nullptr && strcmp(origin, doc::ORIGIN_VOICE) == 0) {
    return doc::ORIGIN_VOICE;
  }
  if (origin != nullptr && strcmp(origin, doc::ORIGIN_CLOUD) == 0) {
    return doc::ORIGIN_CLOUD;
  }
  return source == DesiredSource::kSync ? doc::ORIGIN_BOOT : doc::ORIGIN_VOICE;
}
