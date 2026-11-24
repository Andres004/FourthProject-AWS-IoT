# A06 — Regla C1 en la Nube y tiempo de respuesta

- Fecha y hora: 24/11/2026, 08:48–08:50 (Bolivia) / 12:48–12:50 UTC
- Responsable: Dabner (A06_01 es una captura previa de Ricardo, con reportes publicados a mano desde el MQTT test client)
- Firmware: `vent`, placa 1 conectada a AWS; se hizo mientras corría A08
- Requisitos: RF13 (lógica en la Nube, actúa solo por `desired`), RNF10 (respuesta de la lógica automática en la Nube)
- Regla: C1, `GAS_EVENTS_LIMIT = 3` alarmas en `GAS_EVENTS_WINDOW_H = 24` h, solo en modo `manual`
- Estímulo: gas de encendedor sin llama a 2–3 cm del MQ-2, con la ventilación en `manual` (puesta por voz en A04)
- Archivos: [A06_extracto_log.txt](A06_extracto_log.txt), [A06_analisis.txt](A06_analisis.txt) (sección "C1 / RNF8" de [analyze_log.py](../../../tools/analyze_log.py)), [A06_02](A06_02_modo_automatico_tras_c1.png) (modo consultado por voz después de C1), [log completo](../A08/A08_vent_ESP32.log)
- Reloj: `millis()` de la placa 1 para todas las medidas

| Alarma | `GAS_ALARM_ON` (hora UTC) | Índice | Modo | Respuesta de la Nube | Ventana |
|---|---|---|---|---|---|
| 1 | 12:48:52.090 | 68.1 % | `manual` | Ninguna (menos de 3 alarmas en 24 h) | No se movió (correcto en manual) |
| 2 | 12:49:04.090 | 31.7 % | `manual` | Ninguna | No se movió |
| 3 | 12:49:27.090 | 53.3 % | `manual` | `desired.mode = auto`, `cmd_origin = cloud` | Se abrió por E1 en cuanto entró `auto` |

**Secuencia de la alarma 3** (líneas 1928–1938 del log):

| t (ms, placa) | Evento | Desde el reporte |
|---|---|---|
| 1 812 702 | `REPORT_TX seq=52 event=gas_alarm_on` | 0 ms |
| 1 813 275 | `DELTA_RX version=78 {"mode":"auto","cmd_origin":"cloud"}` | 573 ms |
| 1 813 293 | `MODE_APPLIED mode=auto origin=cloud` | 591 ms |
| 1 813 308 | `EDGE_ACTION window=open gas_pct=53.3` | 606 ms |
| 1 813 702 | `REPORT_TX seq=53 event=mode_changed origin=cloud` | 1000 ms |
| 1 813 735 | `ACTUATOR_DONE window=open angle=90` | 1033 ms |
| 1 814 702 | `REPORT_TX seq=54 event=window_changed origin=edge` | 2000 ms |
| 1 819 697 | `GAS_ALARM_OFF` → la ventana se cierra sola (`origin=edge`), ya en `auto` | — |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Alarmas en `manual` que no movieron la ventana | 2 / 2 (alarmas 1 y 2) | La Nube no actúa con menos de 3 | PASS |
| C1 al llegar a 3 alarmas | Sí: `mode = auto`, `cmd_origin = cloud` | Actúa solo por `desired` | PASS |
| Respuesta de la Nube (`REPORT_TX gas_alarm_on` → `MODE_APPLIED`) | **591 ms (n = 1)** | ≤ 5000 ms | PASS, con una sola medición |
| Hasta la ventana abierta (`ACTUATOR_DONE`) | 1033 ms | — | INFO |
| Eventos de la Nube y del Edge en reportes separados | `mode_changed` (cloud) y luego `window_changed` (edge) | Sin pérdida de eventos (D-01) | PASS |
| Bucle regla ↔ Lambda | El reporte `mode_changed` no volvió a disparar la regla (no hubo un segundo `DELTA_RX`) | Sin bucle | PASS |
| Consulta por voz después | "La ventilación está en modo automático." | `auto` | PASS |

**Limitación: n = 1.** C1 solo actúa en la alarma que completa el límite estando en `manual`, así que esta corrida dio **una** medición del tiempo de respuesta de la Nube. El criterio general de las pruebas pide al menos 10 repeticiones por punto; el valor de 591 ms se informa como una medición única, no como un resultado estadístico. Las 13 pruebas unitarias de la Lambda de control (B01) cubren la lógica de la decisión (conteo, exclusión de la alarma actual, modo `auto`), pero no el tiempo.

**Análisis.** El camino de la Nube suma la regla de IoT, la invocación de `smartloft_control_lambda`, la consulta a `event-index`, el `UpdateThingShadow` y la entrega del `delta`: 573 ms hasta la placa. Es ≈ 1.4 veces el tiempo de la regla E1 en el Edge (411 ms, A05), aceptable para una decisión que no es urgente: la seguridad inmediata la da E1, que abrió la ventana en cuanto la Nube cambió el modo.

**Veredicto: PASS** (RF13 C1, RNF10).
