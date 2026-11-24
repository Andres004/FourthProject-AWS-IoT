# Evidencia B01: Pruebas unitarias de la Lambda

Prueba B01 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026.

| Archivo | Qué muestra |
|---|---|
| B01_salida.txt | Salida de `python -m unittest discover -s lambda/tests -v` |

Las pruebas de [test_lambda_function.py](../../../lambda/tests/test_lambda_function.py) envían sobres de solicitud reales de Alexa a `lambda_handler`. DynamoDB, AWS IoT y AWS IoT Data se reemplazan por objetos en memoria; el de IoT Data simula una ESP32 que copia `desired` en `reported` después de algunas lecturas, o que nunca responde. Un reloj simulado evita esperar los 3 s reales.

| Requisito | Pruebas | Qué verifican | Resultado |
|---|---|---|---|
| RF4 | `test_rf4_presence_true_and_false`, `test_rf4_missing_attribute_or_shadow_says_no_data`, `test_rf4_reads_reported_not_desired` | Respuesta según `reported.presence`; sin dato o sin Shadow no falla; nunca lee `desired` | 3/3 ok |
| RF5, RF10 | `test_rf5_rf10_open_and_close_are_confirmed_by_device`, `test_rf5_door_already_in_position_is_not_rewritten`, `test_rf5_cancels_pending_opposite_order`, `test_rf10_no_confirmation_within_3_s_is_reported` | Escribe `desired`, espera la confirmación, no reescribe si ya está en esa posición y avisa si no hay confirmación en 3 s (corta entre 3.00 y 3.25 s) | 4/4 ok |
| RF6 | `test_rf6_door_open_and_closed` | "abierta"/"cerrada" según `reported.door` | 1/1 ok |
| RF7 | `test_rf7_link_valid_code_stores_link_with_date`, `test_rf7_link_persists_between_sessions` | Guarda `thingName` y `fechaVinculacion` ISO 8601; el vínculo sirve en otra sesión | 2/2 ok |
| RF8 | `test_rf8_unlinked_user_is_guided_to_link`, `test_rf8_each_user_reaches_only_their_own_thing`, `test_rf8_launch_greets_linked_and_unlinked_users` | Guía al usuario sin vincular en los 4 intents; dos usuarios no se cruzan | 3/3 ok |
| RF9 | `test_rf9_rejects_invalid_codes_without_saving`, `test_rf9_rejects_thing_that_does_not_exist`, `test_rf9_change_link_replaces_previous_thing`, `test_rf9_same_code_again_reports_already_linked`, `test_rf9_unlink_deletes_link` | 7 códigos inválidos (`?`, `abc`, 5 y 7 dígitos, cero inicial, con espacio, vacío) y un Thing inexistente no se guardan; cambiar y desvincular | 5/5 ok |
| RF11 | `test_rf11_offline_threshold_is_150_seconds`, `test_rf11_offline_command_is_queued_in_desired` | 150 s todavía es "conectado" y 151 s ya avisa; un comando con la casa desconectada se encola sin esperar | 2/2 ok |
| Robustez | `test_rf4_rf9_aws_error_is_spoken_and_logged`, `test_unknown_intent_is_answered`, `test_log_line_hides_user_id` | Un error de AWS se responde y se registra; intents sin handler propio; el log guarda un hash del usuario, no su `userId` | 3/3 ok |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Pruebas ejecutadas | 23 | todas `ok` | PASS |
| Pedidos con una línea `SKILL_REQUEST` | 1 por pedido en todas las pruebas | exactamente 1 | PASS |
