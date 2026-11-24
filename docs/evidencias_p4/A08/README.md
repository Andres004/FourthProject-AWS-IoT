# A08 — Integridad y latencia del almacenamiento

- Fecha y hora: 24/11/2026, 08:19:13–09:25:13 (Bolivia) / 12:19:13–13:25:13 UTC (66 min)
- Responsable: Dabner
- Firmware: `vent` y `lights` (commit `435c9fb` + `MQTT_SOCKET_TIMEOUT_S = 10`); las dos placas se reiniciaron al empezar (`seq` desde 1) y no se tocaron hasta el final
- Red: hotspot de celular a 30–50 cm (RSSI −67 a −17 dBm en la placa 1, −57 a −25 dBm en la placa 2; ver D-07 en el informe)
- Requisitos: RF10 (reglas que invocan la Lambda), RF11 (validar y guardar), RF12 (eventos con origen), RNF7 (integridad ≥ 99 %), RNF8 (latencia ≤ 5 s)
- Durante la corrida se hicieron A01–A04, A06 y A07: hubo órdenes por voz, 3 alarmas de gas y una intervención de la Nube, así que se guardaron lecturas y eventos de todos los orígenes
- Archivos:
  - [A08_vent_ESP32.log](A08_vent_ESP32.log), [A08_lights_ESP32.log](A08_lights_ESP32.log): logs de las dos placas
  - [A08_smartloft-data_completo.csv](A08_smartloft-data_completo.csv): exportación de la tabla `smartloft-data` (230 ítems, incluye conexiones anteriores a la corrida)
  - [A08_smartloft-data_ventana.csv](A08_smartloft-data_ventana.csv): los 176 ítems con `timestamp` dentro de la ventana de la corrida
  - [A08_analisis_logs.txt](A08_analisis_logs.txt): salida de [analyze_log.py](../../../tools/analyze_log.py) con `--dynamo`

## Cómo se mide

- **Integridad:** por placa, `seq` distintos guardados en DynamoDB / (`seq` máx − mín + 1). Además, cada `seq` de una línea `REPORT_TX` del log se busca en DynamoDB.
- **Latencia:** `storedTs − deviceTs` (de la publicación en la placa a la escritura en la Lambda; dos relojes: NTP de la placa y AWS) y `storedTs − timestamp` (de la regla de IoT a la escritura; un solo reloj, AWS). Se comprueba que no haya valores negativos, que indicarían relojes desfasados.

## Resultados

| Medida | Placa 1 (`vent`) | Placa 2 (`lights`) | Criterio | Veredicto |
|---|---|---|---|---|
| Reportes publicados (log) | 96 (`seq` 1–96), 0 fallidos | 80 (`seq` 1–80), 0 fallidos | — | INFO |
| Ítems guardados en la ventana | 96 (`seq` 1–96) | 80 (`seq` 1–80) | — | INFO |
| **Integridad** | **100.00 %** (96 / 96) | **100.00 %** (80 / 80) | ≥ 99 % | PASS |
| `REPORT_TX` del log que no están en DynamoDB | 0 / 96 | 0 / 80 | 0 | PASS |
| **Latencia** `storedTs − deviceTs` | mín. 262 / mediana 325 / p95 490 / **máx. 655 ms** | mín. 265 / mediana 320 / p95 525 / **máx. 642 ms** | ≤ 5000 ms | PASS |
| Valores negativos (relojes desfasados) | 0 | 0 | 0 | PASS |
| Regla → escritura `storedTs − timestamp` (solo reloj de AWS) | mediana 80 / máx. 214 ms | mediana 79 / máx. 151 ms | — | INFO |
| Lecturas / eventos guardados | 81 / 15 | 67 / 13 | — | INFO |
| Eventos por tipo | `boot` 1, `gas_alarm_on` 3, `gas_alarm_off` 3, `window_changed` 4, `mode_changed` 2, `thresholds_changed` 2 | `boot` 1, `light_changed` 8, `presence_detected` 2, `presence_cleared` 2 | — | INFO |
| `origin` en los ítems | `boot` 28, `voice` 24, `cloud` 1, `edge` 43 | `boot` 26, `voice` 54 | Los 4 orígenes (RF12) | PASS |
| Mensajes por hora (con la actividad de las pruebas) | 87 | 73 | — | Base de B04 |

**Análisis.** De los ≈ 325 ms de latencia típica, ≈ 80 ms son el tramo regla → Lambda → DynamoDB (medido con un solo reloj) y el resto es la publicación MQTT desde la placa y el servicio del Shadow. La latencia máxima (655 ms) está 7.6 veces por debajo del límite. No hubo valores negativos, así que el reloj NTP de las placas y el de AWS concuerdan a menos de ≈ 260 ms.

**Descarte de inválidos.** A las 13:43 UTC se publicó dos veces, desde el MQTT test client de la consola, un reporte inválido en el *Thing* de prueba `smartloft-518306-vent` (para no tocar las placas de la corrida):

```json
{"state":{"reported":{"gas_pct":"abc","window":"half","event":"heartbeat","seq":-1,"device_ts":0}}}
```

La regla lo entregó a la Lambda de datos, que **no lo guardó** y registró `{"log": "DATA_DISCARDED", "reason": "missing_origin", "thingName": "smartloft-518306-vent", "event": "heartbeat"}` en las dos invocaciones ([A08_01](A08_01_cloudwatch_data_discarded.webp), [A08_02](A08_02_cloudwatch_data_discarded_reason.png)). El motivo es el primer error que encuentra la validación (falta `origin`); el reporte tenía además `gas_pct` no numérico, `window` fuera de su lista, `seq` negativo y le faltaban atributos. Las dos invocaciones terminaron en `DATA_DISCARDED` y ninguna en `DATA_STORED`: 2 / 2 inválidos descartados. La validación de cada campo por separado está cubierta por 34 pruebas unitarias de la Lambda de datos ([B01](../B01/README.md)).

A las 18:29 UTC se publicaron, en el mismo *Thing* de prueba, reportes **completos y válidos salvo en un solo campo**, para comprobar que cada error se detecta por sí mismo ([A08_03](A08_03_cloudwatch_motivos_distintos.webp)):

| Hora (UTC) | Único campo inválido | `reason` registrado | ¿Guardado? |
|---|---|---|---|
| 18:29:45.772 | `gas_pct: 150` (fuera de 0–100) | `bad_gas_pct` | No |
| 18:29:49.386 | `window: "half"` | `bad_window` | No |
| 18:29:57.851 | `gas_low_pct: 20` con `gas_high_pct: 15` | `low_not_below_high` | No |

Con los dos de las 13:43 (`missing_origin`) suman 5 reportes inválidos y **4 motivos distintos**, todos descartados. El caso `seq` negativo (`bad_seq`) está cubierto por las pruebas unitarias de B01.

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Inválidos descartados | 5 / 5 con 4 motivos distintos (`DATA_DISCARDED`, ningún `DATA_STORED`) | 100 % | PASS |

**Lectura de [A08_analisis_logs.txt](A08_analisis_logs.txt).** El script imprime todas sus secciones. Las líneas `FAIL` que aparecen no contradicen el resultado: "longest loop 2913 / 2213 ms" es la conexión MQTT/TLS del primer minuto, explicada en [A11](../A11/README.md); "shortest gap 988 / 987 ms" mide entre líneas `REPORT_TX`, que se escriben después de publicar (el firmware separa el inicio de cada publicación por ≥ 1000 ms); y "A05 smoke cycles 0" es el criterio de A05, que no aplica a esta corrida.

**Veredicto: PASS** (RF10, RF11, RF12, RNF7, RNF8).
