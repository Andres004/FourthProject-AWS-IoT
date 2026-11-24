# A05 — Regla E1 con gas real y tiempo de respuesta Edge

- Fecha y hora: 24/11/2026, 06:55–07:03 (Bolivia) / 10:55–11:03 UTC
- Responsable: Dabner
- Commit del firmware: `435c9fb` (entorno `vent_local_test`: la lógica E1–E3 es la misma que en `vent`; solo cambia el transporte del Shadow, que aquí es el puerto serie, así que la prueba no depende de Internet)
- Requisitos: RF13 (E1, E2), RNF9 (respuesta de la lógica automática en el Edge)
- Umbrales: `gas_high_pct = 15`, `gas_low_pct = 8` (calibración A10), modo `auto`
- Estímulo: gas de un encendedor **sin llama**, a 2–3 cm del MQ-2, hasta que se encendía el LED de gas (3–5 s); 20 s de espera entre ciclos
- Archivos:
  - [A05_vent_ESP32.log](A05_vent_ESP32.log): log de la placa 1 (un `GAS_SAMPLE` por segundo)
  - [A05_analisis.txt](A05_analisis.txt): salida de [analyze_log.py](../../../tools/analyze_log.py)
  - [A05_video_1.mp4](A05_video_1.mp4), [A05_video_2.mp4](A05_video_2.mp4): ventana y LED de gas durante los ciclos
  - [A05_intento1_ESP32.log](A05_intento1_ESP32.log): primer intento, con el estímulo sin estandarizar (ver "Resultado negativo")
- Reloj: `millis()` de la placa 1 para todas las medidas (un solo reloj)

## Resultados

| Ciclo | `GAS_ALARM_ON` (t, ms) | Índice al disparar | Abrir: `GAS_ALARM_ON` → `ACTUATOR_DONE` | `GAS_ALARM_OFF` (t, ms) | Índice al apagar | Cerrar |
|---|---|---|---|---|---|---|
| 1 | 394 042 | 68.6 % | 411 ms | 400 042 | 6.1 % | 411 ms |
| 2 | 424 042 | 16.8 % | 411 ms | 428 042 | 7.9 % | 411 ms |
| 3 | 465 042 | 28.1 % | 411 ms | 472 042 | 7.1 % | 411 ms |
| 4 | 494 042 | 57.5 % | 411 ms | 500 042 | 6.4 % | 411 ms |
| 5 | 514 042 | 47.2 % | 411 ms | 521 042 | 6.8 % | 411 ms |
| 6 | 543 042 | 25.1 % | 411 ms | 547 042 | 6.8 % | 411 ms |
| 7 | 568 042 | 48.7 % | 411 ms | 572 042 | 8.0 % | 411 ms |
| 8 | 593 042 | 60.1 % | 411 ms | 598 042 | 6.7 % | 411 ms |
| 9 | 618 042 | 67.0 % | 411 ms | 622 042 | 7.7 % | 411 ms |
| 10 | 643 043 | 35.1 % | 410 ms | 648 042 | 6.0 % | 411 ms |
| 11 | 671 042 | 60.3 % | 411 ms | 677 042 | 6.5 % | 411 ms |
| 12 | 701 043 | 71.2 % | 410 ms | 706 042 | 6.3 % | 411 ms |
| 13 | 733 042 | 40.8 % | 411 ms | 738 042 | 5.8 % | 411 ms |
| 14 | 763 042 | 78.2 % | 411 ms | 767 042 | 7.3 % | 411 ms |
| 15 | 808 042 | 51.4 % | 411 ms | 812 042 | 7.0 % | 411 ms |

| Medida | Mín. / mediana / promedio / máx. | Criterio | Veredicto |
|---|---|---|---|
| Ciclos completos (abre y cierra) | 15 de 15 | ≥ 10 | PASS |
| Respuesta Edge al abrir (`GAS_ALARM_ON` → `ACTUATOR_DONE`) | 410 / 411 / 411 / 411 ms | ≤ 1000 ms | PASS |
| Respuesta Edge al cerrar (`GAS_ALARM_OFF` → `ACTUATOR_DONE`) | 411 / 411 / 411 / 411 ms | ≤ 1000 ms | PASS |
| Cambios de alarma fuera de los umbrales | 0 de 30 | 0 | PASS |
| Alarmas durante el calentamiento (E2) | 0 (la placa ya estaba caliente al empezar) | 0 | PASS |
| Soplos débiles sin alarma | 2 (picos de 6.1 % y 8.1 %, < 15 %) | Sin alarma | PASS |

**Tiempos del sensor** (con la granularidad de 1 s del promedio; desde los `GAS_SAMPLE`):

| Medida | Mín. | Promedio | Máx. |
|---|---|---|---|
| Respuesta del sensor (última lectura en la línea base → alarma) | 1.0 s | 1.5 s | 3.0 s |
| Duración de la alarma | 4.0 s | 5.1 s | 7.0 s |
| Recuperación (fin de la alarma → línea base de 4.4 %) | 1.0 s | 1.3 s | 2.0 s |

## Análisis

- **La respuesta Edge (≈ 411 ms) es el tiempo del servo**: `SETTLE_TIME_MS = 400` más ≈ 11 ms entre la decisión y la orden al servo (el bucle y la escritura del log). La decisión no pasa por Internet: la placa estaba sin WiFi.
- **El tiempo total desde que llega el gas hasta que la ventana está abierta** es la respuesta del sensor (1–3 s) más el promedio de 1 s más 0.41 s. Lo domina la química del sensor, no el firmware.
- **Histéresis:** las 15 alarmas se apagaron con índices entre 5.8 % y 8.0 %, siempre ≤ 8 %; ninguna oscilación (cada alarma produjo exactamente un `ON` y un `OFF`).
- **El umbral filtra los soplos débiles:** dos soplos breves llegaron a 6.1 % y 8.1 % y no produjeron alarma, que es lo esperado.

## Resultado negativo: primer intento

En el primer intento ([A05_intento1_ESP32.log](A05_intento1_ESP32.log)) el gas se soltó a distinta distancia y durante tiempos distintos. Hubo 4 episodios con picos de 9.0 %, 26.3 %, 17.8 % y 81.9 %: los 3 que superaron el 15 % abrieron y cerraron la ventana (411 ms) y el de 9.0 % no produjo alarma. El firmware se comportó bien; la variación estaba en la cantidad de gas que llegaba al sensor. Por eso el estímulo se estandarizó (2–3 cm, gas hasta que se enciende el LED) y la prueba se repitió.

**Veredicto: PASS** (RF13 E1, RNF9).
