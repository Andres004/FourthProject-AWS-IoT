# Reglas de AWS IoT

Región `us-east-2`, SQL versión **2016-03-23**. Las dos reglas escuchan el mismo tema (`update/accepted`), es decir, solo los reportes que el servicio del Shadow ya aceptó.

## `smartloft_data_rule` → `smartloft_data_lambda`

```sql
SELECT topic(3) AS thingName,
       timestamp() AS timestamp,
       substring(topic(3), 0, 9) AS thingType,
       substring(topic(3), 10, 16) AS serialNumber,
       substring(topic(3), 17) AS place,
       state.reported AS reported
FROM '$aws/things/+/shadow/update/accepted'
WHERE substring(topic(3), 0, 9) = 'smartloft'
  AND NOT isUndefined(state.reported)
```

| Elemento | Valor |
|---|---|
| Acción | Lambda `smartloft_data_lambda`, versión `$LATEST` |
| Se dispara con | Cada reporte de las dos placas (eventos y heartbeats de 60 s) |
| No se dispara con | Las escrituras de `desired` de la skill o de la Lambda de control (no traen `state.reported`) y los Things que no son `smartloft-*` |
| Qué agrega la regla | `thingName`, `timestamp` (reloj de AWS, ms), `thingType`, `serialNumber` y `place`, tomados del tema |

## `smartloft_control_rule` → `smartloft_control_lambda`

```sql
SELECT topic(3) AS thingName,
       timestamp() AS timestamp,
       state.reported AS reported
FROM '$aws/things/+/shadow/update/accepted'
WHERE substring(topic(3), 0, 9) = 'smartloft'
  AND NOT isUndefined(state.reported)
  AND state.reported.event = 'gas_alarm_on'
```

| Elemento | Valor |
|---|---|
| Acción | Lambda `smartloft_control_lambda`, versión `$LATEST` |
| Se dispara con | Solo el reporte del **inicio** de una alarma de gas (`event = gas_alarm_on`) |
| Por qué filtra por **evento** y no por estado | Filtrar por `gas_alarm = true` la dispararía con cada heartbeat mientras dure la alarma, y cada `desired` que escribe la Lambda podría volver a dispararla (bucle). El evento ocurre una sola vez por alarma |

## Por qué dos reglas y dos Lambdas

| | Datos | Control |
|---|---|---|
| Responsabilidad | Validar y guardar todo | Aplicar C1 |
| Frecuencia | ~1 por minuto por placa | Pocas veces al día |
| Permisos mínimos | `dynamodb:PutItem` en `smartloft-data` | `dynamodb:Query` en `event-index` e `iot:UpdateThingShadow` en `smartloft-*-vent` |

Juntas, la función que guarda cada heartbeat tendría permiso para mover la ventana, y la lógica de C1 correría con cada mensaje (más costo y más riesgo). Separadas, cada una tiene solo los permisos que usa.

**Carrera entre reglas.** Las dos reglas se disparan en paralelo con el mismo mensaje, así que cuando corre la de control la alarma actual puede estar guardada o no. La Lambda de control cuenta las alarmas guardadas por su par (`seq`, `deviceTs`), excluye la actual y la suma una vez ([lambda/control/lambda_function.py](../lambda/control/lambda_function.py)).

**Permiso de invocación.** Al elegir la acción Lambda, la consola agrega a cada función un permiso para que `iot.amazonaws.com` la invoque solo desde su regla ([lambda-invoke-permissions.json](lambda-invoke-permissions.json)).
