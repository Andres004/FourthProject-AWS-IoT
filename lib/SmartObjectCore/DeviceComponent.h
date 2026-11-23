/**
 * @file DeviceComponent.h
 * @brief Common interface of every sensor and actuator of a SmartLoft board.
 */
#pragma once

#include <ArduinoJson.h>
#include <stddef.h>
#include <stdint.h>

#include "config_common.h"

/** Where a desired state comes from, used to resolve the command origin. */
enum class DesiredSource {
  kDelta,  ///< /update/delta: a new command while connected
  kSync,   ///< /get/accepted: pending desired state after (re)connecting
};

/** A component's reason to publish a report. */
struct ReportRequest {
  const char* event;  ///< Report event name, e.g. "window_changed"
  uint8_t priority;   ///< Higher wins inside the minimum report interval
  const char* origin; ///< Who caused the change, or nullptr to keep the last one
};

/**
 * @brief Common interface of every sensor and actuator of the smart object.
 *
 * Adding hardware means adding one class that implements this interface and
 * registering it in the board's main.cpp. The Shadow code does not change.
 *
 * Besides its state, a component tells the reporter why a report is needed
 * (event, priority, origin) and which desired keys it has consumed, so the
 * next report clears them with "desired": {key: null} (guide section 5.6).
 */
class DeviceComponent {
 public:
  virtual ~DeviceComponent() = default;

  /** Initializes the hardware. */
  virtual void begin() = 0;

  /** Advances the component without blocking. */
  virtual void update(uint32_t nowMs) = 0;

  /** Adds this component's attributes to the "reported" section. */
  virtual void fillReported(JsonObject reported) const = 0;

  /**
   * Applies the attributes this component owns from a desired state.
   * Sensors keep this default, because they have no desired state.
   * @param source Delta or synchronization; see commandOrigin().
   */
  virtual void applyDesired(JsonObjectConst desired, DesiredSource source) {
    (void)desired;
    (void)source;
  }

  /**
   * Takes the pending report request, if any.
   * @param[out] request Filled when the method returns true.
   * @return true once for each requested report.
   */
  bool consumeReportRequest(ReportRequest& request);

  /** Adds {key: null} for every desired key consumed since the last report. */
  void fillConsumedDesired(JsonObject desired) const;

  /** Forgets the consumed keys once a report carrying them was published. */
  void clearConsumedDesired() { consumedCount_ = 0; }

 protected:
  /**
   * Asks the reporter to publish soon. When several requests arrive before
   * the report, the one with the highest priority is kept.
   * @param origin Who caused the change; nullptr keeps the last origin.
   */
  void requestReport(const char* event, uint8_t priority,
                     const char* origin = nullptr);

  /**
   * Asks for a report without a change of its own, e.g. to confirm a command
   * that needs no movement. It is sent as a heartbeat-level report.
   */
  void requestConfirmation();

  /** Marks a desired key as applied, so the next report deletes it. */
  void markDesiredConsumed(const char* key);

  /**
   * Resolves who sent a command: desired.cmd_origin ("voice" or "cloud")
   * when present and valid; otherwise "boot" for a synchronization and
   * "voice" for a delta (a command published by hand in the test client).
   */
  static const char* commandOrigin(JsonObjectConst desired,
                                   DesiredSource source);

 private:
  bool reportRequested_ = false;
  ReportRequest request_ = {nullptr, 0, nullptr};
  const char* consumedKeys_[config::report_doc::MAX_CONSUMED_KEYS] = {};
  size_t consumedCount_ = 0;
};
