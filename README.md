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

`BOOT`, `LINK_CODE`, `WIFI_*`, `MQTT_*`, `GET_TX`, `GET_RX`, `GET_REJECTED`, `DELTA_RX`, `ACTUATOR_START`, `ACTUATOR_DONE`, `PIR_READY`, `PRESENCE_ON`, `PRESENCE_OFF`, `REPORT_TX`, `UPDATE_REJECTED`, `INVALID_VALUE`, `JSON_ERROR`.
