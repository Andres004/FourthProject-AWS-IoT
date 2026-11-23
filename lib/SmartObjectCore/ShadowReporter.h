#pragma once

#include <stddef.h>
#include <stdint.h>

#include "DeviceComponent.h"
#include "ShadowTransport.h"
#include "config_common.h"

/**
 * @brief Decides when the full device state is published to "reported".
 *
 * A report is sent on a state change, limited by a minimum interval, and also
 * periodically as a heartbeat.
 */
class ShadowReporter {
 public:
  ShadowReporter(ShadowTransport& transport,
                 DeviceComponent* const* components, size_t componentCount);

  /** Sends a report if an event is pending or the heartbeat is due. */
  void update(uint32_t nowMs);

  /** Schedules a report that does not come from a component. */
  void requestReport();

 private:
  void collectComponentRequests();
  bool publish(uint32_t nowMs, const char* reason);

  ShadowTransport& transport_;
  DeviceComponent* const* components_;
  size_t componentCount_;
  char payload_[config::report::PAYLOAD_BUFFER_SIZE];
  bool reportPending_ = false;
  uint32_t lastReportMs_ = 0;
};
