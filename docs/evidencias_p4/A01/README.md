# A01 — Vinculación usuario ↔ Things por voz

- Fecha y hora: 24/11/2026, 08:30–08:40 (Bolivia) / 12:30–12:40 UTC
- Responsable: Dabner (A01_01 es una captura previa de Ricardo)
- Requisitos: RF7 (vinculación persistente), RF8 (Things por usuario), RF9 (validar, cambiar y eliminar)
- Entorno: Alexa Developer Console → Test → Development (Spanish US), skill `monoambiente inteligente`; tabla `smartloft-user-thing` en DynamoDB. Se hizo mientras corría A08 (las órdenes de vinculación no tocan las placas)

| # | Frase escrita en el simulador | Respuesta | Esperado | Captura |
|---|---|---|---|---|
| 1 | `abre monoambiente inteligente` | "Bienvenido. Puedes manejar las luces, la ventana y la ventilación, o preguntar si hay gas." | Bienvenida | [A01_02](A01_02_abrir.png) |
| 2 | `vincula mi casa con el código uno dos tres` | "El código debe tener seis dígitos y no empezar en cero." | Rechazo por formato | [A01_03](A01_03_codigo_corto.png) |
| 3 | `vincula mi casa con el código nueve nueve nueve nueve nueve nueve` | "No encontré ninguna casa con el código 999999. Revisa el código e inténtalo otra vez." | Rechazo: el Thing no existe | [A01_04](A01_04_codigo_inexistente.png) |
| 4 | `vincula mi casa con el código siete tres nueve dos seis cuatro` | "Tu casa ya estaba vinculada con el código 739264." | Vinculada (ya lo estaba) | [A01_05](A01_05_vincular_739264.png) |
| 5 | `detener` | "Hasta luego." (antes, una frase compuesta no reconocida respondió con la ayuda: intent Fallback) | Cierra la sesión | [A01_06](A01_06_detener.png) |
| 6 | `abre monoambiente inteligente` (sesión nueva) | Bienvenida de usuario vinculado | La vinculación persiste | [A01_07](A01_07_nueva_sesion_recuerda.png) |
| — | DynamoDB `smartloft-user-thing` | 2 ítems del usuario: `vent` y `lights`, `homeCode = 739264` | Un código → dos Things | [A01_08](A01_08_dynamodb_dos_items.webp) |
| 7 | `cambia mi casa al código cinco uno ocho tres cero seis` | "Listo, cambié tu vinculación al código 518306." | Cambio | [A01_09](A01_09_cambiar_518306.png) |
| — | DynamoDB | Los 2 ítems pasan a `smartloft-518306-vent` y `-lights` | Reemplazo de los dos ítems | [A01_10](A01_10_dynamodb_518306.png) |
| 8 | `desvincula mi casa` | "Tu casa quedó desvinculada." | Borrado | [A01_11](A01_11_desvincular.png) |
| 9 | `hay gas en la cocina` (sin vinculación) | "Todavía no tienes una casa vinculada. Di: vincula mi casa con el código, seguido de los seis dígitos." | Guía para vincular | [A01_12](A01_12_sin_vincular_y_volver_739264.png) |
| 10 | `vincula mi casa con el código siete tres nueve dos seis cuatro` | "Listo, tu casa con el código 739264 quedó vinculada." | Vinculada | [A01_12](A01_12_sin_vincular_y_volver_739264.png) |
| — | DynamoDB | 2 ítems con `smartloft-739264-vent` y `-lights` | Estado final | [A01_13](A01_13_dynamodb_739264_final.png) |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Respuestas correctas | 10 / 10 | todas | PASS |
| Códigos inválidos guardados en DynamoDB | 0 | 0 | PASS |
| Ítems por vinculación | 2 (`vent` y `lights`) | 2 | PASS |
| Persistencia entre sesiones | Sí (paso 6) | Sí | PASS |

Las capturas de DynamoDB muestran el `userId` recortado (`amzn1.ask.account.AM…`); no se publica completo.

**Veredicto: PASS** (RF7, RF8, RF9).
