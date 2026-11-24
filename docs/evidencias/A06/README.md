# Evidencia A06: Exactitud del PIR y del servo

Prueba A06 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 10/11/2026, 00:18–00:36 (hora de Bolivia; 04:18–04:36 UTC). Versión corta del plan: 3 distancias × 5 cruces, 12 s entre cruces y 5 min sin personas. La parte del servo se hizo el 10/11/2026 a las 17:06–17:12 (21:06–21:12 UTC).

| Archivo | Qué muestra |
|---|---|
| A06_PIR_ESP32.log | Log de la ESP32 de 04:18 a 04:36 UTC con todos los `PRESENCE_ON`/`PRESENCE_OFF` |
| A06_servo_cerrada_1.jpeg, A06_servo_cerrada_2.jpeg | Brazo del servo con la puerta `closed`, sobre el transportador |
| A06_servo_abierta_1.jpeg, A06_servo_abierta_2.jpeg | Brazo del servo con la puerta `open`, sobre el transportador |
| A06_video_servo.mp4 | Video de los movimientos del servo con el transportador |
| A06_servo_ESP32.log | Log de la ESP32 durante las fotos: 7 movimientos de 400 ms (`ACTUATOR_START` → `ACTUATOR_DONE`) |

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

## Ángulo del servo

El transportador se apoyó con su línea base (0°–180°) paralela al cuerpo del servo, y se lee la dirección del brazo largo respecto de esa línea.

| Foto | Posición pedida | Ángulo del firmware | Brazo observado | Diferencia estimada |
|---|---|---|---|---|
| A06_servo_cerrada_1 | `closed` | 0° | paralelo a la línea 0°–180° | < 3° |
| A06_servo_cerrada_2 | `closed` | 0° | paralelo a la línea 0°–180° | < 3° |
| A06_servo_abierta_1 | `open` | 90° | perpendicular, sobre la marca de 90° | < 3° |
| A06_servo_abierta_2 | `open` | 90° | perpendicular, sobre la marca de 90° | < 3° |

**Limitación de la medición.** El transportador se sostuvo a mano y su centro no quedó exactamente sobre el eje del servo, así que el ángulo se lee por la orientación del brazo respecto de la línea base, a ojo sobre la foto. La resolución práctica es de unos ±2–3°, suficiente para el criterio de ±5° pero no para afirmar un error menor. Además, el brazo se encastra en el eje en pasos de unos 15° (estrías), así que la orientación del brazo respecto de la puerta se ajusta mecánicamente, y el firmware solo garantiza el ángulo del eje.

En el log, durante las fotos llegó dos veces el mismo `closed` (versiones 716 y 717, 21:09:20–21) mientras el servo se movía, y no generó un segundo movimiento: es el caso `moving_ && target == target_` de [DoorActuator::applyDesired()](../../../src/DoorActuator.cpp).

## Resumen

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Detección entre 0.5 y 2.0 m | 15/15 (100 %) | 15/15 | PASS (RNF2, RF1) |
| Falsos positivos sin personas | 0 en 5.0 min | 0 | PASS (RNF2) |
| Ángulo del servo vs. transportador | 4/4 fotos con diferencia estimada < 3° (0° y 90°) | ±5° en 0° y 90° | PASS (RNF2) |
