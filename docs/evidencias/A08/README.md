# Evidencia A08: Corte de energía con orden pendiente

Prueba A08 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 10/11/2026, 00:10–00:14 (hora de Bolivia; 04:10–04:14 UTC). Corte real: se desconectó el cable USB, que alimenta la ESP32 y el servo.

| Archivo | Qué muestra |
|---|---|
| A08_01_intento1_sin_confirmacion.png | Intento 1: con la placa desenchufada, "cierra la puerta" → "Envié la orden para cerrar la puerta, pero todavía no recibo la confirmación…" |
| A08_02_intento1_shadow_delta_closed.png | Intento 1: Shadow con `delta.door = "closed"` |
| A08_03_intento2_sin_confirmacion.png | Intento 2: "abre la puerta" → "Envié la orden para abrir la puerta, pero todavía no recibo la confirmación…" |
| A08_04_intento2_shadow_delta_open.png | Intento 2: Shadow con `desired.door = "open"`, `reported.door = "closed"`, `delta.door = "open"` |
| A08_video_arranque_aplica_orden.mp4 | Intento 2: se enchufa la placa, la puerta arranca cerrada y se abre sola |
| A08_ESP32.log | Log de los dos arranques. Las líneas `# … port lost` y `# … port open` son del registrador al desenchufar y enchufar |

## Resultados

| Intento | Orden pendiente | Primera línea registrada → `MQTT_CONNECTED` | `GET_RX` trae | Puerta | Veredicto |
|---|---|---|---|---|---|
| 1 | `closed` | 2590 ms desde el arranque | versión 587, `desired.door = closed` | ya cerrada por el arranque | no concluyente |
| 2 | `open` | `WIFI_CONNECTED` a 587 ms, `MQTT_CONNECTED` a 2703 ms | versión 592, `desired.door = open` | se abre: `ACTUATOR_START` a 3504 ms, `ACTUATOR_DONE` a 3903 ms | PASS |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Comando con la placa sin energía (último reporte < 150 s) | La Lambda espera 3 s y responde que no recibió confirmación | aviso de no confirmación | PASS (RF10) |
| Orden pendiente aplicada al arrancar | `open`, 3316 ms después de `WIFI_CONNECTED` y 3.9 s desde el arranque | ≤ 10 000 ms | PASS (RNF5) |
| Movimientos duplicados | 0: el `delta` v593 que llega después pide la misma posición y no genera otro movimiento | 0 | PASS |

**Por qué el intento 1 no es concluyente.** Al arrancar, [DoorActuator::begin()](../../../src/DoorActuator.cpp) lleva el servo a `closed`, que es el estado seguro ante un corte de luz. Como la orden pendiente también era `closed`, la puerta quedó cerrada por el arranque y `GET_RX` solo confirmó lo mismo. Por eso se repitió con la orden contraria (`open`), y la apertura demuestra que la orden se aplicó desde el Shadow.

**Líneas de arranque.** Al enchufar, el puerto USB de la PC aparece unos 0.5 s después de que la placa empieza a ejecutar, así que `BOOT`, `RESET_REASON` y `LINK_CODE` no quedaron en el log. Los tiempos de la tabla son `t_ms`, el tiempo desde el arranque de la placa, que no depende del registrador.
