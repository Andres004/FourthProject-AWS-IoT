# Evidencias de las pruebas

Una carpeta por prueba del [plan de pruebas](../PLAN_DE_PRUEBAS.md). Cada `README.md` lista sus archivos, la tabla de medidas con el criterio y el veredicto, y las observaciones.

| Prueba | Requisitos | Resultado |
|---|---|---|
| [A01](A01/README.md) Vinculación, cambio y desvinculación por voz | RF7, RF8, RF9 | PASS: 13/13 respuestas, 0 errores |
| [A02](A02/README.md) Dos usuarios con Things distintos | RF8, RF9, RF11 | PASS: cada usuario solo modifica su Shadow |
| [A03](A03/README.md) Consulta del sensor por voz | RF1, RF4, RNF4 | PASS: 8/8 respuestas coinciden con el PIR |
| [A04](A04/README.md) Comandos y estado de la puerta | RF3, RF5, RF6, RF10 | PASS: 6/6; `DELTA_RX` → `reported` en 415 ms |
| [A05](A05/README.md) Tiempo de respuesta extremo a extremo | RNF3, RF10 | PASS: 28/28; mediana 616 ms al servo detenido, máx. 1691 ms confirmado |
| [A06](A06/README.md) Exactitud del PIR y del servo | RNF2, RF1 | PASS: 15/15 cruces, 0 falsos positivos en 5 min, servo < 3° en 0° y 90° |
| [A07](A07/README.md) Caída de WiFi con orden pendiente | RNF5, RF11 | PASS: orden aplicada 3.3–3.8 s después de volver el WiFi; defecto corregido |
| [A08](A08/README.md) Corte de energía con orden pendiente | RNF5, RF10 | PASS: orden aplicada 3.9 s después del arranque |
| [A09](A09/README.md) Comandos inválidos desde AWS | RF12, RF3 | PASS: 3/3 rechazados, 2/2 válidos aplicados |
| [A10](A10/README.md) Estabilidad de 15 min | RNF1, RF2, RNF4 | PASS: 27.3 min, 0 reinicios, 0 caídas, `loop()` máx. 21 ms |
| [B01](B01/README.md) Pruebas unitarias de la Lambda | RF4–RF11 | PASS: 23/23 |
| [B02](B02/README.md) Firmware con transporte serie | RF2, RF3, RF12, RNF4 | PASS: 16/16; defecto corregido |
| [B03](B03/README.md) Secretos en el repositorio | RNF6 | PASS |

**Defectos encontrados por las pruebas y corregidos:**
1. **B02:** el Shadow confirmaba la nueva posición de la puerta antes de que el servo terminara de moverse (resta sin signo en `DoorActuator::update()`).
2. **A07:** con WiFi pero sin internet, los reintentos de MQTT se encadenaban y bloqueaban `loop()` hasta 7 s (`ShadowClient::connect()`).

**Datos ocultos.** Las capturas de la consola están recortadas por arriba para no mostrar el número de cuenta de AWS de la barra de direcciones; en `A01_11` se tapó el `userId` completo de Alexa. En los logs, el endpoint de AWS IoT se reemplazó por `xxxxxxxx-ats.iot…`. La Lambda registra un hash de 10 caracteres del usuario, no su `userId`.

**Horas.** Las capturas muestran la hora de Bolivia (UTC−4); los logs de la ESP32 y de CloudWatch usan UTC.
