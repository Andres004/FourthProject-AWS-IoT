# A03 — Gas y ventana por voz

- Fecha y hora: 24/11/2026, 08:45–08:46 (Bolivia) / 12:45–12:46 UTC
- Responsable: Dabner (A03_01 y A03_02 son capturas previas de Ricardo)
- Firmware: `vent` (commit `435c9fb` + `MQTT_SOCKET_TIMEOUT_S = 10`), placa 1 conectada a AWS por el hotspot; se hizo mientras corría A08
- Requisitos: RF3, RF4–RF6, RF12, RNF3; convivencia voz / automático (§2.6 del informe)
- Archivos: capturas [A03_03](A03_03_gas_ventana_rechazo_auto.png), [A03_04](A03_04_modo_manual_abrir.png), [A03_05](A03_05_abrir_cerrar_umbrales.png); [A03_extracto_log.txt](A03_extracto_log.txt) (líneas de la placa 1; [log completo](../A08/A08_vent_ESP32.log))

| # | Frase | Respuesta | En la placa 1 (log) | Veredicto |
|---|---|---|---|---|
| 1 | `hay gas en la cocina` | "No, el aire está normal: el índice de gas es 4,4 por ciento, y la alarma se activa en 15." | — (lee `reported.gas_pct`) | PASS |
| 2 | `cómo está la ventana` | "La ventana está cerrada." | — | PASS |
| 3 | `abre la ventana` (modo `auto`) | "La ventilación está en modo automático. Si quieres manejar la ventana, di: activa el modo manual." | Sin `DELTA_RX`: la skill no escribe `desired` | PASS |
| 4 | `activa el modo manual` | "Listo, la ventilación está en modo manual…" | `MODE_APPLIED mode=manual origin=voice` (17 ms después de `DELTA_RX`); reporte `mode_changed` | PASS |
| 5 | `abre la ventana` | "Listo, la ventana está abierta." | `ACTUATOR_START window=open origin=voice` 11 ms después de `DELTA_RX`; `ACTUATOR_DONE` +400 ms; reporte `window_changed` | PASS |
| 6 | `cierra la ventana` | "Listo, la ventana está cerrada." | `ACTUATOR_START window=closed`; `ACTUATOR_DONE` +400 ms | PASS |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas correctas | 6 / 6 | todas | PASS |
| `DELTA_RX` → `ACTUATOR_DONE` (abrir / cerrar) | 410 / 411 ms | — | INFO |
| `DELTA_RX` → reporte publicado (abrir / cerrar) | 416 / 417 ms | ≤ 1500 ms | PASS |
| Lambda → ventana confirmada | La skill dijo "Listo" en los dos comandos (espera hasta 3 s) | ≤ 3 s | PASS |
| Orden de ventana en `auto` | Rechazada por la skill, sin escribir `desired` | Rechazo explicado | PASS |

**Veredicto: PASS.**
