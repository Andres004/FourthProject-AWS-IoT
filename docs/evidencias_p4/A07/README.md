# A07 — Convivencia de la voz con la lógica automática

- Fecha y hora: 24/11/2026, 08:45–08:50 (Bolivia) / 12:45–12:50 UTC
- Responsable: Dabner
- Requisito: §3.1 del enunciado (cómo conviven los comandos de voz y la lógica automática); §2.6 y §2.12 del informe
- Archivos: [A07_01](A07_01_abrir_en_automatico.png), [A07_02](A07_02_cerrar_con_alarma_y_consulta_gas.png), capturas de [A04](../A04/README.md) y [A06](../A06/README.md); log de la placa 1 en [A08](../A08/A08_vent_ESP32.log)

Una frase por situación de la tabla de convivencia:

| Situación | Frase | Respuesta de la skill | ¿Escribió `desired`? | En la placa | Veredicto |
|---|---|---|---|---|---|
| Ventana en modo `auto` | `abre la ventana` | "La ventilación está en modo automático. Si quieres manejar la ventana, di: activa el modo manual." | No | Sin `DELTA_RX` | PASS |
| "Cerrar" con alarma de gas (en `manual`) | `cierra la ventana` | "No puedo cerrarla: el índice de gas es 82,9 por ciento, por encima del umbral de 15." | No | La ventana no se movió | PASS |
| Consulta durante la alarma | `hay gas en la cocina` | "Sí, hay alarma de gas: el índice es 74,6 por ciento, por encima del umbral de 15. La ventana está cerrada." | — | — | PASS |
| Umbral bajo ≥ alto | `cambia el umbral bajo a veinticinco por ciento` | "El umbral bajo tiene que ser menor que el alto…" | No | — | PASS ([A04](../A04/README.md)) |
| Umbral fuera de rango | `cambia el umbral alto a cien por ciento` | "El umbral tiene que ser un número entero entre 1 y 99 por ciento." | No | — | PASS ([A04](../A04/README.md)) |
| Ventana en `manual` sin alarma | `abre la ventana` / `cierra la ventana` | "Listo, la ventana está abierta / cerrada." | Sí | Se movió (origen `voice`) | PASS ([A03](../A03/README.md)) |
| La Nube vuelve a `auto` (C1) mientras el usuario estaba en `manual` | `en qué modo está la ventilación` | "La ventilación está en modo automático." | — | `MODE_APPLIED origin=cloud` | PASS ([A06](../A06/README.md)) |
| Placa sin reportar > 150 s | `hay gas en la cocina`, `cambia el umbral alto a dieciocho por ciento`, `enciende la luz de la cocina` | "…Ojo: tu casa no se reporta desde hace 3 minutos…" / "Envié la orden, pero tu casa está desconectada. Se aplicará apenas vuelva a conectarse." | Sí (encolada) | Aplicadas al reconectar, `origin=voice` | PASS ([A09](../A09/README.md)) |

**Prioridad.** La lógica automática tiene prioridad sobre la voz en `auto`; en `manual` la voz mueve la ventana, salvo para cerrarla con gas. La placa repite las mismas reglas aunque la orden llegue por `desired` (casos V08 y V13 de [B02](../B02/README.md)).

**Veredicto: PASS** en las 8 situaciones probadas.
