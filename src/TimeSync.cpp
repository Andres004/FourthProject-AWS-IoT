#include "TimeSync.h"

#include <Arduino.h>
#include <sys/time.h>

#include "EventLog.h"
#include "config.h"

namespace {
constexpr int64_t MS_PER_S = 1000;
constexpr int64_t US_PER_MS = 1000;
}  // namespace

void TimeSync::update(bool wifiConnected) {
  if (!started_ && wifiConnected) {
    namespace cs = config::clock_sync;
    // Asynchronous: SNTP runs in the background and resyncs periodically.
    configTime(cs::UTC_OFFSET_S, cs::DST_OFFSET_S, cs::NTP_SERVER_PRIMARY,
               cs::NTP_SERVER_SECONDARY);
    started_ = true;
    EventLog::recordf("TIME_SYNC_START", "server=%s",
                      cs::NTP_SERVER_PRIMARY);
  }

  int64_t epochMs = 0;
  if (started_ && !synced_ && nowUtcMs(epochMs)) {
    synced_ = true;
    EventLog::record("TIME_SYNCED");  // The prefix now carries UTC.
  }
}

bool TimeSync::nowUtcMs(int64_t& epochMs) {
  struct timeval now;
  gettimeofday(&now, nullptr);
  if (now.tv_sec < config::clock_sync::MIN_VALID_EPOCH_S) {
    return false;
  }
  epochMs = static_cast<int64_t>(now.tv_sec) * MS_PER_S +
            static_cast<int64_t>(now.tv_usec) / US_PER_MS;
  return true;
}
