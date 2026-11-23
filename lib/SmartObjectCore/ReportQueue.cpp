/**
 * @file ReportQueue.cpp
 * @brief Insertion, de-duplication and priority order of pending events.
 */
#include "ReportQueue.h"

#include <string.h>

#include "EventLog.h"

void ReportQueue::add(const ReportRequest& request) {
  for (size_t i = 0; i < count_; ++i) {
    if (strcmp(items_[i].event, request.event) == 0) {
      if (request.origin != nullptr) {
        items_[i].origin = request.origin;  // The latest cause wins.
      }
      return;
    }
  }

  if (count_ < config::report_doc::MAX_PENDING_EVENTS) {
    items_[count_++] = request;
    return;
  }

  // Full: keep the most important events.
  size_t lowest = 0;
  for (size_t i = 1; i < count_; ++i) {
    if (items_[i].priority < items_[lowest].priority) {
      lowest = i;
    }
  }
  const bool replace = request.priority > items_[lowest].priority;
  EventLog::recordf("REPORT_EVENT_DROPPED", "event=%s",
                    replace ? items_[lowest].event : request.event);
  if (replace) {
    items_[lowest] = request;
  }
}

bool ReportQueue::popHighest(ReportRequest& request) {
  if (count_ == 0) {
    return false;
  }
  size_t best = 0;
  for (size_t i = 1; i < count_; ++i) {
    if (items_[i].priority > items_[best].priority) {
      best = i;  // Strictly greater: on a tie the oldest one goes first.
    }
  }
  request = items_[best];
  removeAt(best);
  return true;
}

void ReportQueue::removeAt(size_t index) {
  for (size_t i = index + 1; i < count_; ++i) {
    items_[i - 1] = items_[i];  // Keeps the arrival order of the rest.
  }
  --count_;
}
