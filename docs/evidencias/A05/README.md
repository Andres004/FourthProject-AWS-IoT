# Evidencia A05: Tiempo de respuesta extremo a extremo

Prueba A05 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026, 23:24–23:49 (hora de Bolivia; 03:24–03:49 UTC del 10/11). Se hizo en la misma corrida que [A10](../A10/README.md).

| Archivo | Qué muestra |
|---|---|
| A05_cloudwatch.csv | Líneas `SKILL_REQUEST` de la Lambda; incluye las pruebas anteriores de la sesión |
| A05_analisis.txt | `analyze_log.py` con este CSV y con `../A10/A10_ESP32.log`: cada comando cruzado por versión del Shadow |
| A05_captura_602.png, 603, 604 | Respuestas "Listo, la puerta está abierta/cerrada" durante la corrida |

Se midió de dos formas independientes:

1. **Un solo reloj (Lambda).** `confirm_ms` va desde que la Lambda recibe el intent hasta que lee `reported.door` con la nueva posición. Incluye `UpdateThingShadow`, la entrega del `delta`, los 400 ms del servo, el reporte de la ESP32 y la espera de la consulta periódica de la Lambda (cada 250 ms). Es una cota superior del tiempo real.
2. **Dos relojes (Lambda + NTP de la ESP32).** Une cada comando con su `DELTA_RX` por el número de versión del Shadow, y mide desde que la Lambda recibe el intent hasta `ACTUATOR_DONE` (servo detenido). El error del NTP de la ESP32 es de decenas de ms.

| Medida | n | Mín. | Mediana | p95 | Máx. | Límite | Veredicto |
|---|---|---|---|---|---|---|---|
| `confirm_ms` (Lambda → puerta confirmada en `reported`) | 28 | 876 ms | 919 ms | 1304 ms | 1691 ms | 3000 ms | PASS (RNF3) |
| Lambda → servo detenido (dos relojes) | 28 | 537 ms | 616 ms | 872 ms | 984 ms | 3000 ms | PASS (RNF3) |
| `UpdateThingShadow` → `DELTA_RX` (nube) | 28 | 18 ms | 96 ms | 308 ms | 391 ms | — | INFO |
| Respuestas "Listo, la puerta está …" (`confirmed`) | 28/28 | | | | | todas | PASS (RF10) |

En `A05_analisis.txt`, las líneas de la Lambda cuentan 31 comandos porque el CSV también incluye los 3 de A04. Todos están dentro del límite.

**Desglose del peor caso de dos relojes (984 ms, versión 412, primer comando de la corrida):** fue el primer comando después de 5 min sin comandos (`confirm_ms` 1304 ms). La causa más probable es que el contenedor de la Lambda o sus conexiones con AWS IoT estaban inactivas; el log no permite separarlo con más detalle. Desde el segundo comando, el tiempo se estabilizó entre 537 y 872 ms.

El tiempo que el simulador tarda en convertir el texto en un intent no se puede medir desde la Lambda; la prueba lo excluye de forma explícita. Para el tiempo percibido por el usuario, A04 incluye videos con la respuesta y el movimiento.
