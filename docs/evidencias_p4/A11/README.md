# A11 — Estabilidad de las dos placas

- Fecha y hora: 24/11/2026, 08:19:13–09:25:13 (Bolivia) / 12:19–13:25 UTC — la misma corrida que [A08](../A08/README.md)
- Responsable: Dabner
- Firmware: `vent` y `lights` (commit `435c9fb` + `MQTT_SOCKET_TIMEOUT_S = 10`), conectadas a AWS IoT por un hotspot a 30–50 cm
- Requisito: RNF1 (estabilidad)
- Archivos: [A08_vent_ESP32.log](../A08/A08_vent_ESP32.log), [A08_lights_ESP32.log](../A08/A08_lights_ESP32.log) (grabados con [serial_logger.py](../../../tools/serial_logger.py) sin reiniciar las placas), [A08_analisis_logs.txt](../A08/A08_analisis_logs.txt) (salida de [analyze_log.py](../../../tools/analyze_log.py), sección "RNF1")
- Durante la corrida se hicieron A01–A04, A06 y A07 (órdenes por voz y 3 alarmas de gas): las placas trabajaron con carga real, no solo en reposo

| Medida | Placa 1 (`vent`) | Placa 2 (`lights`) | Criterio | Veredicto |
|---|---|---|---|---|
| Tiempo sin reinicio | 66.0 min | 65.6 min | ≥ 60 min | PASS |
| Reinicios (`BOOT` después del primero) | 0 | 0 | 0 | PASS |
| Caídas de WiFi / MQTT | 0 / 0 | 0 / 0 | 0 | PASS |
| `loop()` más largo en operación normal | 71 ms | 82 ms | ≤ 500 ms | PASS |
| `loop()` más largo al conectarse (primer minuto) | 2913 ms | 2213 ms | — | INFO (ver nota) |
| Heap libre, primera → última línea `HEALTH` | 197 472 → 197 304 (−168 bytes) | 199 336 → 199 168 (−168 bytes) | pérdida ≤ 4096 bytes | PASS |
| Señal WiFi (RSSI) | −67 a −17 dBm | −57 a −25 dBm | — | INFO |
| Líneas `HEALTH` (una por minuto) | 65 | 65 | — | INFO |

**Nota sobre el primer minuto.** El bucle más largo de cada placa (2.2–2.9 s) ocurrió una sola vez, al establecer la conexión MQTT sobre TLS: PubSubClient conecta de forma sincrónica y el *handshake* TLS bloquea el bucle. Es el mismo comportamiento documentado en la P3 (2.1–2.4 s al conectar) y está cubierto por el watchdog de 30 s. Después de conectarse, ningún bucle superó los 82 ms. La recomendación de un cliente MQTT no bloqueante está en §7 del informe.

**Veredicto: PASS** (RNF1).
