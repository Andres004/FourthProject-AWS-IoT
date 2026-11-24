# Tablas de DynamoDB

Región `us-east-2`, capacidad **on-demand** (se paga por solicitud; a este volumen son centavos al mes).

## `smartloft-user-thing`: qué Things tiene cada usuario de Alexa

| Propiedad | Valor |
|---|---|
| Clave de partición | `userId` (String): el `context.System.user.userId` que envía Alexa |
| Clave de ordenamiento | `place` (String): `vent` o `lights` |
| Otros atributos | `thingName` (S), `homeCode` (S), `linkedAt` (S, ISO 8601 en UTC) |

Cada código de casa crea **dos ítems** por usuario, uno por placa:

```json
{ "userId": "amzn1.ask.account.…", "place": "vent",   "thingName": "smartloft-739264-vent",   "homeCode": "739264", "linkedAt": "2026-11-24T05:57:12+00:00" }
{ "userId": "amzn1.ask.account.…", "place": "lights", "thingName": "smartloft-739264-lights", "homeCode": "739264", "linkedAt": "2026-11-24T05:57:12+00:00" }
```

| Operación | Cuándo | Método |
|---|---|---|
| `Query userId = :u` | En cada intent que necesita la casa del usuario (patrón P4) | `LinkRepository.find_things()` |
| `PutItem` ×2 | Al vincular o cambiar la vinculación | `LinkRepository.save()` |
| `DeleteItem` ×2 | Al desvincular | `LinkRepository.delete()` |

## `smartloft-data`: lecturas y eventos de las placas

| Propiedad | Valor |
|---|---|
| Clave de partición | `thingName` (String) |
| Clave de ordenamiento | `timestamp` (Number): `timestamp()` de la regla, ms, reloj de AWS |
| Índice secundario global | `event-index`: PK `eventKey` (String), SK `timestamp` (Number), proyección ALL |
| TTL | Atributo `expiresAt` (epoch en segundos): lecturas 30 días, eventos 365 días |

| Atributo | Tipo | Notas |
|---|---|---|
| `thingType`, `serialNumber`, `place` | S | Del tema MQTT (`smartloft`, `739264`, `vent`) |
| `recordType` | S | `reading` (`heartbeat`, `gas_changed`) o `event` (el resto) |
| `event`, `origin` | S | `origin` = quién causó el último cambio: `voice`, `cloud`, `edge`, `boot` (RF12) |
| `eventKey` | S | `<thingName>#<event>`, **solo en eventos**: el índice es disperso y no carga las lecturas |
| `gasPct` (N), `gasMv` (N), `gasAlarm` (BOOL), `warmingUp` (BOOL), `window` (S), `servoAngle` (N), `mode` (S), `gasHighPct` (N), `gasLowPct` (N) | | Ítems de `vent` |
| `lightKitchen`, `lightLiving`, `lightDining`, `lightBathroom`, `lightBedroom` (S), `presence` (BOOL) | | Ítems de `lights` |
| `seq`, `deviceTs`, `storedTs` | N | Integridad (`seq`) y latencia (`storedTs − timestamp`, `storedTs − deviceTs`) |

`timestamp` es palabra reservada de DynamoDB: en expresiones escritas a mano se usa `#ts` con `ExpressionAttributeNames`.

### Patrones de acceso

| # | Patrón | Consulta | Lo usa |
|---|---|---|---|
| P1 | Registros de un Thing en un rango | `thingName = :t AND #ts BETWEEN :a AND :b` | Mockups (curva de gas, uso de luces), prueba A08 |
| P2 | Eventos de un tipo en un rango | `event-index`: `eventKey = :k AND #ts BETWEEN :a AND :b` | C1 (alarmas de 24 h), mockups de alarmas y presencia |
| P3 | Últimos N registros de un Thing | `thingName = :t`, `ScanIndexForward = false`, `Limit = N` | Demo y depuración |
| P4 | Things de un usuario | `smartloft-user-thing`: `userId = :u` | Skill |

Ninguna Lambda hace `Scan`.
