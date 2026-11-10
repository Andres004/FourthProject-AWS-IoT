#pragma once

#include <ArduinoJson.h>
#include <stddef.h>
#include <stdint.h>

#include <functional>

/**
 * @brief Link between the firmware and a Device Shadow.
 *
 * It holds the message interpretation shared by the real MQTT client and the
 * Serial client used for local tests.
 */
class ShadowTransport {
 public:
  /** Receives the desired state to apply. */
  using DesiredHandler = std::function<void(JsonObjectConst desired)>;

  /** Called when the initial Shadow synchronization ends. */
  using SyncHandler = std::function<void()>;

  virtual ~ShadowTransport() = default;

  /** Prepares the link. Set the handlers first. */
  virtual void begin() = 0;

  /** Services the link without waiting for incoming data. */
  virtual void update(uint32_t nowMs) = 0;

  /** @return true while reports can be published. */
  virtual bool isConnected() const = 0;

  /** Publishes a serialized {"state":{"reported":...}} document. */
  virtual bool publishReported(const char* payload) = 0;

  /** @return Times the Shadow link has been lost since boot. */
  virtual uint32_t disconnections() const { return 0; }

  /** Registers the callbacks used for incoming Shadow data. */
  void setHandlers(DesiredHandler desiredHandler, SyncHandler syncHandler);

 protected:
  /**
   * Applies an /update/delta document, whose "state" is the difference.
   * A document whose version is not newer than the last one applied is a
   * duplicate or out-of-order delivery (MQTT QoS 1) and is ignored.
   */
  void handleDelta(const uint8_t* payload, size_t length);

  /** Applies a /get/accepted document, whose desired part is pending work. */
  void handleGetAccepted(const uint8_t* payload, size_t length);

  /** Signals that the initial synchronization has finished. */
  void notifySynced();

 private:
  /** @return false when the document version was already processed. */
  bool acceptVersion(const JsonDocument& document, const char* source);

  DesiredHandler desiredHandler_;
  SyncHandler syncHandler_;
  int64_t lastVersion_ = -1;  // -1: nothing processed since boot
};
