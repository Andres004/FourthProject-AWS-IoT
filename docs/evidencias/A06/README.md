# Evidencia A06: Exactitud del PIR y del servo

Prueba A06 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 10/11/2026, 00:18–00:36 (hora de Bolivia; 04:18–04:36 UTC). Versión corta del plan: 3 distancias × 5 cruces, 12 s entre cruces y 5 min sin personas.

> **Pendiente:** fotos del servo con transportador (2 en `closed`, 2 en `open`) y foto de las marcas del piso.

| Archivo | Qué muestra |
|---|---|
| A06_PIR_ESP32.log | Log de la ESP32 de 04:18 a 04:36 UTC con todos los `PRESENCE_ON`/`PRESENCE_OFF` |

## Detección por distancia

Cada cruce cuenta solo si su `PRESENCE_ON` llega después de un `PRESENCE_OFF`, es decir, con el sensor en reposo.

| Distancia | Inicio del bloque (UTC) | `PRESENCE_ON` contados | Detectados |
|---|---|---|---|
| 0.5 m | 04:18:15 | 04:18:43, 04:19:04, 04:19:35, 04:20:04, 04:21:43 | 5/5 |
| 1.0 m | 04:22:36 | 04:22:57, 04:23:30, 04:23:56, 04:24:25, 04:24:55 | 5/5 |
| 2.0 m | 04:27:03 | 04:27:25, 04:28:03, 04:28:32, 04:29:04, 04:29:27 | 5/5 |

En 0.5 m, el primer cruce se hizo con el sensor todavía activo por un movimiento anterior (`PRESENCE_OFF` a las 04:18:38), así que no se distinguía como un evento nuevo. Se repitió ese cruce a las 04:21:43, con el sensor en reposo.

## Falsos positivos

| Intervalo sin personas (UTC) | Duración | `PRESENCE_ON` | Veredicto |
|---|---|---|---|
| 04:30:41 (`PRESENCE_OFF` al salir) → 04:35:41 (`PRESENCE_ON` al volver) | 5.0 min | 0 | PASS |

## Resumen

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Detección entre 0.5 y 2.0 m | 15/15 (100 %) | 15/15 | PASS (RNF2, RF1) |
| Falsos positivos sin personas | 0 en 5.0 min | 0 | PASS (RNF2) |
| Ángulo del servo vs. transportador | pendiente | ±5° en 0° y 90° | pendiente |
