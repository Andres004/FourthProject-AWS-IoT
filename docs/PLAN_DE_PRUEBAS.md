# Plan de pruebas — Práctica 3

Este documento define los requerimientos medibles, el valor declarado de cada uno y la prueba que lo verifica. Los resultados y la evidencia de cada prueba quedan en [docs/evidencias/](evidencias/), en una carpeta por prueba, y luego se copian al informe (§4 y §5).

Cada criterio de éxito sale de un valor declarado aquí o de una constante del código ([config.h](../include/config.h) y [lambda_function.py](../lambda/lambda_function.py)), así el veredicto no depende de una apreciación. Los tiempos y conteos se calculan con [tools/analyze_log.py](../tools/analyze_log.py), que lee el log de la ESP32 y el de la Lambda y escribe una línea por requisito, terminada en `PASS`, `FAIL`, `NOT ENOUGH DATA` o `INFO`.

## 1. Requerimientos

### 1.1 Funcionales

RF1 a RF9 son los de la consigna. RF10 a RF12 se agregan porque cierran casos que la consigna deja abiertos y que afectan la confiabilidad del sistema.

| ID | Requerimiento | Criterio de aceptación |
|---|---|---|
| RF1 | Detectar presencia en la entrada con el PIR AM312. | `PRESENCE_ON` al detectar movimiento, después de 30 s de calentamiento (`PIR_READY`). `presence` se mantiene `true` 10 s después del último movimiento. |
| RF2 | Reportar periódicamente `presence`, `door` y `servo_angle` en `reported`. | Cada reporte trae los tres atributos. Con la conexión activa, nunca pasan más de 61.5 s entre dos reportes (heartbeat de 60 s). |
| RF3 | Aplicar el `delta` en el servo y confirmarlo en `reported`. | Un `delta` válido mueve el servo y su posición aparece en `reported` en ≤ 1.5 s desde `DELTA_RX`. |
| RF4 | Responder por voz el valor del sensor, leyendo `reported`. | "Sí, se detecta a alguien…" o "No, no se detecta…", según `reported.presence`, nunca según `desired`. |
| RF5 | Ejecutar por voz abrir y cerrar, escribiendo `desired`. | `desired.door` cambia a `open` o `closed` en el Shadow del Thing del usuario. |
| RF6 | Responder por voz el estado de la puerta. | "La puerta está abierta/cerrada" según `reported.door`; si `desired` difiere, menciona la orden pendiente. |
| RF7 | Vincular con un código y que persista entre sesiones. | El ítem `userId → thingName, fechaVinculacion` queda en DynamoDB y la skill lo usa al volver a abrirla. |
| RF8 | Resolver el Thing de cada usuario por su `userId`. | Un usuario sin vincular recibe la guía para hacerlo; dos usuarios vinculados a Things distintos solo actúan sobre el suyo. |
| RF9 | Validar el Thing antes de vincular y permitir cambiar o eliminar la vinculación. | Un código inválido o un Thing inexistente no se guarda; volver a vincular reemplaza el ítem; desvincular lo borra. |
| RF10 | Confirmar al usuario que la puerta se movió. | Tras un comando, la Lambda espera `reported.door` hasta 3 s y dice "Listo, la puerta está abierta/cerrada"; si no llega, dice que no recibió confirmación. |
| RF11 | Avisar cuando el objeto está desconectado. | Si el último reporte tiene más de 150 s (2.5 heartbeats), las consultas lo advierten y los comandos avisan que se aplicarán al reconectarse. |
| RF12 | Rechazar comandos inválidos y repetidos sin mover el servo. | Un valor fuera de `open`/`closed`, un JSON mal formado o un `delta` con versión repetida o anterior quedan registrados (`INVALID_VALUE`, `JSON_ERROR`, `STALE_IGNORED`) y el servo no se mueve. |

### 1.2 No funcionales

