# Smart studio apartment: door and presence (SIS-234, Practice 3)

ESP32 firmware for a smart object synchronized with an AWS IoT Device Shadow over MQTT and TLS. A servo opens and closes the door, and an AM312 PIR sensor detects presence at the entrance. Alexa and the Lambda function interact with the object only through the Shadow.

## Hardware

| Component | Pin | ESP32 connection |
|---|---|---|
| SG90 servo | Signal | GPIO13 |
| SG90 servo | V+ / GND | 5 V / common GND |
| AM312 PIR | OUT | GPIO26 |
| AM312 PIR | VCC / GND | 3.3 V / common GND |
| Status LED | Anode, through 220-330 ohm | GPIO32 |

The LED only indicates the connection state: fast blink means no WiFi, slow blink means no Shadow link, and steady means online. It is not the actuator.

## Shadow contract

Thing name: `monoambiente-<LINK_CODE>`.

```json
{
  "state": {
    "desired":  { "door": "closed" },
    "reported": { "door": "closed", "servo_angle": 0, "presence": false }
  }
}
```

| Attribute | Section | Type | Valid values | Written by |
|---|---|---|---|---|
| `door` | desired, reported | string | `"open"`, `"closed"` | Lambda in `desired`; ESP32 in `reported` after moving |
| `servo_angle` | reported | integer | `CLOSED_ANGLE_DEG`, `OPEN_ANGLE_DEG` | ESP32 |
| `presence` | reported | boolean | `true`, `false` | ESP32 |

## Setup

1. Copy `include/secrets.example.h` to `include/secrets.h`.
2. Fill in the WiFi credentials, AWS endpoint, Root CA, device certificate and private key.
3. Set `LINK_CODE` in `include/config.h` to match the Thing name.

Never commit `include/secrets.h` or certificate files.

## Build and run

```bash
pio run -e esp32doit-devkit-v1 -t upload -t monitor
```

To test the hardware without AWS:

```bash
pio run -e local_test -t upload -t monitor
```

In local test mode, send a delta through the Serial Monitor:

```json
{"state":{"door":"open"}}
```

## Architecture

| Class | Responsibility |
|---|---|
| `DeviceComponent` | Interface implemented by sensors and actuators |
| `DoorActuator` | Validates door commands and controls the servo |
| `PresenceSensor` | Reads the PIR sensor and applies warm-up and hold times |
| `ShadowTransport` | Interprets delta and get documents |
| `ShadowClient` | MQTT over TLS connection to the Shadow |
| `SerialShadowClient` | Serial replacement for local tests |
| `ShadowReporter` | Applies the event and heartbeat reporting policy |
| `WifiManager` | Connects and retries WiFi |
| `StatusLed` | Displays the connection state |
| `EventLog` | Writes timestamped evidence to Serial |

To add a sensor or actuator, implement `DeviceComponent` and register the object in `src/main.cpp`.

## Log events

Every Serial line has the format `[t_ms|UTC] EVENT details`. `t_ms` is the time since boot. `UTC` is the NTP time with milliseconds, or `-` until the clock is synchronized, and is used to compare device logs with the Lambda logs in CloudWatch.

| Event | Meaning |
|---|---|
| `BOOT`, `RESET_REASON`, `LINK_CODE` | Start, why the chip restarted (`brownout`, `task_watchdog`...) and the code to say to Alexa |
| `WIFI_*`, `MQTT_*`, `TIME_SYNC_START`, `TIME_SYNCED` | Connection and clock state; `*_LOST` lines carry a drop counter |
| `GET_TX`, `GET_RX`, `GET_REJECTED` | Full Shadow request after each connection |
| `DELTA_RX version=N` | Desired change received; `STALE_IGNORED` drops duplicated or older versions |
| `ACTUATOR_START`, `ACTUATOR_DONE` | Servo movement and its confirmation |
| `PIR_READY`, `PRESENCE_ON`, `PRESENCE_OFF` | Sensor warm-up end and presence changes |
| `REPORT_TX reason=event\|heartbeat` | Report published to `reported` |
| `HEALTH` | Every 60 s: uptime, free and minimum heap, RSSI, link drops and longest loop iteration |
| `UPDATE_REJECTED`, `INVALID_VALUE`, `JSON_ERROR`, `REPORT_TX_FAILED` | Errors |

A task watchdog restarts the ESP32 if `loop()` stalls for 30 s.

## Lambda tests

The skill backend has unit tests that replace DynamoDB and AWS IoT with in-memory fakes. They need the dependencies in `lambda/package` (see the AWS guide):

```bash
python -m unittest discover -s lambda/tests -v
```

Each request writes one `SKILL_REQUEST` JSON line to CloudWatch, with the intent, a hash of the user, the Thing, the result, the Shadow version written and the Lambda time.
