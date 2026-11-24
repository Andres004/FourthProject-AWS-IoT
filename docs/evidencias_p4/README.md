# Evidencias de la Práctica 4

Una carpeta por prueba del [plan de pruebas](../../Informe_P4.md#41-plan-de-pruebas). Cada carpeta tiene un `README.md` con la fecha, la hora de Bolivia y UTC, el responsable, el commit del firmware o la versión de la Lambda, la tabla de medidas, el criterio y el veredicto, además de los datos crudos (logs, CSV, capturas, videos).

| Prueba | Qué | Carpeta |
|---|---|---|
| A01 | Vinculación y dos usuarios | `A01/` |
| A02 | Las 5 luces por voz | `A02/` |
| A03 | Gas y ventana por voz | `A03/` |
| A04 | Modo y umbrales por voz | `A04/` |
| A05 | Regla E1 y respuesta Edge | `A05/` |
| A06 | Regla C1 y respuesta Nube | `A06/` |
| A07 | Convivencia voz / automático | `A07/` |
| A08 | Integridad y latencia del almacenamiento | `A08/` |
| A09 | Operación sin conexión | `A09/` |
| A10 | Hardware y calibración del MQ-2 | `A10/` |
| A11 | Estabilidad | `A11/` |
| A12 | Exactitud del PIR | `A12/` |
| B01 | Pruebas unitarias de las Lambdas | `B01/` |
| B02 | Firmwares en `*_local_test` | `B02/` |
| B03 | Secretos en el repositorio | `B03/` |
| B04 | Costo mensual | `B04/` |

Plantilla del `README.md` de cada prueba:

```markdown
# A0X — <nombre>

- Fecha y hora (Bolivia / UTC):
- Responsable:
- Commit del firmware / versión de la Lambda:
- Requisito(s):
- Archivos: <log>, <csv>, <captura>

| # | Valor medido | Unidad |
|---|---|---|

Mín. / máx. / promedio / error máx.:
Criterio:
Veredicto: PASS / FAIL — <causa si FAIL>
```
