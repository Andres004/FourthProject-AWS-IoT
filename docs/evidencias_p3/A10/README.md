# Evidencia A10: Estabilidad y frecuencia de reporte

Prueba A10 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 23:22–23:49 (hora de Bolivia; 03:22–03:49 UTC del 10/11). Misma corrida que [A05](../A05/README.md): 28 comandos de voz (uno cada ~40 s) y pasos frente al PIR cada pocos minutos.

| Archivo | Qué muestra |
|---|---|
| A10_ESP32.log | Log de la ESP32: 27.3 min continuos |
| A10_analisis.txt | Salida de `analyze_log.py` |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Duración continua sin reinicio | 27.3 min (27 líneas `HEALTH`) | ≥ 15 min | PASS (RNF1) |
| Reinicios (`BOOT`) | 0 | 0 | PASS (RNF1) |
| Caídas de WiFi y MQTT | 0 y 0 | 0 | PASS (RNF1) |
| Iteración más larga de `loop()` | 21 ms | ≤ 500 ms | PASS (RNF1) |
| Heap libre, primera vs. última `HEALTH` | 196 960 → 196 960 bytes (mínimo histórico 182 532) | pérdida ≤ 4096 bytes | PASS (RNF1) |
| Mayor intervalo entre reportes | 59 999 ms | ≤ 61 500 ms | PASS (RF2, RNF4) |
| Reportes con los 3 atributos | 115/115 (113 por evento, 2 heartbeat) | todos | PASS (RF2) |
| Cambio de estado → `REPORT_TX` | máx. 804 ms | ≤ 1100 ms | PASS (RNF4) |
| `DELTA_RX` → `reported` con la nueva posición | 30/30 en ≤ 1500 ms | todos | PASS (RF3) |
| Episodios de presencia < 10 s | 0 | 0 | PASS (RNF2) |
| RSSI | −83 a −22 dBm | — | INFO |

**Más allá de la corrida.** La ESP32 se encendió a las 22:21 y, en la línea `HEALTH` de las 23:44, llevaba 83 min sin reiniciarse ni perder la conexión (`HEALTH uptime_s=4980 … wifi_drops=0 mqtt_drops=0` en el log general), pasando por A01–A10.

**Consumo de mensajes (RNF4).** Esta corrida es un uso intensivo: 253 reportes por hora, sobre todo eventos del PIR y de la puerta, que proyectan unos 6 000 por día. En reposo, con solo el heartbeat de 60 s, son 1 440 por día (unos 43 000 por mes). Con un heartbeat de 10 s serían 8 640 por día sin ganar información, porque los cambios ya se reportan por evento.
