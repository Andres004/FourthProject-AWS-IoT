#include "WifiManager.h"

#include <WiFi.h>

#include "EventLog.h"
#include "config_common.h"

WifiManager::WifiManager(const char* ssid, const char* password)
    : ssid_(ssid), password_(password) {}

void WifiManager::begin() {
  WiFi.persistent(false);  // Avoid wearing the flash on every reconnection.
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);  // Modem sleep would delay incoming Shadow deltas.
  WiFi.setAutoReconnect(false);  // Retries are handled by update().
  startConnection(millis());
}

void WifiManager::update(uint32_t nowMs) {
  const bool linkUp = WiFi.status() == WL_CONNECTED;

  if (linkUp != connected_) {
    connected_ = linkUp;
    if (connected_) {
      EventLog::recordf("WIFI_CONNECTED", "ip=%s",
                        WiFi.localIP().toString().c_str());
    } else {
      ++disconnections_;
      EventLog::recordf("WIFI_LOST", "count=%lu",
                        static_cast<unsigned long>(disconnections_));
      startConnection(nowMs);
    }
    return;
  }

  if (!connected_ &&
      nowMs - lastAttemptMs_ >= config::network::WIFI_RETRY_INTERVAL_MS) {
    startConnection(nowMs);
  }
}

bool WifiManager::isConnected() const {
  return connected_;
}

uint32_t WifiManager::disconnections() const {
  return disconnections_;
}

void WifiManager::startConnection(uint32_t nowMs) {
  lastAttemptMs_ = nowMs;
  EventLog::recordf("WIFI_CONNECTING", "ssid=%s", ssid_);
  WiFi.disconnect();
  WiFi.begin(ssid_, password_);
}
