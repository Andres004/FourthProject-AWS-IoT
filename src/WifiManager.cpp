#include "WifiManager.h"

#include <WiFi.h>

#include "EventLog.h"
#include "config.h"
#include "secrets.h"

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
      EventLog::record("WIFI_LOST");
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

void WifiManager::startConnection(uint32_t nowMs) {
  lastAttemptMs_ = nowMs;
  EventLog::recordf("WIFI_CONNECTING", "ssid=%s", secrets::WIFI_SSID);
  WiFi.disconnect();
  WiFi.begin(secrets::WIFI_SSID, secrets::WIFI_PASSWORD);
}
