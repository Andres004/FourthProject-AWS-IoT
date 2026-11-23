/**
 * @file ReportTypes.h
 * @brief Small types shared by components, transport and reporter.
 */
#pragma once

#include <stdint.h>

/** Where a desired state comes from, used to resolve the command origin. */
enum class DesiredSource {
  kDelta,  ///< /update/delta: a new command while connected
  kSync,   ///< /get/accepted: pending desired state after (re)connecting
};

/** A component's reason to publish a report. */
struct ReportRequest {
  const char* event;  ///< Report event name, e.g. "window_changed"
  uint8_t priority;   ///< Higher is published first
  const char* origin; ///< Who caused the change, or nullptr to keep the last one
};
