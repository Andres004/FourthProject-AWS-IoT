# Puerta inteligente de un monoambiente — SIS-234, Práctica 3

Un ESP32 abre y cierra una puerta (maqueta) con un servo SG90 y detecta con un sensor PIR AM312 si hay alguien en la entrada. Se controla por voz o texto desde la skill de Alexa **"monoambiente inteligente"**. Alexa nunca habla con el ESP32: todo pasa por el **Device Shadow** de AWS IoT Core.

```text
Usuario → Alexa (simulador) → AWS Lambda → DynamoDB (vinculación)
                                         → Device Shadow ⇄ ESP32 (MQTT/TLS) → servo + PIR
```

- **Informe técnico:** [Informe.md](Informe.md)
- **Plan de pruebas:** [docs/PLAN_DE_PRUEBAS.md](docs/PLAN_DE_PRUEBAS.md)
- **Evidencia de cada prueba:** [docs/evidencias/](docs/evidencias/README.md)
- **Configuración de AWS y Alexa exportada:** [aws/](aws/README.md), [alexa/](alexa/interaction-model.es-US.json)

---

## 1. Qué necesitas

| Hardware | Software y cuentas |
|---|---|
| ESP32 DOIT DevKit V1 (30 pines) | VS Code con PlatformIO |
| Servo SG90 | Python 3.11 o más reciente (para las pruebas automáticas y los scripts) |
| Sensor PIR AM312 | Cuenta de AWS (región `us-east-2`, Ohio) |
| LED y una resistencia (la única del circuito) | Cuenta de Amazon Developer (Alexa Developer Console) |
| Protoboard, cables y un cable USB | Una red WiFi de 2.4 GHz |

## 2. Conexiones

Todas las tierras son una sola: el GND del servo, del PIR, del LED y del ESP32 van a la misma línea de tierra.

| Componente | Pin del componente | Pin del ESP32 |
|---|---|---|
| Servo SG90 | Señal (naranja) | D13 (GPIO13) |
| Servo SG90 | V+ (rojo) | VIN (5 V del USB) |
| Servo SG90 | GND (marrón) | GND común |
| PIR AM312 | OUT | D26 (GPIO26) |
| PIR AM312 | VCC | VIN (5 V) |
| PIR AM312 | GND | GND común |
| LED de estado | Ánodo, a través de la resistencia | D32 (GPIO32) |
| LED de estado | Cátodo | GND común |

Esquema completo: [docs/img/circuito_objeto_inteligente.svg](docs/img/circuito_objeto_inteligente.svg). Foto del montaje: [docs/img/montaje.jpeg](docs/img/montaje.jpeg).

**LED de estado** (solo indicador, no es el actuador):

| LED | Significa |
|---|---|
| Parpadeo rápido | Sin WiFi |
| Parpadeo lento | Con WiFi, pero sin conexión con AWS |
| Encendido fijo | En línea con el Shadow |

## 3. Puesta en marcha

### 3.1 AWS y Alexa (una sola vez)

La configuración completa está en el [Informe §3.4–3.5](Informe.md) y en [aws/README.md](aws/README.md). En resumen:

1. **AWS IoT Core:** el Thing `monoambiente-739264` con Shadow clásico, su certificado activo y la política de IoT asociada.
2. **DynamoDB:** la tabla `user_thing`, con clave de partición `userId` (String).
3. **Lambda** `monoambiente-skill` (Python): código de [lambda/lambda_function.py](lambda/lambda_function.py), variables `IOT_ENDPOINT`, `IOT_REGION=us-east-2` y `TABLE_NAME=user_thing`, timeout de 7 s y disparador de Alexa.
4. **Skill de Alexa** en *Spanish (US)*: modelo de [alexa/interaction-model.es-US.json](alexa/interaction-model.es-US.json) y, en **Build → Endpoint**, el ARN de la Lambda.

Para armar el `.zip` de la Lambda:

```bash
python -m pip install -r lambda/requirements.txt -t lambda/package
```

```bash
copy lambda\lambda_function.py lambda\package\
```

```bash
python -c "import shutil; shutil.make_archive('lambda/lambda_deployment', 'zip', 'lambda/package')"
```

Luego, en la Lambda: **Code → Upload from → .zip file** con `lambda/lambda_deployment.zip`.

### 3.2 Firmware del ESP32