| ID | Atributo | Valor declarado | Método de verificación | Prueba |
|---|---|---|---|---|
| RNF1 | Estabilidad | ≥ 15 min continuos con 0 reinicios, 0 caídas de WiFi o MQTT, iteración de `loop()` ≤ 500 ms y pérdida de heap libre ≤ 4096 bytes entre la primera y la última línea `HEALTH`. | Líneas `HEALTH` (cada 60 s) y `BOOT`/`RESET_REASON` del log de la ESP32. | A10 |
| RNF2 | Exactitud del sensor y del actuador | PIR: detección del 100 % de los cruces de una persona a 0.5, 1.0 y 2.0 m (5 cruces por distancia) y 0 falsos positivos en 5 min sin personas. Servo: error ≤ 5° respecto de un transportador en 0° y 90°. | Conteo de `PRESENCE_ON` por distancia medida con cinta métrica; ángulo medido con transportador en fotos. | A06 |
| RNF3 | Tiempo de respuesta extremo a extremo | ≤ 3 s desde que la Lambda recibe el comando hasta que la puerta está confirmada, en ≥ 20 comandos. | `confirm_ms` de la Lambda (un solo reloj) y, de forma cruzada, `DELTA_RX`/`ACTUATOR_DONE` de la ESP32 con hora NTP. | A05 |
| RNF4 | Frecuencia de reporte | Por evento: ≤ 1.1 s desde el cambio de estado. Periódico: cada 60 s (máx. 61.5 s entre reportes). Consumo: alrededor de 1440 mensajes por día en reposo. | Intervalos `REPORT_TX` del log y prueba automática B02. | A10, B02 |
| RNF5 | Reconexión y sincronización | WiFi reintenta cada 10 s ± 0.5 s; tras recuperar la red, la orden pendiente se aplica en ≤ 10 s desde `WIFI_CONNECTED`, sin intervención. | Secuencia `WIFI_LOST` → `WIFI_CONNECTED` → `MQTT_CONNECTED` → `GET_RX` → `ACTUATOR_DONE`. | A07, A08 |
| RNF6 | Seguridad | 0 secretos en los archivos del repositorio y en todo su historial; archivos de secretos ignorados por git; plantilla publicada. | [tools/check_secrets.py](../tools/check_secrets.py), con un control positivo sobre el `secrets.h` real. | B03 |

**Justificación de los valores**

- **RNF2 (0.5 a 2.0 m):** es la zona frente a la puerta de un monoambiente donde se para quien llega. El AM312 es un sensor binario, así que su exactitud se expresa como tasa de detección y falsos positivos, no como error en una unidad. Las distancias de 2.5 y 3.0 m se miden solo como información.
- **RNF3 (≤ 3 s):** es la referencia de la consigna. El servo tarda 400 ms (`SETTLE_TIME_MS`), así que el resto del presupuesto queda para la nube y la red.
- **RNF4:** la puerta y la presencia son eventos discretos, por eso se reportan de inmediato (orden de 1 s, como pide la consigna para una puerta). El mínimo de 1 s entre mensajes evita ráfagas si el PIR oscila. El heartbeat de 60 s da 1440 mensajes por día en reposo; un heartbeat cada 10 s daría 8640, seis veces más, sin ganar nada, porque los cambios ya se reportan por evento.
- **RF11 (150 s):** 2.5 heartbeats tolera un mensaje perdido más el tiempo de una reconexión, sin dar por desconectado un objeto que solo se demoró.
- **RNF5 (≤ 10 s):** después de `WIFI_CONNECTED` quedan la conexión TLS y MQTT, la espera de 0.5 s antes de `/get` y los 400 ms del servo. El límite de la conexión TLS es de 8 s + 8 s (`TLS_CONNECT_TIMEOUT_S`, `TLS_HANDSHAKE_TIMEOUT_S`), pero una conexión normal tarda unos pocos segundos; A07 y A08 miden el valor real.

## 2. Plan de pruebas

**A. Físicas y de entorno:** requieren actuar sobre el montaje, la red o la skill. El veredicto sale de los logs analizados y de las capturas.
**B. Automáticas:** el veredicto sale solo del software.

| ID | Prueba | Requisitos | Duración aprox. |
|---|---|---|---|
| A01 | Vinculación, cambio y desvinculación por voz | RF7, RF8, RF9 | 15 min |
| A02 | Dos usuarios con Things distintos | RF8, RF9 | 10 min |
| A03 | Consulta del sensor por voz | RF1, RF4 | 10 min |
| A04 | Comandos y estado de la puerta por voz | RF3, RF5, RF6, RF10 | 15 min |
| A05 | Tiempo de respuesta extremo a extremo | RNF3, RF10 | junto con A10 |
| A06 | Exactitud del PIR y del servo | RNF2, RF1 | 20 min |
| A07 | Caída de WiFi con orden pendiente | RNF5, RF11 | 15 min |
| A08 | Corte de energía con orden pendiente | RNF5, RF10 | 10 min |
| A09 | Comandos inválidos desde AWS | RF12 | 10 min |
| A10 | Estabilidad de 15 min | RNF1, RF2, RNF4 | 20 min |
| B01 | Pruebas unitarias de la Lambda | RF4–RF11 | 1 min |
| B02 | Firmware con transporte serie | RF2, RF3, RF12, RNF4 | 3 min |
| B03 | Secretos en el repositorio | RNF6 | 1 min |

