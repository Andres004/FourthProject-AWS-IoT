/**
 * @file ShadowReporter.h
 * @brief Decides when and what the board publishes to its Shadow "reported".
 */
#pragma once

#include <stddef.h>
#include <stdint.h>

#include "DeviceComponent.h"
#include "ReportQueue.h"
#include "ShadowTransport.h"
#include "config_common.h"

/**
 * @brief Publishes the full board state on events and as a heartbeat.
 *
 * Every report carries the complete "reported" section of the board
 * (contract V1) plus event, origin, seq and device_ts, and a
 * "desired": {key: null} entry for each command a component consumed.
 *
 * - event: "boot" for the first report after a restart; then the pending
 *   events one per MIN_REPORT_INTERVAL_MS, highest priority first;
 *   "heartbeat" when nothing changed.
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
  const char* nextEvent();
  bool publish(uint32_t nowMs);

  ShadowTransport& transport_;
  DeviceComponent* const* components_;
  size_t componentCount_;
  char payload_[config::report::PAYLOAD_BUFFER_SIZE];

  ReportQueue events_;
  bool reportPending_ = false;  // A report without event (resync, confirmation)
  bool bootReported_ = false;
  const char* lastOrigin_ = config::report_doc::ORIGIN_BOOT;
  uint32_t seq_ = 0;
  uint32_t lastReportMs_ = 0;
};
