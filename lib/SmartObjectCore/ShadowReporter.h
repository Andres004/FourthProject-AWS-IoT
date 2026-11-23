/**
 * @file ShadowReporter.h
 * @brief Decides when and what the board publishes to its Shadow "reported".
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "DeviceComponent.h"
#include "ShadowTransport.h"
#include "config_common.h"

/**
 * @brief Publishes the full board state on events and as a heartbeat.
 *
 * Every report carries the complete "reported" section of the board
 * (contract V1) plus event, origin, seq and device_ts, and a
 * "desired": {key: null} entry for each command a component consumed.
 *
 * - event: the highest-priority request since the last report; "boot" for
 *   the first report after a restart; "heartbeat" when nothing changed.
 * - origin: who caused the last change ("boot" until the first command).
 * - seq: incremented on every publish attempt, even when it fails or the
 *   link is down (contract V2), so lost reports show up as gaps.
 * - device_ts: UTC epoch in ms from NTP, or 0 before the clock is set.
 *
 * There is no offline buffer: a report that cannot be sent is lost and the
 * next one, after reconnecting, carries the full state again.
 */
class ShadowReporter {
 public:
  ShadowReporter(ShadowTransport& transport,
                 DeviceComponent* const* components, size_t componentCount);

  /** Sends a report if an event is pending or the heartbeat is due. */
  void update(uint32_t nowMs);

  /** Schedules a report that does not come from a component (e.g. resync). */
  void requestReport();

 private:
  void collectComponentRequests();
  void mergeRequest(const ReportRequest& request);
  bool publish(uint32_t nowMs);
  void resetPending();

  ShadowTransport& transport_;
  DeviceComponent* const* components_;
  size_t componentCount_;
  char payload_[config::report::PAYLOAD_BUFFER_SIZE];

  bool reportPending_ = false;
  bool bootReported_ = false;
  const char* pendingEvent_ = nullptr;
  uint8_t pendingPriority_ = config::report_doc::PRIORITY_HEARTBEAT;
  const char* lastOrigin_ = config::report_doc::ORIGIN_BOOT;
  uint32_t seq_ = 0;
  uint32_t lastReportMs_ = 0;
};