**Orden de ejecución:** B01 y B03 primero; luego B02, que necesita el firmware `local_test`; después se carga el firmware real y la Lambda nueva, y se hacen A01 a A10.

### Preparación común

- **Log de la ESP32:** [tools/serial_logger.py](../tools/serial_logger.py) graba el puerto serie en segundo plano, sin reiniciar la placa (DTR y RTS liberados), y vuelve a abrir el puerto solo si la placa se desenchufa. Cada evidencia es el tramo del log entre la hora de inicio y fin de la prueba, con las horas UTC de las líneas. Como alternativa, el monitor de PlatformIO guarda cada sesión en `logs/` (filtro `log2file`).
- **Log de la Lambda:** CloudWatch → **Logs Insights** → grupo `/aws/lambda/monoambiente-skill`, rango de tiempo de la prueba, y esta consulta:

  ```text
  fields @timestamp, @message
  | filter @message like /SKILL_REQUEST/
  | sort @timestamp asc
  | limit 1000
  ```

  **Run query** → **Export results** → **Download table (CSV)**. Guárdalo con el nombre que se indica.
- **Análisis:** desde la raíz del proyecto:

  ```bash
  python tools/analyze_log.py docs/evidencias/AXX/archivo.log docs/evidencias/AXX/cloudwatch.csv -o docs/evidencias/AXX/AXX_analisis.txt
  ```

- **Skill I/O:** en el simulador de Alexa marca **Skill I/O** y toma la captura con el JSON visible cuando se indica.
- **Videos:** con el celular, mostrando a la vez la puerta y la pantalla con el simulador o el monitor serie.

### A01. Vinculación, cambio y desvinculación por voz

1. En DynamoDB borra el ítem del usuario del simulador si existe, y toma captura de la tabla.
2. En el simulador escribe, en orden, y captura cada respuesta:

| Paso | Frase | Respuesta esperada |
|---|---|---|
| 1 | abre monoambiente inteligente | "Bienvenido. Todavía no tienes una casa vinculada…" |
| 2 | hay alguien en la puerta | Guía para vincular (RF8) |
| 3 | vincula mi casa con el código uno dos tres | "El código debe tener seis dígitos…" |
| 4 | vincula mi casa con el código nueve nueve nueve nueve nueve nueve | "No encontré ninguna casa con el código 9 9 9 9 9 9…" |
| 5 | vincula mi casa con el código siete tres nueve dos seis cuatro | "Listo, tu casa con el código … quedó vinculada" → captura de DynamoDB |
| 6 | vincula mi casa con el código siete tres nueve dos seis cuatro | "Tu casa ya estaba vinculada…" |
| 7 | cambia mi casa al código cinco uno ocho tres cero seis | "Listo, cambié tu vinculación…" → captura de DynamoDB |
| 8 | vincula mi casa con el código siete tres nueve dos seis cuatro | "Listo, cambié tu vinculación…" |
| 9 | desvincula mi casa | "Tu casa quedó desvinculada" → captura de DynamoDB |
| 10 | desvincula mi casa | "No tienes ninguna casa vinculada" |
| 11 | vincula mi casa con el código siete tres nueve dos seis cuatro | Vinculada |
| 12 | detener | "Hasta luego" (cierra la sesión) |
| 13 | abre monoambiente inteligente | "Bienvenido. Puedes abrir o cerrar la puerta…" (persistió, RF7) |

3. Exporta CloudWatch como `A01_cloudwatch.csv` y analízalo.

**Criterio:** las 13 respuestas coinciden; DynamoDB muestra un solo ítem por usuario en cada captura, con `thingName` correcto y `fechaVinculacion`; el análisis muestra los `result` `not_linked`, `invalid_code`, `thing_not_found`, `linked`, `already_linked`, `changed`, `unlinked` y 0 `error`.

### A02. Dos usuarios con Things distintos

1. Deja el simulador vinculado a `739264` (A01).
2. En la Lambda, ejecuta el evento de prueba `vincular2` (`test-user-2` → `518306`).
3. Crea y ejecuta el evento `abrir2`: el mismo JSON de `vincular2`, pero con `"name": "OpenDoor"` y `"slots": {}`.
4. Captura: el Shadow de `monoambiente-518306` (con `desired.door = "open"`), el Shadow de `monoambiente-739264` (sin cambios) y DynamoDB con los dos ítems.
5. En el simulador: "cómo está la puerta". Debe responder según `monoambiente-739264`.

