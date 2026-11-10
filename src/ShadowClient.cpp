#include "ShadowClient.h"

#include "EventLog.h"
#include "config.h"
#include "secrets.h"

ShadowClient::ShadowClient(const WifiManager& wifi)
    : wifi_(wifi), mqtt_(tlsClient_) {}

void ShadowClient::begin() {
  namespace api = config::shadow_api;
  namespace net = config::network;

  thingName_ = String(config::device::THING_NAME_PREFIX) +
               String(config::device::LINK_CODE);

  const String base = String(api::TOPIC_PREFIX) + thingName_;
  updateTopic_ = base + api::TOPIC_UPDATE;
  deltaTopic_ = base + api::TOPIC_UPDATE_DELTA;
  updateRejectedTopic_ = base + api::TOPIC_UPDATE_REJECTED;
  getTopic_ = base + api::TOPIC_GET;
  getAcceptedTopic_ = base + api::TOPIC_GET_ACCEPTED;
  getRejectedTopic_ = base + api::TOPIC_GET_REJECTED;

  tlsClient_.setCACert(secrets::ROOT_CA);
  tlsClient_.setCertificate(secrets::DEVICE_CERTIFICATE);
  tlsClient_.setPrivateKey(secrets::DEVICE_PRIVATE_KEY);
  tlsClient_.setTimeout(net::TLS_CONNECT_TIMEOUT_S);
  tlsClient_.setHandshakeTimeout(net::TLS_HANDSHAKE_TIMEOUT_S);

  mqtt_.setServer(secrets::AWS_IOT_ENDPOINT, net::MQTT_PORT);
  mqtt_.setBufferSize(net::MQTT_BUFFER_SIZE);
  mqtt_.setKeepAlive(net::MQTT_KEEPALIVE_S);
  mqtt_.setSocketTimeout(net::MQTT_SOCKET_TIMEOUT_S);
  mqtt_.setCallback([this](char* topic, uint8_t* payload, unsigned int length) {
    onMessage(topic, payload, length);
  });
}

void ShadowClient::update(uint32_t nowMs) {
  if (!wifi_.isConnected()) {
    markDisconnected();
    return;
  }

  if (mqtt_.connected()) {
    mqtt_.loop();
    requestShadowIfDue(nowMs);
    return;
  }

  markDisconnected();
  if (!attemptedConnection_ ||
      nowMs - lastAttemptMs_ >= config::network::MQTT_RETRY_INTERVAL_MS) {
    connect(nowMs);
  }
}

bool ShadowClient::isConnected() const {
  return mqtt_.connected();
}

bool ShadowClient::publishReported(const char* payload) {
  return mqtt_.publish(updateTopic_.c_str(), payload);
}

uint32_t ShadowClient::disconnections() const {
  return disconnections_;
}

void ShadowClient::connect(uint32_t nowMs) {
  attemptedConnection_ = true;
  lastAttemptMs_ = nowMs;

  EventLog::recordf("MQTT_CONNECTING", "client_id=%s", thingName_.c_str());
  tlsClient_.stop();  // Releases any socket left by a previous session.

  if (mqtt_.connect(thingName_.c_str())) {
    onConnected(millis());
  } else {
    EventLog::recordf("MQTT_CONNECT_FAILED", "state=%d", mqtt_.state());
  }
}

void ShadowClient::onConnected(uint32_t nowMs) {
  sessionActive_ = true;
  EventLog::record("MQTT_CONNECTED");

  const uint8_t qos = config::network::MQTT_SUBSCRIBE_QOS;
  const bool subscribed = mqtt_.subscribe(deltaTopic_.c_str(), qos) &&
                          mqtt_.subscribe(getAcceptedTopic_.c_str(), qos) &&
                          mqtt_.subscribe(getRejectedTopic_.c_str(), qos) &&
                          mqtt_.subscribe(updateRejectedTopic_.c_str(), qos);
  if (!subscribed) {
    EventLog::record("MQTT_SUBSCRIBE_FAILED");
    mqtt_.disconnect();
    return;
  }

  // PubSubClient does not expose SUBACK, so /get waits for subscriptions.
  getPending_ = true;
  nextGetMs_ = nowMs + config::network::GET_AFTER_SUBSCRIBE_MS;
}

void ShadowClient::markDisconnected() {
  if (!sessionActive_) {
    return;
  }
  sessionActive_ = false;
  getPending_ = false;
  ++disconnections_;
  EventLog::recordf("MQTT_LOST", "state=%d count=%lu", mqtt_.state(),
                    static_cast<unsigned long>(disconnections_));
}

void ShadowClient::requestShadowIfDue(uint32_t nowMs) {
  if (!getPending_ || static_cast<int32_t>(nowMs - nextGetMs_) < 0) {
    return;
  }
  nextGetMs_ = nowMs + config::network::GET_RESPONSE_TIMEOUT_MS;
  if (mqtt_.publish(getTopic_.c_str(), "")) {
    EventLog::record("GET_TX");
  } else {
    EventLog::record("GET_TX_FAILED");
  }
}

void ShadowClient::onMessage(const char* topic, const uint8_t* payload,
                             size_t length) {
  if (deltaTopic_ == topic) {
    handleDelta(payload, length);
  } else if (getAcceptedTopic_ == topic) {
    getPending_ = false;
    handleGetAccepted(payload, length);
  } else if (getRejectedTopic_ == topic) {
    onGetRejected(payload, length);
  } else if (updateRejectedTopic_ == topic) {
    EventLog::recordf("UPDATE_REJECTED", "%.*s", static_cast<int>(length),
                      reinterpret_cast<const char*>(payload));
  }
}

void ShadowClient::onGetRejected(const uint8_t* payload, size_t length) {
  EventLog::recordf("GET_REJECTED", "%.*s", static_cast<int>(length),
                    reinterpret_cast<const char*>(payload));

  JsonDocument document;
  if (deserializeJson(document, payload, length)) {
    return;  // The pending /get will be sent again.
  }
  if (document["code"] == config::shadow_api::ERROR_CODE_NOT_FOUND) {
    getPending_ = false;  // No document yet: the first report creates it.
    notifySynced();
  }
}
