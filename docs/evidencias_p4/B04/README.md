# B04 — Costo mensual estimado frente a la capa gratuita

- Fecha: 24/11/2026, 14:10 (Bolivia)
- Responsable: Dabner
- Requisito: RNF12 (costo)
- Base: el conteo real de [A08](../A08/README.md) (66 min con las dos placas y las pruebas de voz y gas) extrapolado a 30 días
- Precios: precios de lista públicos de AWS para US East, consultados el 24/11/2026 en las páginas de precios de [AWS IoT Core](https://aws.amazon.com/iot-core/pricing/), [AWS Lambda](https://aws.amazon.com/lambda/pricing/) y [Amazon DynamoDB](https://aws.amazon.com/dynamodb/pricing/on-demand/). Son una **estimación**: no se verificaron en la calculadora oficial para us-east-2, y AWS puede cambiarlos

## Volumen medido y extrapolado

| Dato | Valor | Fuente |
|---|---|---|
| Reportes en A08 | 96 (placa 1) + 80 (placa 2) en 66 min = **160 por hora** con actividad de pruebas | Logs de A08 |
| Reportes en reposo (solo heartbeats) | 2 placas × 60 por hora = **120 por hora** | Política de reporte (§2.8) |
| Ítems guardados por reporte | 1 (100 % de integridad); el 16 % son eventos y escriben además en el índice `event-index` | A08 |
| Lambda de datos | 1 invocación por reporte, 256 MB, ≈ 20 ms facturados (8–19 ms medidos en caliente) | `aws/README.md`, CloudWatch |
| Skill | Supuesto: 20 solicitudes por día, ≈ 8 operaciones de Shadow cada una (lectura más la espera de confirmación) | — |

| Concepto mensual (30 días) | Escenario "demo" (160/h) | Escenario "reposo" (120/h) | Capa gratuita de IoT Core (12 meses) |
|---|---|---|---|
| Reportes | 115 200 | 86 400 | — |
| Mensajes de IoT Core | 115 200 | 86 400 | 500 000 |
| Operaciones de Shadow | 120 000 | 91 200 | 225 000 |
| Minutos de conexión (2 placas) | 86 400 | 86 400 | 2 250 000 |
| Reglas disparadas (2 por reporte) | 230 400 | 172 800 | 250 000 |
| Acciones de reglas | 115 200 | 86 400 | 250 000 |
| Invocaciones de Lambda | 115 800 | 87 000 | 1 000 000 (siempre gratuita) |
| Cómputo de Lambda | 651 GB-s | 507 GB-s | 400 000 GB-s (siempre gratuita) |
| Escrituras en DynamoDB (WRU) | 133 527 | 100 145 | — (on-demand no tiene capa gratuita) |
| Almacenamiento en DynamoDB | ≈ 69 MB (el TTL lo limita) | ≈ 52 MB | 25 GB (siempre gratuita) |

## Costo

| Servicio | Precio de lista | "Demo" | "Reposo" |
|---|---|---|---|
| IoT Core, mensajes | 1.00 USD / millón | 0.115 | 0.086 |
| IoT Core, Shadow | 1.25 USD / millón | 0.150 | 0.114 |
| IoT Core, conexión | 0.08 USD / millón de minutos | 0.007 | 0.007 |
| IoT Core, reglas disparadas | 0.15 USD / millón | 0.035 | 0.026 |
| IoT Core, acciones | 0.15 USD / millón | 0.017 | 0.013 |
| Lambda, solicitudes | 0.20 USD / millón | 0.023 | 0.017 |
| Lambda, cómputo | 0.0000166667 USD / GB-s | 0.011 | 0.009 |
| DynamoDB, escrituras on-demand | 0.625 USD / millón de WRU | 0.084 | 0.063 |
| DynamoDB, almacenamiento | 0.25 USD / GB-mes | 0.017 | 0.013 |
| **Total sin capa gratuita** | | **≈ 0.46 USD / mes** | **≈ 0.35 USD / mes** |
| **Total con la capa gratuita de 12 meses** | Solo DynamoDB on-demand | **≈ 0.10 USD / mes** | **≈ 0.08 USD / mes** |

La cuenta es de Ricardo; no se verificó si tiene la capa gratuita clásica de 12 meses o el plan de créditos de las cuentas creadas desde julio de 2025. En cualquiera de los dos casos el consumo es de centavos por mes.

## Análisis

- **El costo no es el límite; las cuotas de la capa gratuita sí.** Con 2 placas, el recurso más cercano a su límite gratuito son las **reglas disparadas: 230 400 de 250 000 (92 %)**, porque las dos reglas escuchan el mismo tema y AWS cuenta cada una por cada reporte, aunque la de control filtre casi todo con su `WHERE`. Con una tercera placa se superaría; el costo extra sería ≈ 0.02 USD por cada 100 000 reglas.
- **Lo que más cuesta son el Shadow y los mensajes**, proporcionales a la frecuencia de reporte. El heartbeat de 60 s representa el 75 % del volumen ("reposo" frente a "demo"); subirlo a 5 minutos bajaría el costo de IoT Core a la quinta parte, a cambio de detectar una placa caída más tarde.
- **DynamoDB on-demand** cobra desde la primera escritura (≈ 0.08 USD/mes). Con capacidad provisionada de 1–2 WCU (un reporte cada 22 s en promedio) entraría en la capa gratuita permanente de 25 WCU.
- **Lambda** queda muy por debajo de la capa gratuita permanente (12 % de las invocaciones y < 0.2 % del cómputo).

**Veredicto: PASS** (RNF12): ≈ 0.10 USD por mes con la capa gratuita y ≈ 0.46 USD sin ella, en el escenario de uso más intenso medido.
