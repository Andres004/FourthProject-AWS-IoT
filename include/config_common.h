/**
 * @file config_common.h
 * @brief Constants shared by both SmartLoft firmwares: identity, logging,
 * network, clock, health, Shadow API, reporting and status LED.
 *
 * Board-specific constants live in config_vent.h and config_lights.h.
 * Credentials and the AWS endpoint live in secrets_<board>.h, which are not
 * committed.
 */
#pragma once

#include <stddef.h>
#include <stdint.h>
#include <time.h>

namespace config {

/** Identity of the smart home in AWS IoT Core. */
namespace device {
// Thing name = THING_NAME_PREFIX + LINK_CODE + board suffix ("-vent"/"-lights").
constexpr char THING_NAME_PREFIX[] = "smartloft-";
constexpr uint32_t LINK_CODE = 739264;  // Six digits, first digit not 0; spoken to Alexa
}  // namespace device

/** Serial event log. */
namespace serial_log {
constexpr uint32_t BAUD_RATE = 115200;        // Serial Monitor speed [baud]
constexpr uint16_t MAX_DETAILS_LENGTH = 1280;  // Longest formatted detail [characters]
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

/** UTC clock used for device_ts and to correlate logs with CloudWatch. */
namespace clock_sync {
constexpr char NTP_SERVER_PRIMARY[] = "pool.ntp.org";
constexpr char NTP_SERVER_SECONDARY[] = "time.google.com";
constexpr long UTC_OFFSET_S = 0;  // Logs use UTC, like CloudWatch
constexpr long DST_OFFSET_S = 0;  // No daylight saving time in UTC
constexpr time_t MIN_VALID_EPOCH_S = 1767225600;  // 2026-01-01: clock is set
}  // namespace clock_sync

/** Stability evidence: health log and loop watchdog. */
namespace health {
constexpr uint32_t LOG_PERIOD_MS = 60000;  // Between HEALTH lines [ms]
// Longest legal blocking call: TCP 8 s + TLS 8 s + MQTT 5 s = 21 s.
constexpr uint32_t WATCHDOG_TIMEOUT_S = 30;  // Reset if loop() stalls [s]
}  // namespace health

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
constexpr char KEY_VERSION[] = "version";  // Shadow document version
}  // namespace shadow_api

/** Shadow reporting policy (guide section 5.8). */
namespace report {
constexpr uint32_t HEARTBEAT_PERIOD_MS = 60000;    // Max time between reports [ms]
constexpr uint32_t MIN_REPORT_INTERVAL_MS = 1000;  // Min time between reports [ms]
// Full vent report plus "desired": {key: null} is about 400 bytes (contract V3).
constexpr uint16_t PAYLOAD_BUFFER_SIZE = 1024;     // Serialized report limit [bytes]
}  // namespace report

/**
 * Report metadata shared by both Things (technical guide sections 5.3, 5.4
 * and 5.6). Board-specific events and their priorities live in
 * config_vent.h and config_lights.h.
 */
namespace report_doc {
constexpr char KEY_EVENT[] = "event";            // reported: why this report was sent
constexpr char KEY_ORIGIN[] = "origin";          // reported: who caused the last change
constexpr char KEY_SEQ[] = "seq";                // reported: report counter since boot
constexpr char KEY_DEVICE_TS[] = "device_ts";    // reported: UTC epoch at publish [ms]
constexpr char KEY_CMD_ORIGIN[] = "cmd_origin";  // desired: written with each command

constexpr char EVENT_BOOT[] = "boot";            // First report after a restart
constexpr char EVENT_HEARTBEAT[] = "heartbeat";  // Periodic report, nothing changed

constexpr char ORIGIN_BOOT[] = "boot";    // State restored at boot (NVS or /get)
constexpr char ORIGIN_VOICE[] = "voice";  // Command from the Alexa skill
constexpr char ORIGIN_CLOUD[] = "cloud";  // Command from the control Lambda (C1)
constexpr char ORIGIN_EDGE[] = "edge";    // Automatic rule on the board (E1)

// Distinct events that fall inside MIN_REPORT_INTERVAL_MS are queued and
// published one per interval, highest priority first; the state itself is
// never lost (every report carries the full "reported").
constexpr uint8_t PRIORITY_HEARTBEAT = 0;  // Lowest: nothing better to report
constexpr size_t MAX_PENDING_EVENTS = 4;   // Queued distinct events per component and reporter

constexpr int64_t DEVICE_TS_UNKNOWN = 0;  // device_ts before the NTP sync
constexpr size_t MAX_CONSUMED_KEYS = 4;   // desired keys a component clears per report
}  // namespace report_doc

/**
 * Connection status LED. Only board 2 has one (its pin is in config_lights.h);
 * on board 1 GPIO32 is the gas indicator instead (config_vent.h).
 */
namespace status_led {
constexpr int NO_LED = -1;                       // Board without a status LED
constexpr uint32_t BLINK_WIFI_DOWN_MS = 200;     // Half period without WiFi [ms]
constexpr uint32_t BLINK_SHADOW_DOWN_MS = 1000;  // Half period without MQTT [ms]
}  // namespace status_led

/** Serial protocol of the *_local_test builds. */
namespace local_test {
constexpr uint16_t MAX_LINE_LENGTH = 512;  // Longest Serial line [characters]
}  // namespace local_test

}  // namespace config
