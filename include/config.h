/**
 * @file config.h
 * @brief Firmware constants: pins, timing, Shadow contract and MQTT settings.
 *
 * Credentials and the AWS endpoint live in secrets.h, which is not committed.
 */
#pragma once

#include <stdint.h>

namespace config {

/** Identity of this smart object in AWS IoT Core. */
namespace device {
constexpr char THING_NAME_PREFIX[] = "monoambiente-";  // Thing name = prefix + LINK_CODE
constexpr uint32_t LINK_CODE = 482731;  // Six digits, first digit not 0; spoken to Alexa
}  // namespace device

/** ESP32 GPIO numbers. */
namespace pins {
constexpr uint8_t SERVO_SIGNAL = 13;  // SG90 PWM signal
constexpr uint8_t STATUS_LED = 32;    // Connection indicator only, NOT the actuator
constexpr uint8_t PIR_OUTPUT = 26;    // AM312 digital output (3.3 V, active HIGH)
}  // namespace pins

/** Serial event log. */
namespace serial_log {
constexpr uint32_t BAUD_RATE = 115200;  // Serial Monitor speed [baud]
constexpr uint16_t MAX_DETAILS_LENGTH = 256;  // Longest formatted detail [characters]
}  // namespace serial_log

/** WiFi, TLS and MQTT connection settings. */
namespace network {
constexpr uint32_t WIFI_RETRY_INTERVAL_MS = 10000;  // Between WiFi attempts [ms]
constexpr uint32_t MQTT_RETRY_INTERVAL_MS = 5000;   // Between MQTT attempts [ms]
constexpr uint16_t MQTT_PORT = 8883;                // MQTT over TLS port
constexpr uint16_t MQTT_BUFFER_SIZE = 2048;         // Largest MQTT packet [bytes]
constexpr uint16_t MQTT_KEEPALIVE_S = 60;           // MQTT keep-alive [s]
constexpr uint16_t MQTT_SOCKET_TIMEOUT_S = 5;       // MQTT read timeout [s]
constexpr uint32_t TLS_CONNECT_TIMEOUT_S = 8;       // TCP connect limit [s]
constexpr uint32_t TLS_HANDSHAKE_TIMEOUT_S = 8;     // TLS handshake limit [s]
constexpr uint8_t MQTT_SUBSCRIBE_QOS = 1;           // QoS of Shadow subscriptions
constexpr uint32_t GET_AFTER_SUBSCRIBE_MS = 500;    // Wait for subscriptions before /get [ms]
constexpr uint32_t GET_RESPONSE_TIMEOUT_MS = 5000;  // Repeat /get after this silence [ms]
}  // namespace network

/** Device Shadow topics and error codes. */
namespace shadow_api {
constexpr char TOPIC_PREFIX[] = "$aws/things/";  // Topic = prefix + thing + suffix
constexpr char TOPIC_UPDATE[] = "/shadow/update";
constexpr char TOPIC_UPDATE_DELTA[] = "/shadow/update/delta";
constexpr char TOPIC_UPDATE_REJECTED[] = "/shadow/update/rejected";
constexpr char TOPIC_GET[] = "/shadow/get";
constexpr char TOPIC_GET_ACCEPTED[] = "/shadow/get/accepted";
constexpr char TOPIC_GET_REJECTED[] = "/shadow/get/rejected";
constexpr int ERROR_CODE_NOT_FOUND = 404;  // /get rejected: Shadow does not exist yet
}  // namespace shadow_api

/** Shadow document contract shared with the Lambda function. */
namespace shadow_doc {
constexpr char KEY_DOOR[] = "door";                // desired and reported: string
constexpr char KEY_SERVO_ANGLE[] = "servo_angle";  // reported: integer [deg]
constexpr char KEY_PRESENCE[] = "presence";        // reported: boolean
constexpr char DOOR_OPEN[] = "open";               // Valid value of KEY_DOOR
constexpr char DOOR_CLOSED[] = "closed";           // Valid value of KEY_DOOR
}  // namespace shadow_doc

/** SG90 servo that moves the door. */
namespace door {
constexpr int PWM_FREQUENCY_HZ = 50;     // Standard servo frequency [Hz]
constexpr int PULSE_MIN_US = 500;        // Pulse width at 0 deg [us]
constexpr int PULSE_MAX_US = 2400;       // Pulse width at 180 deg [us]
constexpr int CLOSED_ANGLE_DEG = 0;      // Door closed; calibrate on the model [deg]
constexpr int OPEN_ANGLE_DEG = 90;       // Door open; calibrate on the model [deg]
constexpr uint32_t SETTLE_TIME_MS = 400; // Time allowed to finish a move [ms]
}  // namespace door

/** AM312 PIR presence sensor. */
namespace pir {
constexpr uint32_t POLL_PERIOD_MS = 50;       // Between digital reads [ms]
constexpr uint32_t WARMUP_MS = 30000;         // Output ignored after boot [ms]
constexpr uint32_t PRESENCE_HOLD_MS = 10000;  // Presence kept after last motion [ms]
}  // namespace pir

/** Shadow reporting policy. */
namespace report {
constexpr uint32_t HEARTBEAT_PERIOD_MS = 60000;   // Max time between reports [ms]
constexpr uint32_t MIN_REPORT_INTERVAL_MS = 1000; // Min time between reports [ms]
constexpr uint16_t PAYLOAD_BUFFER_SIZE = 512;     // Serialized report limit [bytes]
}  // namespace report

/** Connection status LED patterns. */
namespace status_led {
constexpr uint32_t BLINK_WIFI_DOWN_MS = 200;   // Half period without WiFi [ms]
constexpr uint32_t BLINK_SHADOW_DOWN_MS = 1000;  // Half period without MQTT [ms]
}  // namespace status_led

/** Serial protocol of the LOCAL_TEST_MODE build. */
namespace local_test {
constexpr uint16_t MAX_LINE_LENGTH = 256;  // Longest Serial line [characters]
}  // namespace local_test

}  // namespace config
