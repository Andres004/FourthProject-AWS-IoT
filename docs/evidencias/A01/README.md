# Evidencia A01: Vinculación, cambio y desvinculación por voz

Prueba A01 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 22:29–22:49 (hora de Bolivia; 02:29–02:49 UTC del 10/11). Simulador de Alexa en Spanish (US), con un único usuario (hash `40fdb5ffb4` en el log).

| Archivo | Qué muestra |
|---|---|
| A01_00_dynamodb_antes.png | Tabla `user_thing` antes de la prueba: 3 ítems de pruebas anteriores |
| A01_01_dynamodb_vacia.png | Tabla vacía, punto de partida |
| A01_02 a A01_18 (*.png) | Cada frase del simulador con su respuesta y el JSON de Skill I/O, y las capturas de DynamoDB después de cada cambio |
| A01_cloudwatch.csv | Exportación de Logs Insights: las 14 líneas `SKILL_REQUEST` de la prueba |
| A01_analisis.txt | Salida de `analyze_log.py` para el CSV |

| Paso | Frase | Respuesta | `result` en el log | Captura | Estado |
|---|---|---|---|---|---|
| 1 | abre monoambiente inteligente | "Bienvenido. Todavía no tienes una casa vinculada…" | `LaunchRequest`, `thing=None` | A01_02 | OK |
| 2 | hay alguien en la puerta | "Todavía no tienes una casa vinculada. Di: vincula mi casa…" | `not_linked` | A01_03 | OK (RF8) |
| 3 | vincula … uno dos tres | "El código debe tener seis dígitos y no empezar en cero." | `invalid_code` | A01_04 | OK (RF9) |
| 4 | vincula … nueve × 6 | "No encontré ninguna casa con el código 999999…" | `thing_not_found` | A01_05 | OK (RF9) |
| 5 | vincula … 739264 | "Listo, tu casa con el código 739264 quedó vinculada." | `linked` | A01_06, A01_07 | OK (RF7) |
| 6 | vincula … 739264 | "Tu casa ya estaba vinculada con el código 739264." | `already_linked` | A01_08 | OK |
| 7 | cambia mi casa al código 518306 | "Listo, cambié tu vinculación al código 518306." | `changed` | A01_09, A01_10, A01_11 | OK (RF9) |
| 8 | vincula … 739264 | "Listo, cambié tu vinculación al código 739264." | `changed` | A01_12 | OK (RF9) |
| 9 | desvincula mi casa | "Tu casa quedó desvinculada." | `unlinked` | A01_13, A01_14 | OK (RF9) |
| 10 | desvincula mi casa | "No tienes ninguna casa vinculada." | `not_linked` | A01_15 | OK |
| 11 | vincula … 739264 | "Listo, tu casa … quedó vinculada." | `linked` | A01_16 | OK |
| 12 | detener | "Hasta luego." | `AMAZON.StopIntent` | A01_17 | OK |
| 13 | abre monoambiente inteligente (sesión nueva) | "Bienvenido. Puedes abrir o cerrar la puerta…" | `LaunchRequest`, `thing=monoambiente-739264` | A01_18 | OK (RF7, persistió) |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas correctas | 13/13 | todas | PASS |
| Ítems en DynamoDB por usuario | 1 en cada captura; el cambio reemplaza el ítem (`fechaVinculacion` 02:37 → 02:39, `thingName` 739264 → 518306) | 1 | PASS (RF7, RF9) |
| Datos inválidos guardados | 0 (la tabla no cambió en los pasos 3 y 4) | 0 | PASS (RF9) |
| Solicitudes con `error` | 0 de 14 | 0 | PASS |
| Tiempo de la Lambda (`lambda_ms`) | mediana 76 ms, máx. 486 ms | — | INFO |

El primer `SessionEndedRequest` del log (02:34:15) es el cierre de una sesión anterior del simulador. La línea `RNF3 … NOT ENOUGH DATA` del análisis es esperable: A01 no incluye comandos de la puerta, y RNF3 se mide en A05.
