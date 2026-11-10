# Evidencia A04: Comandos y estado de la puerta por voz

Prueba A04 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 23:10–23:15 (hora de Bolivia; 03:10–03:15 UTC del 10/11).

| Archivo | Qué muestra |
|---|---|
| A04_01_cerrar.png | "cierra la puerta" → "Listo, la puerta está cerrada." |
| A04_02_estado_cerrada.png | "cuál es el estado de la puerta" → "La puerta está cerrada." |
| A04_03_abrir.png | "abre la puerta" → "Listo, la puerta está abierta." |
| A04_04_ya_abierta.png | "abre la puerta" dos veces con la puerta abierta → "La puerta ya está abierta." (sin movimiento) |
| A04_05_cerrar_variante.png | Variante "cerrar la puerta" → "Listo, la puerta está cerrada." |
| A04_06_shadow_sin_delta.png, A04_07_shadow_metadata.png | Shadow después del último comando: `desired.door` = `reported.door` = `closed`, sin `delta`; `reported` 11 s después de `desired` (por el heartbeat/evento siguiente) |
| A04_video_1.mp4, A04_video_2.mp4, A04_video_3.mp4 | Videos del servo moviéndose con los comandos de voz |
| A04_ESP32.log | Log de la ESP32 de 03:09:30 a 03:15:27 UTC |
| A04_analisis.txt | Salida de `analyze_log.py` |

| Paso | Frase | Respuesta | En la ESP32 | Estado |
|---|---|---|---|---|
| 1 | cierra la puerta | "Listo, la puerta está cerrada." | `DELTA_RX` v356 → servo 410 ms → reportado a 415 ms | OK (RF3, RF5, RF10) |
| 2 | cuál es el estado de la puerta | "La puerta está cerrada." | — | OK (RF6) |
| 3 | abre la puerta | "Listo, la puerta está abierta." | `DELTA_RX` v360 → 410 ms → 415 ms | OK (RF3, RF5, RF10) |
| 4 | abre la puerta (×2) | "La puerta ya está abierta." | ningún `DELTA_RX` entre 03:11:22 y 03:14:40 | OK (no reescribe `desired`) |
| 5 | cerrar la puerta (variante) | "Listo, la puerta está cerrada." | `DELTA_RX` v376 → 411 ms → 416 ms | OK |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas correctas | 6/6 | todas | PASS |
| `DELTA_RX` → `reported` con la nueva posición | 415, 415 y 416 ms | ≤ 1500 ms | PASS (RF3) |
| Cambio de estado → `REPORT_TX` | máx. 654 ms | ≤ 1100 ms | PASS (RNF4) |
| Shadow final | sin `delta` | sin `delta` | PASS |

`ACTUATOR_START` llega 11 ms después de `DELTA_RX` y el servo tarda 400 ms (`SETTLE_TIME_MS`), igual que en B02 después de la corrección. Los saltos de versión del Shadow (356 → 360 → 376) corresponden a los reportes del PIR y a los heartbeats entre comandos.
