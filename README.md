# SmartLoft: monoambiente inteligente — SIS-234, Práctica 4

Maqueta de un monoambiente con **dos objetos inteligentes** conectados a AWS IoT Core:

- **Placa 1 — ventilación:** un MQ-2 mide gas y humo; si el índice supera un umbral, un servo SG90 abre la ventana y la cierra al volver a la normalidad. La regla funciona en la placa (Edge), aun sin Internet.
- **Placa 2 — luces y entrada:** cinco LEDs representan las luces de la cocina, la sala de estar, el comedor, el baño y la habitación; un PIR AM312 detecta presencia en la entrada (solo se consulta, no acciona nada).

Se controlan por voz o texto desde la skill de Alexa **"monoambiente inteligente"**. Alexa y la Nube nunca hablan con las placas: todo pasa por el **Device Shadow** de cada una. Cada reporte se guarda en DynamoDB con su origen (`voice`, `edge`, `cloud`, `boot`).

```text
Usuario → Alexa (simulador) → AWS Lambda (skill) → DynamoDB (vinculación)
                                                 → Shadow -vent   ⇄ Placa 1 (MQTT/TLS) → MQ-2 + servo
                                                 → Shadow -lights ⇄ Placa 2 (MQTT/TLS) → 5 LEDs + PIR
Shadows → reglas de AWS IoT → Lambda de datos   → DynamoDB (histórico)
                            → Lambda de control → Shadow -vent (vuelve a automático)
```

- **Informe técnico de la Práctica 4:** [Informe_P4.md](Informe_P4.md)
- **Informe de la Práctica 3** (sin cambios): [Informe.md](Informe.md)
- **Evidencia de cada prueba:** [docs/evidencias_p4/](docs/evidencias_p4/)

---

## 1. Qué necesitas

| Hardware | Software y cuentas |
|---|---|
| ESP32 DOIT DevKit V1 (30 pines) — placa 1 | VS Code con PlatformIO |
| ESP32-DevKitC (38 pines) — placa 2 | Python 3.11 o más reciente (para los scripts) |
| Sensor MQ-2 (módulo con salida AO) y servo SG90 | Cuenta de AWS (región `us-east-2`, Ohio) |
| Sensor PIR AM312 | Cuenta de Amazon Developer (Alexa Developer Console) |
| 5 LEDs blancos con resistencias de 220 Ω, 2 LEDs de estado | Una red WiFi de 2.4 GHz (un solo hotspot para las dos placas) |
| Divisor de 10 kΩ / 15 kΩ y capacitor de 100 nF para el MQ-2 | |
| Fuente de 5 V / 2 A para el servo y el MQ-2 | |

## 2. Conexiones

**Placa 1 (ventilación).** El servo y el MQ-2 se alimentan de la fuente de 5 V, con **GND común** con la placa. El 5 V de la fuente nunca va a VIN, 3V3 ni a un GPIO.

| Componente | Pin del componente | Conexión |
|---|---|---|
| Servo SG90 | Señal (naranja) | GPIO13 (cable `SERVO`) |
| Servo SG90 | V+ (rojo) / GND (marrón) | Fuente 5 V / GND común |
| MQ-2 | AO | Divisor: AO → 10 kΩ → **GPIO34** → 15 kΩ → GND, con 100 nF de GPIO34 a GND (cable `MQ2`) |
| MQ-2 | VCC / GND | Fuente 5 V / GND común |
| LED de estado | Ánodo, con su resistencia | GPIO32 |

El divisor deja 5 V × 15 / 25 = **3.0 V** en GPIO34. **Antes de conectar el AO real**, comprobarlo con la punta del AO en +5 V: el multímetro debe marcar unos 3.0 V en GPIO34, nunca más de 3.3 V.

**Placa 2 (luces y entrada).** Alimentada por USB.

| Componente | Conexión | Cable |
|---|---|---|
| Luz de la cocina | GPIO22 → 220 Ω → LED → GND | `L-COC` |
| Luz de la sala de estar | GPIO21 | `L-SAL` |
| Luz del comedor | GPIO23 | `L-COM` |
| Luz del baño | GPIO19 | `L-BAN` |
| Luz de la habitación | GPIO18 | `L-HAB` |
| PIR AM312 | OUT → GPIO26; VCC → 3V3; GND → GND | `PIR` |
| LED de estado | GPIO32 | — |

## 3. Puesta en marcha

### 3.1 AWS y Alexa (una sola vez)

