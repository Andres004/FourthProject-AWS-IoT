# A04 — Modo y umbrales por voz

- Fecha y hora: 24/11/2026, 08:45–08:47 (Bolivia) / 12:45–12:47 UTC
- Responsable: Dabner (A04_01 a A04_03 son capturas previas de Ricardo: timeout de 3 s y arranque en frío de la Lambda de datos)
- Firmware: `vent`, placa 1 conectada a AWS; se hizo mientras corría A08
- Requisito: RF14 (modo y umbrales en `reported`, consultables y modificables por voz)
- Archivos: capturas [A03_03](../A03/A03_03_gas_ventana_rechazo_auto.png) (modo), [A03_04](../A03/A03_04_modo_manual_abrir.png) (modo manual), [A03_05](../A03/A03_05_abrir_cerrar_umbrales.png) (consulta de umbrales), [A04_04](A04_04_umbral_alto_20_y_bajo_invalido.png), [A04_05](A04_05_umbral_fuera_de_rango_y_15.png); [A04_extracto_log.txt](A04_extracto_log.txt)

| # | Frase | Respuesta | En la placa 1 (log) | Veredicto |
|---|---|---|---|---|
| 1 | `en qué modo está la ventilación` | "La ventilación está en modo automático." | — | PASS |
| 2 | `activa el modo manual` | "Listo, la ventilación está en modo manual. Ahora puedes abrir o cerrar la ventana con la voz." | `MODE_APPLIED mode=manual origin=voice`; reporte `mode_changed` | PASS |
| 3 | `cuáles son los umbrales de gas` | "La alarma de gas se activa en 15 por ciento y se apaga cuando baja a 8 por ciento." | — | PASS |
| 4 | `cambia el umbral alto a veinte por ciento` | "Listo, el umbral alto quedó en 20 por ciento." | `THRESHOLDS_APPLIED gas_high_pct=20 gas_low_pct=8 origin=voice` (guardado en la NVS); reporte `thresholds_changed` | PASS |
| 5 | `cambia el umbral bajo a veinticinco por ciento` | "El umbral bajo tiene que ser menor que el alto. Ahora el alto es 20 y el bajo quedaría en 25." | Sin `DELTA_RX` | PASS |
| 6 | `cambia el umbral alto a cien por ciento` | "El umbral tiene que ser un número entero entre 1 y 99 por ciento." | Sin `DELTA_RX` | PASS |
| 7 | `cambia el umbral alto a quince por ciento` | "Listo, el umbral alto quedó en 15 por ciento." | `THRESHOLDS_APPLIED gas_high_pct=15 gas_low_pct=8 origin=voice` | PASS |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas correctas | 7 / 7 | todas | PASS |
| Órdenes inválidas que llegaron a la placa | 0 de 2 (la skill las rechaza antes de escribir `desired`) | 0 | PASS |
| `DELTA_RX` → `THRESHOLDS_APPLIED` | 17–18 ms | — | INFO |
| Estado final | `manual`, 15 / 8 (se deja en manual para A06) | — | — |

**Defensa en profundidad.** La placa también rechaza los umbrales inválidos y los modos desconocidos aunque lleguen por `desired` (casos V16–V21 de [B02](../B02/README.md)).

**Veredicto: PASS** (RF14).
