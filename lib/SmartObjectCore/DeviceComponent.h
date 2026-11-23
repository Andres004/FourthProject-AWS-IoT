#pragma once

#include <ArduinoJson.h>
#include <stdint.h>

/**
 * 
 * @brief Common interface of every sensor and actuator of the smart object.
 *
 * Adding hardware means adding one class that implements this interface and
 * registering it in main.cpp. The Shadow code does not need to change.
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
   */
  virtual void applyDesired(JsonObjectConst desired) { (void)desired; }

  /** @return true once for each state change that must be reported. */
  bool consumeReportRequest() {
    const bool requested = reportRequested_;
    reportRequested_ = false;
    return requested;
  }

 protected:
  /** Asks the reporter to publish this component's state soon. */
  void requestReport() { reportRequested_ = true; }

 private:
  bool reportRequested_ = false;
};