La configuración de AWS IoT Core, las reglas, las Lambdas, DynamoDB y la skill está en el [Informe_P4 §3.4–3.5](Informe_P4.md#34-configuración-en-aws) y en [aws/](aws/). ⟨A cargo de Ricardo.⟩

Cada placa necesita su propio *Thing* y su propio certificado: `smartloft-739264-vent` (placa 1) y `smartloft-739264-lights` (placa 2).

### 3.2 Firmware de las placas

1. Copia `include/secrets_vent.example.h` como `include/secrets_vent.h` y `include/secrets_lights.example.h` como `include/secrets_lights.h`. Completa en cada uno el WiFi, el endpoint de AWS IoT, el certificado raíz (`AmazonRootCA1.pem`) y **el certificado y la clave privada de esa placa**. **Nunca subas los `secrets_*.h` ni los certificados al repositorio**: están en `.gitignore`.
2. Si usas otros *Things*, cambia `LINK_CODE` en [include/config_common.h](include/config_common.h) (`smartloft-<LINK_CODE>-vent` / `-lights`).
3. Antes de la primera carga de la placa 1, pon en [include/config_vent.h](include/config_vent.h) los valores medidos: `gas::SUPPLY_MV` (tensión del bus de 5 V con carga), `gas::WARMUP_MS`, los umbrales por defecto y los ángulos de la ventana.
4. Carga cada firmware en su placa y abre el monitor:

```bash
pio run -e vent -t upload -t monitor
```

```bash
pio run -e lights -t upload -t monitor
```

Al arrancar, el monitor muestra `LINK_CODE 739264`. Cuando aparecen `MQTT_CONNECTED` y `GET_RX`, la placa está en línea. La placa 1 no da alarmas mientras el MQ-2 se calienta (`GAS_READY` marca el final); la placa 2 ignora el PIR los primeros 30 s (`PIR_READY`).

| Entorno | Placa | Para qué |
|---|---|---|
| `vent` | 1 | Firmware real, conectado a AWS |
| `lights` | 2 | Firmware real, conectado a AWS |
| `vent_local_test` | 1 | Sin AWS: los `delta` se escriben en el monitor serie; el gas se puede simular |
| `lights_local_test` | 2 | Sin AWS: los `delta` se escriben en el monitor serie |

## 4. Cómo usarlo: frases para Alexa

⟨A cargo de Ricardo: tabla de frases de la skill (luces, ventana, modo, umbrales, gas, presencia, vinculación).⟩

**Modos de la ventilación:**
- **Automático** (por defecto): la placa abre la ventana con `gas_pct ≥` umbral alto y la cierra con `gas_pct ≤` umbral bajo. La ventana no se maneja por voz.
- **Manual:** la ventana se abre y se cierra solo por voz; con alarma de gas no se puede cerrar. Si las alarmas se repiten (3 en 24 h), la Nube vuelve a automático.

## 5. Probar sin AWS (firmware en `*_local_test`)

Carga el firmware de prueba y escribe los `delta` en el monitor serie, una línea por orden:

```bash
pio run -e vent_local_test -t upload -t monitor
```

| Para… | Escribe | Qué debe pasar |
|---|---|---|
| Simular gas (solo `vent_local_test`) | `{"state":{"sim_gas_pct":45}}` | Termina el calentamiento; con 45 ≥ umbral alto: `GAS_ALARM_ON` y, en automático, la ventana se abre |
| Volver al sensor real | `{"state":{"sim_gas_pct":-1}}` | `GAS_SIMULATION active=0` |
| Modo manual | `{"state":{"mode":"manual","cmd_origin":"voice"}}` | `MODE_APPLIED mode=manual origin=voice` |
| Abrir la ventana (en manual) | `{"state":{"window":"open","cmd_origin":"voice"}}` | El servo se mueve y el reporte trae `"desired":{"window":null,"cmd_origin":null}` |
| Cambiar umbrales | `{"state":{"gas_high_pct":40,"gas_low_pct":25}}` | `THRESHOLDS_APPLIED` y se guardan en la NVS |
| Encender una luz (`lights_local_test`) | `{"state":{"light_kitchen":"on","cmd_origin":"voice"}}` | Se enciende el LED de la cocina y sale `light_changed` |

## 6. Pruebas automáticas y herramientas

Los scripts que hablan con la placa necesitan `pyserial`; el Python de PlatformIO ya lo trae (`%USERPROFILE%\.platformio\penv\Scripts\python.exe`).

**Firmware sin AWS (B02):** con el firmware `*_local_test` cargado y el monitor cerrado:

```bash
python tools/serial_check.py --board vent --port COM3 --log docs/evidencias_p4/B02/B02_vent_ESP32.log
```

```bash
python tools/serial_check.py --board lights --port COM4 --log docs/evidencias_p4/B02/B02_lights_ESP32.log
```

Agrega `--skip-heartbeat` para no esperar los 60 s del último caso.

**Grabar el log de una placa sin reiniciarla:**

```bash
python tools/serial_logger.py --port COM3 --out logs/A08_vent.log
```

**Medir los requisitos desde los logs** (una línea PASS/FAIL por requisito; con `--dynamo`, la integridad y la latencia del almacenamiento):

```bash
python tools/analyze_log.py logs/A08_vent.log logs/A08_lights.log --dynamo smartloft-data.csv -o analisis.txt
```

**Secretos en el repositorio:**

```bash
python tools/check_secrets.py
```

**Calibración del MQ-2:** programa aparte en [tools/mq2_probe/](tools/mq2_probe/), que imprime una lectura por segundo y marca con el botón BOOT los momentos en que se acerca y se retira el humo.

## 7. Estructura del repositorio

| Ruta | Contenido |
|---|---|
| [lib/SmartObjectCore/](lib/SmartObjectCore/) | Código común a las dos placas: conexión, Shadow, reporte, log y salud |
| [src/vent/](src/vent/) | Firmware de la placa 1: gas, ventana, lógica de ventilación y NVS |
| [src/lights/](src/lights/) | Firmware de la placa 2: luces por zona y PIR |
| [include/](include/) | `config_common.h`, `config_vent.h`, `config_lights.h` (todas las constantes) y las plantillas `secrets_*.example.h` |
| [lambda/](lambda/), [alexa/](alexa/), [aws/](aws/) | Nube: Lambdas, modelo de la skill y configuración exportada |
| [tools/](tools/) | Scripts de prueba, análisis y calibración |
| [docs/](docs/) | Evidencias de la P4 y de la P3, diagramas y fotos |

Para agregar un sensor o actuador, se implementa la interfaz `DeviceComponent` y se suma el objeto al arreglo `components[]` del `main.cpp` de su placa; el código del Shadow no cambia.

## 8. Eventos del log de las placas

Cada línea tiene el formato `[t_ms|UTC] EVENTO detalle`: `t_ms` es el tiempo desde el arranque y `UTC`, la hora NTP (o `-` antes de sincronizar).

| Evento | Significado |
|---|---|
| `BOOT`, `RESET_REASON`, `LINK_CODE` | Arranque, motivo del reinicio y código de vinculación |
| `WIFI_*`, `MQTT_*`, `TIME_SYNCED` | Estado de la conexión y del reloj |
| `GET_TX`, `GET_RX` | Pedido del Shadow completo al conectarse |
| `DELTA_RX version=N` | Orden recibida; `STALE_IGNORED` descarta versiones repetidas o viejas |
| `GAS_SAMPLE`, `GAS_READY` | Lectura del MQ-2 cada 1 s y fin del calentamiento |
| `GAS_ALARM_ON`, `GAS_ALARM_OFF`, `EDGE_ACTION` | Cambios de la alarma y movimientos de la regla automática |
| `ACTUATOR_START`, `ACTUATOR_DONE` | Movimiento del servo (con su origen) y su confirmación (400 ms) |
| `MODE_APPLIED`, `THRESHOLDS_APPLIED`, `COMMAND_REJECTED` | Órdenes de modo y umbrales aplicadas, u órdenes rechazadas y por qué |
| `SETTINGS_LOADED`, `SETTINGS_SAVED` | Modo y umbrales leídos o guardados en la NVS |
| `LIGHT_APPLIED` | Luz de una zona cambiada (con su origen) |
| `PIR_READY`, `PRESENCE_DETECTED`, `PRESENCE_CLEARED` | Fin del calentamiento del PIR y cambios de presencia |
| `REPORT_TX seq event origin`, `REPORT_TX_FAILED` | Reporte publicado, o perdido por falta de conexión |
| `HEALTH` | Cada 60 s: tiempo encendido, memoria, señal WiFi, caídas y `loop()` más largo |
| `INVALID_VALUE`, `JSON_ERROR`, `UPDATE_REJECTED` | Errores |