**Criterio:** cada usuario solo modifica el Shadow de su Thing, la puerta real no se mueve en el paso 3 y la respuesta de `abrir2` avisa que esa casa está desconectada (no tiene ESP32).

### A03. Consulta del sensor por voz

1. Monitor serie abierto; espera `PIR_READY`.
2. Párate frente al sensor y, sin salir, escribe "hay alguien en la puerta" → captura.
3. Sal del campo del sensor, espera `PRESENCE_OFF` (≥ 10 s) y escribe "detectas a alguien en la entrada" → captura.
4. Repite 3 veces cada caso, alternando las 4 frases de `GetPresence`.
5. Graba en video un ciclo completo con el monitor serie visible.

**Criterio:** 6 de 6 respuestas coinciden con `reported.presence` en ese momento; en el log, cada `PRESENCE_ON`/`PRESENCE_OFF` tiene su `REPORT_TX` en ≤ 1.1 s.

### A04. Comandos y estado de la puerta por voz

| Paso | Frase | Esperado |
|---|---|---|
| 1 | abre la puerta | Servo a 90°; "Listo, la puerta está abierta" |
| 2 | cuál es el estado de la puerta | "La puerta está abierta." |
| 3 | abre la puerta | "La puerta ya está abierta." y no se mueve |
| 4 | cierra la puerta | Servo a 0°; "Listo, la puerta está cerrada" |
| 5 | la puerta está cerrada | "La puerta está cerrada." |
| 6 | abrir la puerta / cerrar la puerta | Las variantes de las frases también funcionan |

Después de los pasos 1 y 4, captura el Shadow: `desired.door` = `reported.door` y sin `delta`. Graba en video los pasos 1 y 4.

**Criterio:** 6 de 6 respuestas correctas; en el log, cada `DELTA_RX` válido tiene `ACTUATOR_DONE` y `REPORT_TX` con la nueva posición en ≤ 1.5 s (RF3 `PASS`).

### A05 y A10. Tiempo de respuesta y estabilidad (misma corrida)

1. Con la ESP32 ya conectada y el registro del log activo (sin reiniciarla).
2. Durante **al menos 17 min**, sin tocar la placa:
   - cada 40 s aproximadamente, alterna "abre la puerta" y "cierra la puerta" en el simulador, hasta completar **al menos 20 comandos** (se hicieron 28);
   - cada 3 min, pasa frente al sensor.
3. Graba en video 3 de los comandos con un cronómetro visible.
4. Cierra el monitor y guarda `A10_ESP32.log`; exporta CloudWatch del mismo intervalo como `A05_cloudwatch.csv`.
5. Analiza los dos juntos.

**Criterio A05 (RNF3):** `RNF3 commands confirmed within 3000 ms` → `PASS` con ≥ 20 comandos, y `RNF3 Lambda start -> servo done` → `PASS`.
**Criterio A10 (RNF1, RF2, RNF4):** todas las líneas `RNF1`, `RF2/RNF4` y `RNF4` → `PASS`.

### A06. Exactitud del PIR y del servo

**PIR, detección.** Marca con cinta en el piso las distancias 0.5, 1.0 y 2.0 m frente al sensor (foto con la cinta métrica).

1. Para cada distancia, espera quieto fuera del campo hasta que no haya presencia, y cruza **5 veces** caminando a ritmo normal de lado a lado, esperando **12 s** quieto entre cruces (más que los 10 s de retención).
2. Se anota la hora de inicio de cada bloque; cada cruce cuenta si su `PRESENCE_ON` llega después de un `PRESENCE_OFF`.

**PIR, falsos positivos.** Deja el sensor apuntando a la entrada vacía durante 5 min, sin nadie en la habitación.

**Servo.** Con un transportador centrado en el eje, toma 2 fotos en `closed` (0°) y 2 en `open` (90°), abriendo y cerrando por voz.

**Criterio:** 15 de 15 cruces detectados; 0 `PRESENCE_ON` en los 5 min sin personas; las 4 fotos del servo dentro de ±5°.

> Se redujo de 40 cruces a 15 por tiempo. Con 15 cruces, un 100 % observado no permite afirmar una tasa de detección mayor al 95 % con confianza estadística; el informe lo declara como limitación.

