/**
 * @file ReportQueue.h
 * @brief Small fixed-size set of pending report events, served by priority.
 */
#pragma once

#include <stddef.h>

#include "ReportTypes.h"
#include "config_common.h"

/**
 * @brief Pending report events, without dynamic memory.
 *
 * Distinct events are kept apart, so two changes that happen within the
 * minimum report interval (e.g. mode_changed from the Cloud and the
 * window_changed that rule E1 causes right after) are published one after
 * the other instead of one hiding the other. Repeating an event that is
 * already pending only refreshes its origin. When the queue is full the
 * lowest-priority event is dropped and logged.
 */
class ReportQueue {
 public:
  /** Adds an event, or refreshes it when the same event is already pending. */
  void add(const ReportRequest& request);

  /**
   * Removes the highest-priority event (the oldest one on a tie).
   * @param[out] request Filled when the method returns true.
   * @return false when the queue is empty.
   */
  bool popHighest(ReportRequest& request);

  /** Forgets every pending event. */
  void clear() { count_ = 0; }

  /** @return true when no event is pending. */
  bool isEmpty() const { return count_ == 0; }

 private:
  void removeAt(size_t index);

  ReportRequest items_[config::report_doc::MAX_PENDING_EVENTS] = {};
  size_t count_ = 0;
};
