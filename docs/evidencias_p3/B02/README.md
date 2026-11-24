# Evidencia B02: Firmware con transporte serie

Prueba B02 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026 (22:19 hora de Bolivia, 02:19 UTC del 10/11).

| Archivo | Qué muestra |
|---|---|
| B02_salida.txt | Salida de [serial_check.py](../../../tools/serial_check.py) con el firmware corregido: 16/16 |
| B02_ESP32.log | Log completo de la ESP32 en esa corrida; las líneas `# TX` son lo que envió el script |
| B02_salida_antes_correccion.txt | Primera corrida: 13/16, con el defecto descrito abajo |
| B02_ESP32_antes_correccion.log | Log de esa primera corrida |

El firmware `local_test` reemplaza AWS por el puerto serie: cada línea recibida se procesa como un `/update/delta` y cada reporte se imprime como `LOCAL_REPORT`. Es el mismo código de [DoorActuator](../../../src/DoorActuator.cpp), [ShadowTransport](../../../src/ShadowTransport.cpp) y [ShadowReporter](../../../src/ShadowReporter.cpp) que corre con AWS; solo cambia la clase de transporte.

| Caso | Requisito | Envío | Esperado | Resultado |
|---|---|---|---|---|
| C01 | RF2 | — (arranque) | Primer reporte con `door=closed`, `servo_angle=0` | PASS |
| C02 | RF3 | `door=open`, versión 1 | Movimiento de 400 ± 60 ms y reporte con `open`, 90° | PASS: 400 ms; reporte a 801 ms (espera el mínimo de 1 s desde el reporte anterior) |
| C03 | RF12 | Versión 1 repetida | `STALE_IGNORED`, sin movimiento | PASS |
| C04 | RF12 | Versión 0 (anterior) | `STALE_IGNORED`, sin movimiento | PASS |
| C05 | RF3 | `open` con la puerta ya abierta | Sin movimiento, reporte que borra el `delta` | PASS |
| C06–C08 | RF12 | `"half"`, `1`, `"OPEN"` | `INVALID_VALUE`, sin movimiento | PASS 3/3 |
| C09 | RF12 | JSON cortado | `JSON_ERROR reason=IncompleteInput` | PASS |
| C10 | RF12 | Sin `state` | `JSON_ERROR reason=missing_state` | PASS |
| C11 | RF12 | Línea de 296 caracteres | `JSON_ERROR reason=line_too_long` | PASS |
| C12 | RF12 | `delta` sin `door` | El actuador lo ignora | PASS |
| C13 | RF3 | `door=closed` | 400 ± 60 ms, reporte `closed`, 0° | PASS: 400 ms; reporte a 400 ms |
| C14 | RF3 | `open` y, 150 ms después, `closed` | Termina cerrada y nunca reporta `open` | PASS |
| C15 | RNF4 | 3 órdenes cada 600 ms | Reportes separados ≥ 1000 ms | PASS: 2 reportes a 1000 ms; el intermedio se agrupa y el último refleja el estado final |
| C16 | RF2, RNF4 | — (espera) | Heartbeat a 60 000 ± 1500 ms del último reporte | PASS: 60 000 ms |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Casos | 16/16 | todos | PASS |
| Duración del movimiento (`ACTUATOR_START` → `ACTUATOR_DONE`) | 400 ms en los 6 movimientos completos | 400 ± 60 ms | PASS |
| Separación mínima entre reportes | 1000 ms | ≥ 1000 ms | PASS |
| Intervalo del heartbeat | 60 000 ms | 60 000 ± 1500 ms | PASS |

## Defecto encontrado y corregido

En la primera corrida, C02 y C13 fallaron: `ACTUATOR_DONE` llegaba 0 y 10 ms después de `ACTUATOR_START` (líneas 22–23 y 57–58 de `B02_ESP32_antes_correccion.log`), en lugar de 400 ms. El Shadow confirmaba la nueva posición mientras el servo todavía se movía.

**Causa.** `loop()` toma `nowMs = millis()` al principio de cada iteración. Durante esa misma iteración, el `delta` llega y `startMove()` guarda `moveStartMs_ = millis()`, unos milisegundos *después* de `nowMs`. En la siguiente llamada a `update(nowMs)`, la resta sin signo `nowMs - moveStartMs_` era negativa y daba un número cercano a 2³², mayor que 400, así que el movimiento se daba por terminado de inmediato.

**Corrección.** [DoorActuator::update()](../../../src/DoorActuator.cpp) calcula la diferencia con signo (`int32_t`). Se revisaron los demás usos de `millis()`: los de `PresenceSensor` y `WifiManager` ocurren antes del primer `loop()`, y `ShadowClient` ya comparaba con signo.

C16 también falló en la primera corrida, pero por un error del script: el PIR detectó movimiento dos veces (líneas 88 y 91), y cada reporte por evento reinicia el período de 60 s, que es el comportamiento correcto. El script medía desde un reporte anterior. Ahora mide desde el último reporte antes del heartbeat.