### A07. Caída de WiFi con orden pendiente

1. Puerta cerrada y monitor abierto.
2. Apaga el hotspot del celular. Espera **3 min** (para pasar los 150 s).
3. En el simulador (desde la PC con otra red): "hay alguien en la puerta" → debe advertir que la casa no se reporta (RF11). Captura.
4. "abre la puerta" → "Envié la orden, pero tu casa está desconectada…" Captura del Shadow con `delta`.
5. Graba en video, con cronómetro: enciende el hotspot y espera a que la puerta se abra sola.
6. Repite con "cierra la puerta". Guarda `A07_ESP32.log` y `A07_cloudwatch.csv`.

**Criterio:** `RNF5 WiFi retries every 10000 +/- 500 ms` y `RNF5 pending desired applied … (<= 10000)` → `PASS` en las dos repeticiones; las respuestas de los pasos 3 y 4 coinciden.

> La PC con el simulador debe tener internet por otra vía (otra red WiFi o cable), porque el hotspot apagado deja sin red a la ESP32.

### A08. Corte de energía con orden pendiente

1. Puerta cerrada. Desconecta el USB de la ESP32.
2. En el simulador: "abre la puerta". Como el último reporte tiene menos de 150 s, la Lambda espera y responde que no recibió confirmación (RF10). Captura.
3. Graba en video: conecta el USB, abre el monitor de inmediato y espera a que la puerta se abra sola.
4. Repite con "cierra la puerta". Guarda `A08_ESP32_1.log` y `A08_ESP32_2.log`.

**Criterio:** en cada arranque, `GET_RX` trae el `desired` pendiente y `RNF5 pending desired applied` → `PASS`.

### A09. Comandos inválidos desde AWS

En AWS IoT → **MQTT test client** → **Publish**, al tema `$aws/things/monoambiente-739264/shadow/update`, publica uno por uno, con el monitor abierto:

| Caso | Mensaje | Esperado en el log |
|---|---|---|
| 1 | `{"state":{"desired":{"door":"medio"}}}` | `INVALID_VALUE door=medio`, sin movimiento |
| 2 | `{"state":{"desired":{"door":5}}}` | `INVALID_VALUE door=<not a string>`, sin movimiento |
| 3 | `{"state":{"desired":{"door":"OPEN"}}}` | `INVALID_VALUE door=OPEN`, sin movimiento |
| 4 | `{"state":{"desired":{"door":"open"}}}` | Se abre (el sistema sigue sano) |
| 5 | `{"state":{"desired":{"door":"closed"}}}` | Se cierra y el `delta` desaparece |

Captura del Shadow después del caso 1 (muestra el `delta`) y del caso 5 (sin `delta`). Pregunta "cómo está la puerta" después del caso 1: debe responder con `reported`. Guarda `A09_ESP32.log`.

**Criterio:** 3 de 3 inválidos registrados sin movimiento y 2 de 2 válidos aplicados. Los casos repetidos y desordenados (`STALE_IGNORED`) se prueban en B02, porque AWS no permite reenviar un `delta` viejo a voluntad.

### B01. Pruebas unitarias de la Lambda

```bash
python -m unittest discover -s lambda/tests -v 2>&1 | tee docs/evidencias/B01/B01_salida.txt
```

**Criterio:** todas las pruebas `ok`.

### B02. Firmware con transporte serie

1. Tapa el PIR con un vaso o una caja para que no genere eventos.
2. Carga el firmware de prueba: `pio run -e local_test -t upload`.
3. Con el monitor cerrado, ejecuta:

   ```bash
   python tools/serial_check.py --port COM3 --log docs/evidencias/B02/B02_ESP32.log
   ```

4. Copia la salida de la consola en `B02_salida.txt`.

**Criterio:** `RESULT 16/16 cases PASS`.

### B03. Secretos en el repositorio

```bash
python tools/check_secrets.py -o docs/evidencias/B03/B03_salida.txt
```

**Criterio:** las cuatro líneas `RNF6` y el control → `PASS`.

## 3. Estructura de la evidencia

```text
docs/evidencias/
  A01/  README.md, capturas (A01_paso05_dynamodb.png…), A01_cloudwatch.csv, A01_analisis.txt
  A02/  …
  …
  B03/  README.md, B03_salida.txt
```

Cada carpeta tiene un `README.md` con la tabla de archivos (qué muestra cada uno) y la tabla de medidas con su criterio y veredicto, igual que en la Práctica 2.
