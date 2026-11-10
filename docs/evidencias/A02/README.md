# Evidencia A02: Dos usuarios con Things distintos

Prueba A02 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 22:51–22:58 (hora de Bolivia; 02:51–02:58 UTC del 10/11).

El simulador de Alexa tiene un solo usuario, así que el segundo usuario (`test-user-2`) se simula con eventos de prueba de la Lambda que llevan otro `userId`. Pasan por el mismo `lambda_handler` que las solicitudes reales de Alexa.

| Archivo | Qué muestra |
|---|---|
| A02_01_evento_vincular2.png | Evento `vincular2` (`test-user-2`, código 518306) |
| A02_02_respuesta_vinculada_518306.png, A02_03_log_vincular2.png | Respuesta "Listo, tu casa con el código 518306 quedó vinculada" y su línea `SKILL_REQUEST` (`result: linked`) |
| A02_04_respuesta_abrir2.png, A02_05_log_abrir2.png | `abrir2` (`OpenDoor` de `test-user-2`): "Envié la orden, pero tu casa está desconectada…", `thing: monoambiente-518306`, `version: 2`, `result: queued_offline` |
| A02_06/07_shadow_518306_*.png | Shadow de `monoambiente-518306`: `desired.door = "open"`, `delta.door = "open"`, timestamp 1794279250 |
| A02_08_dynamodb_dos_usuarios.png | Dos ítems: `test-user-2` → 518306 y el usuario del simulador → 739264 |
| A02_09/09b_shadow_739264_*.png | Shadow de `monoambiente-739264`: `desired` = `reported`, sin `delta`; `desired.door` con timestamp 1794257914 (horas antes) |
| A02_10_simulador_estado_puerta.png | El usuario del simulador pregunta "cómo está la puerta": "La puerta está abierta.", sin orden pendiente |
| A02_ESP32.log | Log de la ESP32 de 02:50 a 02:58 UTC |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Ítems en DynamoDB | 2, uno por usuario y cada uno con su Thing | 2 | PASS (RF7, RF8) |
| Shadow escrito por `test-user-2` | Solo `monoambiente-518306` (versión 2) | solo el suyo | PASS (RF8) |
| Shadow de `monoambiente-739264` | `desired.door` sin cambios (timestamp 1794257914 < 1794279250), sin `delta` | sin cambios | PASS (RF8) |
| `DELTA_RX` en la ESP32 durante la prueba | 0 (solo eventos del PIR, `HEALTH` y heartbeats) | 0 | PASS |
| Movimiento de la puerta real | ninguno (observado) | ninguno | PASS |
| Respuesta a `abrir2` | `queued_offline`: `monoambiente-518306` no tiene ESP32 ni reportes recientes | aviso de desconexión | PASS (RF11) |

Durante la prueba, la ESP32 siguió estable: `HEALTH` a las 02:57:52 UTC con 0 caídas de WiFi y MQTT y una iteración máxima del `loop()` de 16 ms. En ese Shadow, `presence: true` corresponde a una persona frente al sensor en el momento de la captura.
