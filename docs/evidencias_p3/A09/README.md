# Evidencia A09: Comandos inválidos desde AWS

Prueba A09 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 23:17–23:21 (hora de Bolivia; 03:17–03:21 UTC del 10/11).

Los mensajes se publicaron con el **MQTT test client** de AWS IoT en `$aws/things/monoambiente-739264/shadow/update`, es decir, por el mismo camino que usa la Lambda, pero con valores que la Lambda nunca escribe.

| Archivo | Qué muestra |
|---|---|
| A09_01_publicar_medio.png | Publicación de `{"state":{"desired":{"door":"medio"}}}` |
| A09_02_shadow_delta_OPEN.png | Shadow con `desired.door = "OPEN"`, `reported.door = "closed"` y `delta.door = "OPEN"` |
| A09_03_alexa_estado_ignora_invalido.png | "cómo está la puerta" → "La puerta está cerrada.", sin mencionar la orden inválida como pendiente |
| A09_04_shadow_limpio.png | Shadow final: `desired` = `reported` = `closed`, sin `delta` |
| A09_ESP32.log | Log de la ESP32 de 03:17 a 03:21:52 UTC |

| Caso | Mensaje | En la ESP32 | Movimiento | Estado |
|---|---|---|---|---|
| 1 | `"door":"medio"` | `DELTA_RX` v386 → `INVALID_VALUE door=medio` (11 ms) | no | OK |
| 2 | `"door":5` | `DELTA_RX` v387 → `INVALID_VALUE door=<not a string>` | no | OK |
| 3 | `"door":"OPEN"` | `DELTA_RX` v389 → `INVALID_VALUE door=OPEN` | no | OK |
| 4 | `"door":"open"` | `DELTA_RX` v399 → servo 400 ms → reportado a 404 ms | sí, abre | OK |
| 5 | `"door":"closed"` | `DELTA_RX` v401 → servo 400 ms → reportado a 404 ms; el `delta` desaparece | sí, cierra | OK |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Valores inválidos rechazados sin movimiento | 3/3 | todos | PASS (RF12) |
| Órdenes válidas aplicadas después | 2/2 | todas | PASS (RF3) |
| `ACTUATOR_START` por valores inválidos | 0 | 0 | PASS |
| Respuesta de Alexa con `desired` inválido | lee `reported` y no anuncia la orden inválida | — | PASS (RF6) |
| Estabilidad durante la prueba | `HEALTH` 03:21:52: 3600 s encendida, 0 caídas, `loop()` máx. 18 ms | — | INFO |

**Observación.** Mientras el `desired` inválido sigue en el Shadow, AWS publica un `delta` nuevo cada vez que la ESP32 actualiza `reported`, por ejemplo con cada evento del PIR. Por eso, en el log, `INVALID_VALUE` aparece 13 veces para 3 publicaciones, con versiones distintas (no son duplicados, así que `STALE_IGNORED` no aplica). El servo nunca se movió, pero cada repetición es un mensaje más. Una mejora posible (§7 del informe) es que la ESP32, al rechazar un valor, publique `"desired":{"door":null}` para borrar la orden inválida. No se implementó porque la consigna deja la escritura de `desired` a la aplicación, y la Lambda solo escribe `open` o `closed`.