1. Copia `include/secrets.example.h` como `include/secrets.h` y completa el WiFi, el endpoint de AWS IoT, el certificado raíz, el certificado del dispositivo y la clave privada. **Nunca subas `secrets.h` al repositorio**: está en `.gitignore`.
2. Si usas otro Thing, cambia `LINK_CODE` en [include/config.h](include/config.h) para que coincida con su nombre (`monoambiente-<LINK_CODE>`).
3. Carga el firmware y abre el monitor:

```bash
pio run -e esp32doit-devkit-v1 -t upload -t monitor
```

Al arrancar, el monitor muestra `LINK_CODE 739264`, el código que se le dice a Alexa. Cuando aparecen `MQTT_CONNECTED` y `GET_RX`, el objeto está en línea. Durante los primeros 30 s el PIR se calienta y no reporta presencia (`PIR_READY` marca el final).

## 4. Cómo usarlo: frases para Alexa

En la [Alexa Developer Console](https://developer.amazon.com/alexa/console/ask), abre la skill → pestaña **Test** → **Development** → idioma **Spanish (US)**. Escribe las frases en el cuadro de texto (o mantén presionado el micrófono mientras hablas). Marca **Skill I/O** para ver el JSON.

| Para… | Escribe o di | Respuesta esperada |
|---|---|---|
| Abrir la skill | `abre monoambiente inteligente` | Sin casa vinculada: "Bienvenido. Todavía no tienes una casa vinculada…" · Vinculada: "Bienvenido. Puedes abrir o cerrar la puerta…" |
| Vincular tu casa | `vincula mi casa con el código siete tres nueve dos seis cuatro` | "Listo, tu casa con el código 739264 quedó vinculada." |
| Cambiar de casa | `cambia mi casa al código cinco uno ocho tres cero seis` | "Listo, cambié tu vinculación al código 518306." |
| Desvincular | `desvincula mi casa` | "Tu casa quedó desvinculada." |
| ¿Hay alguien? | `hay alguien en la puerta` · `detectas a alguien en la entrada` · `hay presencia en la puerta` | "Sí, se detecta a alguien en la entrada." / "No, no se detecta a nadie en la entrada." |
| Abrir la puerta | `abre la puerta` · `abrir la puerta` | El servo gira a 90° y Alexa dice "Listo, la puerta está abierta." |
| Cerrar la puerta | `cierra la puerta` · `cerrar la puerta` | El servo vuelve a 0° y Alexa dice "Listo, la puerta está cerrada." |
| Estado de la puerta | `cómo está la puerta` · `cuál es el estado de la puerta` | "La puerta está abierta/cerrada." (y menciona si hay una orden pendiente) |
| Ayuda | `ayuda` | Lista de lo que puede hacer |
| Salir | `detener` | "Hasta luego." |

El código se dice dígito por dígito. Sin una casa vinculada, cualquier consulta o comando responde con las instrucciones para vincularla.

## 5. Cómo probarlo (casos para la demo)

Cada caso indica qué hacer y qué debe pasar. Entre paréntesis está la prueba del informe que lo verificó.

| # | Caso | Pasos | Resultado esperado |
|---|---|---|---|
| 1 | **Usuario nuevo** (A01) | `abre monoambiente inteligente` → `hay alguien en la puerta` | Alexa pide vincular la casa antes de responder |
| 2 | **Código inválido** (A01) | `vincula mi casa con el código uno dos tres` | "El código debe tener seis dígitos…"; no se guarda nada |
| 3 | **Casa inexistente** (A01) | `vincula mi casa con el código nueve nueve nueve nueve nueve nueve` | "No encontré ninguna casa con el código 999999…" |
| 4 | **Vincular y persistir** (A01) | Vincular con 739264 → `detener` → `abre monoambiente inteligente` | En la sesión nueva recuerda la casa; DynamoDB muestra un ítem con `thingName` y `fechaVinculacion` |
| 5 | **Sensor** (A03) | Pararse frente al PIR → `hay alguien en la puerta`; salir 15 s → preguntar otra vez | "Sí…" y luego "No…" |
| 6 | **Comandos** (A04, A05) | `abre la puerta`, `cierra la puerta` | El servo se mueve y Alexa confirma en ~1 s |
| 7 | **Orden repetida** (A04) | `abre la puerta` con la puerta ya abierta | "La puerta ya está abierta." y el servo no se mueve |
| 8 | **Sin WiFi** (A07) | Apagar el WiFi 3 min → `hay alguien en la puerta` → `abre la puerta` → volver a encender el WiFi | Alexa avisa que la casa no se reporta y que la orden se aplicará al reconectar; la puerta se abre sola unos 4 s después de volver el WiFi |
| 9 | **Corte de energía** (A08) | Desenchufar el USB → `abre la puerta` → enchufar | La puerta arranca cerrada y se abre sola unos 4 s después |
| 10 | **Dos usuarios** (A02) | En la Lambda, un evento de prueba con otro `userId` vinculado a 518306 que pida abrir | Solo cambia el Shadow de `monoambiente-518306`; la puerta real no se mueve |
| 11 | **Valor inválido desde AWS** (A09) | En **MQTT test client**, publicar en `$aws/things/monoambiente-739264/shadow/update` el mensaje `{"state":{"desired":{"door":"medio"}}}` | El monitor muestra `INVALID_VALUE door=medio` y el servo no se mueve |

Para ver el Shadow: **AWS IoT → Things → monoambiente-739264 → Device Shadows → Classic Shadow**. Después de cada comando, `desired.door` y `reported.door` coinciden y no queda `delta`.

## 6. Pruebas automáticas

**Lambda (sin AWS ni Alexa):** 23 pruebas con DynamoDB y AWS IoT simulados. Necesitan la carpeta `lambda/package` (paso 3.1).

```bash
python -m unittest discover -s lambda/tests -v
```

**Firmware sin AWS:** el entorno `local_test` reemplaza AWS por el puerto serie. Tapa el PIR, carga ese firmware y, con el monitor cerrado, ejecuta los 16 casos:

```bash
pio run -e local_test -t upload
```

```bash
python tools/serial_check.py --port COM3 --log B02_ESP32.log
```

También se puede probar a mano: abre el monitor y escribe `{"state":{"door":"open"}}`.

**Secretos en el repositorio:**

```bash
python tools/check_secrets.py
```

**Análisis de logs** (log de la ESP32 y/o exportación de CloudWatch → una línea PASS/FAIL por requisito):

```bash
python tools/analyze_log.py logs/archivo.log cloudwatch.csv -o analisis.txt
```

Para grabar el log de la ESP32 sin reiniciarla: `python tools/serial_logger.py --port COM3 --out logs/sesion.log`.

## 7. Estructura del repositorio

| Ruta | Contenido |
|---|---|
| [src/](src/) | Firmware del ESP32, una clase por archivo |
| [include/config.h](include/config.h) | Todas las constantes: pines, tiempos, temas y contrato del Shadow |
| [include/secrets.example.h](include/secrets.example.h) | Plantilla de credenciales, sin valores reales |
| [lambda/](lambda/) | Backend de la skill y sus pruebas |
| [alexa/](alexa/), [aws/](aws/) | Configuración exportada |
| [tools/](tools/) | Scripts de prueba y análisis |
| [docs/](docs/) | Plan de pruebas, evidencia y diagramas |

Para agregar un sensor o actuador, se implementa la interfaz `DeviceComponent` y se registra el objeto en [src/main.cpp](src/main.cpp); el código del Shadow no cambia.

## 8. Eventos del log del ESP32

Cada línea tiene el formato `[t_ms|UTC] EVENTO detalle`: `t_ms` es el tiempo desde el arranque y `UTC`, la hora NTP (o `-` antes de sincronizar).

| Evento | Significado |
|---|---|
| `BOOT`, `RESET_REASON`, `LINK_CODE` | Arranque, motivo del reinicio y código de vinculación |
| `WIFI_*`, `MQTT_*`, `TIME_SYNCED` | Estado de la conexión y del reloj |
| `GET_TX`, `GET_RX` | Pedido del Shadow completo al conectarse |
| `DELTA_RX version=N` | Orden recibida; `STALE_IGNORED` descarta versiones repetidas o viejas |
| `ACTUATOR_START`, `ACTUATOR_DONE` | Movimiento del servo y su confirmación (400 ms) |
| `PIR_READY`, `PRESENCE_ON`, `PRESENCE_OFF` | Fin del calentamiento y cambios de presencia |
| `REPORT_TX reason=event\|heartbeat` | Reporte publicado en `reported` |
| `HEALTH` | Cada 60 s: tiempo encendido, memoria, señal WiFi, caídas y `loop()` más largo |
| `INVALID_VALUE`, `JSON_ERROR`, `UPDATE_REJECTED` | Errores |
