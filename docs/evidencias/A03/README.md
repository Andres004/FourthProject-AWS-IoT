# Evidencia A03: Consulta del sensor por voz

Prueba A03 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 22:58–23:05 (hora de Bolivia; 02:58–03:05 UTC del 10/11).

| Archivo | Qué muestra |
|---|---|
| A03_01_presencia_si.png | "hay alguien en la puerta" con una persona frente al sensor → "Sí, se detecta a alguien en la entrada." |
| A03_02_presencia_no.png | "detectas a alguien en la entrada" sin nadie → "No, no se detecta a nadie en la entrada." |
| A03_video_consulta_presencia.mp4 | Video de un ciclo de consulta con el sensor y el simulador |
| A03_cloudwatch.csv | Líneas `SKILL_REQUEST` de las consultas (la primera, `not_linked` de 02:34, es de A01) |
| A03_ESP32.log | Log de la ESP32 de 02:58:07 a 03:05:06 UTC |
| A03_analisis.txt | Salida de `analyze_log.py` para el log de la ESP32 |

Cada respuesta se comparó con el estado del PIR en el log de la ESP32 en el mismo instante. `start_utc_ms` es la hora de la Lambda y el log usa la hora NTP de la ESP32.

| Hora UTC de la consulta | Respuesta (`result`) | Último evento del PIR antes de la consulta | Antigüedad del dato (`age_s`) | Coincide |
|---|---|---|---|---|
| 03:00:13 | `presence=True` | `PRESENCE_ON` 03:00:03 | 10 s | sí |
| 03:00:32 | `presence=True` | `PRESENCE_ON` 03:00:31 | 0 s | sí |
| 03:00:40 | `presence=True` | `PRESENCE_ON` 03:00:31 | 8 s | sí |
| 03:01:09 | `presence=True` | `PRESENCE_ON` 03:00:50 | 19 s | sí |
| 03:01:19 | `presence=True` | `PRESENCE_ON` 03:00:50 | 29 s | sí |
| 03:02:09 | `presence=False` | `PRESENCE_OFF` 03:01:43 | 26 s | sí |
| 03:03:22 | `presence=True` | `PRESENCE_ON` 03:02:47 | 35 s | sí |
| 03:04:10 | `presence=False` | `PRESENCE_OFF` 03:04:02 | 7 s | sí |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas que coinciden con `reported.presence` | 8/8 (6 "sí", 2 "no") | todas | PASS (RF1, RF4) |
| Cambio de presencia → `REPORT_TX` | 28 cambios; mediana 5 ms, máx. 254 ms | ≤ 1100 ms | PASS (RNF4) |
| Duración de cada episodio de presencia | 14 episodios, mín. 11.8 s | ≥ 10 s (retención) | PASS (RNF2) |
| Atributos en cada reporte | `door`, `servo_angle`, `presence` en los 28 | los 3 | PASS (RF2) |

El caso de 254 ms (`PRESENCE_ON` a las 02:58:07.849 y su reporte a las 02:58:08.103) ocurrió porque el reporte anterior había salido 745 ms antes y se respetó el mínimo de 1 s entre mensajes. La línea `RNF1 … 6.9 min → FAIL` de `A03_analisis.txt` es esperable: A03 es un tramo de 7 min, y la estabilidad se mide en A10.
