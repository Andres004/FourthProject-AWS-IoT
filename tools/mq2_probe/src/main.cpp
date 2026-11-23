/**
 * @file main.cpp
 * @brief MQ-2 calibration probe for board 1 (ventilation).
 *
 * Prints one line per second:
 *   GAS_SAMPLE t_ms=... pin_mv=... ao_mv=... ao_pct=... min_mv=... max_mv=... n=...
 * Pressing the BOOT button prints "MARK n=... t_ms=...", so the moments when
 * smoke is applied and removed are stamped with the same clock (millis()).
 */
#include <Arduino.h>

#include "GasProbe.h"
#include "config.h"

namespace {

/** Debounced BOOT button that numbers each press. */
class MarkButton {
 public:
  /** Enables the internal pull-up (the button pulls the pin LOW). */
  void begin() { pinMode(config::pins::MARK_BUTTON, INPUT_PULLUP); }

  /** Prints a MARK line on each new press; never blocks. */
  void update(uint32_t nowMs) {
    const bool pressed = digitalRead(config::pins::MARK_BUTTON) == LOW;
    if (pressed && !wasPressed_ &&
        nowMs - lastPressMs_ >= config::mark::DEBOUNCE_MS) {
      lastPressMs_ = nowMs;
      ++marks_;
      Serial.printf("MARK n=%u t_ms=%lu\n", marks_,
                    static_cast<unsigned long>(nowMs));
    }
    wasPressed_ = pressed;
  }

 private:
  bool wasPressed_ = false;
  uint32_t lastPressMs_ = 0;
  uint16_t marks_ = 0;
};

/** Short LED pulse after each sample, so the board shows it is alive. */
class PulseLed {
 public:
  /** Configures the LED pin, initially off. */
  void begin() {
    pinMode(config::pins::STATUS_LED, OUTPUT);
    digitalWrite(config::pins::STATUS_LED, LOW);
  }

  /** Turns the LED on; update() turns it off after PULSE_MS. */
  void trigger(uint32_t nowMs) {
    onSinceMs_ = nowMs;
    on_ = true;
    digitalWrite(config::pins::STATUS_LED, HIGH);
  }

  /** Ends the pulse when due; never blocks. */
  void update(uint32_t nowMs) {
    if (on_ && nowMs - onSinceMs_ >= config::status_led::PULSE_MS) {
      on_ = false;
      digitalWrite(config::pins::STATUS_LED, LOW);
    }
  }

 private:
  bool on_ = false;
  uint32_t onSinceMs_ = 0;
};

GasProbe probe;
MarkButton markButton;
PulseLed led;

}  // namespace

void setup() {
  Serial.begin(config::serial_log::BAUD_RATE);
  probe.begin();
  markButton.begin();
  led.begin();
  Serial.printf(
      "BOOT mq2_probe supply_mv=%.0f divider_gain=%.3f sample_ms=%lu "
      "window_ms=%lu\n",
      config::gas::SUPPLY_MV, config::gas::DIVIDER_GAIN,
      static_cast<unsigned long>(config::gas::SAMPLE_PERIOD_MS),
      static_cast<unsigned long>(config::gas::REPORT_PERIOD_MS));
}

void loop() {
  const uint32_t nowMs = millis();
  markButton.update(nowMs);
  led.update(nowMs);

  GasWindow window;
  if (probe.update(nowMs, window)) {
    Serial.printf(
        "GAS_SAMPLE t_ms=%lu pin_mv=%lu ao_mv=%lu ao_pct=%.2f min_mv=%lu "
        "max_mv=%lu n=%u\n",
        static_cast<unsigned long>(nowMs),
        static_cast<unsigned long>(window.pinMv),
        static_cast<unsigned long>(window.aoMv), window.aoPct,
        static_cast<unsigned long>(window.minAoMv),
        static_cast<unsigned long>(window.maxAoMv), window.samples);
    led.trigger(nowMs);
  }
}
