# A09 — Operación sin conexión y reconexión con órdenes pendientes

- Fecha y hora: 24/11/2026, 13:51–14:00 (Bolivia) / 17:51–18:00 UTC
- Responsable: Dabner
- Firmware: `vent` y `lights` (commit `435c9fb` + `MQTT_SOCKET_TIMEOUT_S = 10`); placa 1 en modo `auto`, umbrales 15 / 8
- Red: las placas en el hotspot del celular; la PC en otra red (WiFi de la casa), para usar el simulador de Alexa con el hotspot apagado
- Requisitos: RNF11 (operación sin conexión), RNF5 (reconexión), RF11 de la P3 (aviso de desconexión en la skill)
- Archivos: [A09_vent_ESP32.log](A09_vent_ESP32.log), [A09_lights_ESP32.log](A09_lights_ESP32.log), [A09_analisis.txt](A09_analisis.txt) (sección "RNF9 / RNF5" de [analyze_log.py](../../../tools/analyze_log.py)), capturas [A09_01](A09_01_consulta_sin_conexion.png) y [A09_02](A09_02_ordenes_encoladas.png); videos [A09_video_1.mp4](A09_video_1.mp4) y [A09_video_2.mp4](A09_video_2.mp4)
- Reloj: `millis()` de cada placa

## Parte 1 — la regla E1 sin Internet (hotspot apagado 17:51:46 → 17:54:16 UTC)

| t (ms, placa 1) | Evento |
|---|---|
| 483 927 | `MQTT_LOST state=-3` (se apagó el hotspot) |
| 502 985 → 503 395 | `GAS_ALARM_ON 83.1 %` → `EDGE_ACTION open` → `ACTUATOR_DONE` (410 ms) |
| 505 973 → 506 384 | `GAS_ALARM_OFF 6.9 %` → la ventana se cierra (411 ms) |
| 515 980 → 527 417 | Segundo ciclo: abre y cierra |
| 530 005 → 540 403 | Tercer ciclo: abre y cierra |
| 502 972 → 600 992 | 19 reportes no enviados: `REPORT_TX_FAILED seq=11…29` |
| 634 050 | `WIFI_CONNECTED` (hotspot encendido) |
| 637 979 / 639 104 | `MQTT_CONNECTED` (+3.9 s) / `GET_RX` (+5.1 s) |
| 639 111 | `REPORT_TX seq=30`: el estado completo vuelve a publicarse |

## Parte 2 — órdenes por voz con la casa desconectada (hotspot apagado 17:55:2x → ≈ 17:58:40 UTC)

| # | Frase (skill abierta) | Respuesta | Veredicto |
|---|---|---|---|
| 1 | `hay gas en la cocina` (3 min sin reportes) | "No, el aire está normal: el índice de gas es 4,4 por ciento… Ojo: tu casa no se reporta desde hace 3 minutos, así que este dato puede no estar actualizado." | PASS |
| 2 | `cambia el umbral alto a dieciocho por ciento` | "Envié la orden, pero tu casa está desconectada. Se aplicará apenas vuelva a conectarse." | PASS |
| 3 | `enciende la luz de la cocina` | Igual: orden encolada | PASS |

Al volver el hotspot:

| Placa | Reconexión | Orden pendiente aplicada | Tiempo |
|---|---|---|---|
| 1 | `MQTT_CONNECTED` 17:58:44.159 → `GET_RX` +1184 ms | `THRESHOLDS_APPLIED gas_high_pct=18 gas_low_pct=8 origin=voice`; reporte `thresholds_changed` | 1191 ms desde `MQTT_CONNECTED` (*) |
| 2 | `WIFI_CONNECTED` 17:58:40.310 → `MQTT_CONNECTED` +2299 ms → `GET_RX` +3058 ms | `LIGHT_APPLIED zone=kitchen state=on origin=voice`; reporte `light_changed` | **3059 ms** desde `WIFI_CONNECTED` |

(*) En el log de la placa 1, la línea `WIFI_CONNECTED` de esta segunda reconexión llegó con bytes corruptos (ruido en el puerto serie) y no se puede leer; por eso el tiempo se mide desde `MQTT_CONNECTED`. En la primera reconexión, la misma placa tardó 3.9 s de `WIFI_CONNECTED` a `MQTT_CONNECTED`, así que el total estimado es ≈ 5.1 s.

## Resultados

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| E1 sin Internet | 3 ciclos completos: 6 movimientos para 6 cambios de alarma, 410–411 ms cada uno | La ventana se mueve igual | PASS |
| Reportes perdidos sin conexión | Placa 1: 19 (`seq` 11–29) en 154 s; placa 2: 2 (`seq` 11–12) en 149 s; todos registrados como `REPORT_TX_FAILED` | Se declaran (no hay buffer) | INFO |
| Estado al reconectar | Reporte completo inmediato (`seq` 30 en la placa 1) | Se publica el estado completo | PASS |
| Aviso de desconexión en la skill | "tu casa no se reporta desde hace 3 minutos" | Aviso tras > 150 s | PASS |
| Órdenes por voz sin conexión | 2 / 2 encoladas y aplicadas al reconectar, con `origin=voice` | Se aplican solas | PASS |
| Reconexión → orden aplicada | 3.06 s (placa 2); 1.19 s desde MQTT, ≈ 5.1 s estimado desde WiFi (placa 1) | ≤ 10 s | PASS |

**Análisis.** La regla que protege funciona sin Internet: con el hotspot apagado, la placa 1 abrió y cerró la ventana tres veces en 410 ms, como con conexión (A05). Lo que se pierde sin conexión es el **registro**: las alarmas de ese intervalo no llegaron a DynamoDB, así que tampoco las cuenta C1. Esa es la limitación que motiva la recomendación de un buffer de eventos (§7 del informe). Las órdenes por voz no se pierden: quedan en `desired` del Shadow y la placa las recibe con el `/get` al reconectarse.

**Veredicto: PASS** (RNF11, RNF5).
