# A02 — Las 5 luces por voz y consulta de presencia

- Fecha y hora: 24/11/2026, 08:40–08:45 (Bolivia) / 12:40–12:45 UTC
- Responsable: Dabner (A02_01 es una captura previa de Ricardo: orden encolada con la placa desconectada)
- Firmware: `lights` (commit `435c9fb` + `MQTT_SOCKET_TIMEOUT_S = 10`), placa 2 conectada a AWS por el hotspot; se hizo mientras corría A08
- Requisitos: RF3 (aplicar el `delta`), RF4–RF6 (consultas y comandos por voz), RF12 (origen `voice`), RNF3 (respuesta por voz)
- Archivos:
  - Capturas del simulador: [A02_02](A02_02_apagar_cocina.png), [A02_03](A02_03_cocina_sala_comedor.png), [A02_04](A02_04_bano_habitacion_consulta.png), [A02_05](A02_05_cocina_ya_encendida.png), [A02_06](A02_06_todas_apagadas_consulta_presencia.png)
  - Foto de la placa con las 5 luces encendidas: [A02_07](A02_07_foto_cinco_luces.webp) (el LED azul es el de conexión)
  - [A02_extracto_log.txt](A02_extracto_log.txt): líneas `DELTA_RX`, `LIGHT_APPLIED` y `REPORT_TX` del log de la placa 2 ([log completo de A08](../A08/A08_lights_ESP32.log))
  - [A02_analisis.txt](A02_analisis.txt): salida de [analyze_log.py](../../../tools/analyze_log.py), sección "RNF3"

| # | Frase | Respuesta de Alexa | En la placa | Veredicto |
|---|---|---|---|---|
| 1 | `apaga la luz de la cocina` | "Listo, la luz de la cocina quedó apagada." | `LIGHT_APPLIED zone=kitchen state=off origin=voice` | PASS |
| 2 | `enciende la luz de la cocina` | "Listo, la luz de la cocina quedó encendida." | `zone=kitchen state=on` | PASS |
| 3 | `enciende la luz de la sala` | "Listo, la luz de la sala quedó encendida." | `zone=living state=on` | PASS |
| 4 | `enciende la luz del comedor` | "Listo, la luz del comedor quedó encendida." | `zone=dining state=on` | PASS |
| 5 | `enciende la luz del baño` | "Listo, la luz del baño quedó encendida." | `zone=bathroom state=on` | PASS |
| 6 | `enciende la luz de la habitación` | "Listo, la luz de la habitación quedó encendida." | `zone=bedroom state=on` | PASS |
| 7 | `está encendida la luz del baño` | "La luz del baño está encendida." | — (consulta de `reported`) | PASS |
| 8 | `enciende la luz de la cocina` (ya encendida) | "La luz de la cocina ya está encendida." | Sin cambio | PASS |
| 9 | `apaga todas las luces` | "Listo, todas las luces quedaron apagadas." | 5 `LIGHT_APPLIED state=off` y **un** reporte `light_changed` | PASS |
| 10 | `cómo está la luz de la sala` | "La luz de la sala está apagada." | — (consulta) | PASS |
| 11 | `hay alguien en la puerta` | "No, no se detecta a nadie en la entrada." | — (`reported.presence = false`) | PASS |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas correctas | 11 / 11 | todas | PASS |
| Comandos confirmados por la skill ("Listo…") | 8 / 8 | todos | PASS |
| `DELTA_RX` → `LIGHT_APPLIED` (reloj de la placa) | mín. 10 / mediana 11 / máx. 41 ms (7 comandos medidos) | — | INFO |
| `DELTA_RX` → reporte publicado | mediana 29 ms; máx. 741 ms (cuando el reporte anterior había salido hace < 1 s) | ≤ 1500 ms | PASS |
| Lambda → objeto confirmado | La skill solo dice "Listo" si lee la confirmación en `reported` en ≤ 3 s: las 8 órdenes la recibieron | ≤ 3 s | PASS |

**Análisis.** La placa aplica la orden en ≈ 11 ms y publica la confirmación en ≈ 29 ms; cuando el reporte anterior había salido hace menos de 1 s, el firmware espera el mínimo de 1 s entre reportes (741 ms). "Apaga todas las luces" llega en un solo `delta` y produce un único reporte con las 5 zonas apagadas (eventos agrupados). Las consultas responden desde `reported`, nunca desde `desired`.

**Veredicto: PASS** (RF3–RF6, RF12, RNF3).
