#pragma once

#include <PubSubClient.h>
#include <WString.h>
#include <WiFiClientSecure.h>

#include "ShadowTransport.h"
#include "WifiManager.h"

/**
 * @brief Connects to the classic Device Shadow using MQTT over TLS.
 *
 * On every connection it subscribes to the Shadow topics and requests the full
 * document, so a desired state set while offline is applied on return.
 *
 * Retries are spaced in time. A single attempt can still hold the loop for the
 * TCP and TLS time limits defined in config.h, because PubSubClient connects
 * synchronously.
 */
class ShadowClient : public ShadowTransport {
 public:
  explicit ShadowClient(const WifiManager& wifi);

  void begin() override;
  void update(uint32_t nowMs) override;
  bool isConnected() const override;
  bool publishReported(const char* payload) override;
  uint32_t disconnections() const override;

 private:
  void connect();
  void onConnected(uint32_t nowMs);
  void markDisconnected();
  void requestShadowIfDue(uint32_t nowMs);
  void onMessage(const char* topic, const uint8_t* payload, size_t length);
  void onGetRejected(const uint8_t* payload, size_t length);

  const WifiManager& wifi_;
  WiFiClientSecure tlsClient_;
  mutable PubSubClient mqtt_;

  String thingName_;
  String updateTopic_;
  String deltaTopic_;
  String updateRejectedTopic_;
  String getTopic_;
  String getAcceptedTopic_;
  String getRejectedTopic_;

  bool sessionActive_ = false;
  bool attemptedConnection_ = false;
  bool getPending_ = false;
  uint32_t disconnections_ = 0;
  uint32_t lastAttemptMs_ = 0;
  uint32_t nextGetMs_ = 0;
};
