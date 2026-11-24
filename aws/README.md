# Configuración de AWS y Alexa exportada (SmartLoft, P4)

`<account-id>` y `<skill-id>` reemplazan el número de cuenta de AWS y el ID de la skill, que no se publican. Ningún archivo contiene certificados, claves ni access keys.

| Archivo | Qué es |
|---|---|
| [iot-policy-usada.json](iot-policy-usada.json) | Política `smartloft-policy` **tal como está en AWS** (`Allow * *`), asociada a los certificados de las dos placas |
| [iot-policy.json](iot-policy.json) | Política **mínima** equivalente: cada certificado solo opera sobre el Shadow de su propio Thing |
| [iot-rules.md](iot-rules.md) | SQL, acción y justificación de `smartloft_data_rule` y `smartloft_control_rule` |
| [lambda-data-policy.json](lambda-data-policy.json) | Permisos **mínimos** de `smartloft_data_lambda` |
| [lambda-control-policy.json](lambda-control-policy.json) | Permisos **mínimos** de `smartloft_control_lambda` |
| [lambda-skill-policy.json](lambda-skill-policy.json) | Permisos **mínimos** de `smartloft_skill_lambda` |
| [lambda-invoke-permissions.json](lambda-invoke-permissions.json) | Quién puede invocar cada Lambda (las dos reglas y la skill) |
| [dynamodb-tables.md](dynamodb-tables.md) | `smartloft-user-thing` y `smartloft-data` (claves, índice, TTL y patrones de acceso) |
| [../alexa/interaction-model.es-US.json](../alexa/interaction-model.es-US.json) | Modelo de interacción de la skill (Spanish US) |

## Recursos creados

| Recurso | Configuración |
|---|---|
| Región | `us-east-2` (Ohio) para IoT Core, Lambda y DynamoDB |
| Things (Shadow clásico) | `smartloft-739264-vent` y `smartloft-739264-lights` (placas reales, un certificado cada uno); `smartloft-518306-vent` y `smartloft-518306-lights` (sin hardware ni certificado, para probar un segundo usuario) |
| Client ID de MQTT | El nombre del Thing ([ShadowClient.cpp](../lib/SmartObjectCore/ShadowClient.cpp)) |
| Tablas | `smartloft-user-thing` y `smartloft-data` con `event-index` y TTL en `expiresAt`, on-demand |
| Skill | `monoambiente inteligente`, Spanish (US); endpoint = ARN de `smartloft_skill_lambda` |

### Funciones Lambda

Las tres: Python 3.13, x86_64, handler `lambda_function.lambda_handler`, memoria 256 MB.

| Función | Código | Disparador | Timeout | Variables de entorno |
|---|---|---|---|---|
| `smartloft_data_lambda` | [lambda/data](../lambda/data/lambda_function.py) | `smartloft_data_rule` | 15 s | Ninguna: usa los valores por defecto del código (`TABLE_NAME = smartloft-data`, `READING_TTL_DAYS = 30`, `EVENT_TTL_DAYS = 365`) |
| `smartloft_control_lambda` | [lambda/control](../lambda/control/lambda_function.py) | `smartloft_control_rule` | 15 s | `IOT_ENDPOINT`; por defecto `TABLE_NAME = smartloft-data`, `EVENT_INDEX = event-index`, `GAS_EVENTS_LIMIT = 3`, `GAS_EVENTS_WINDOW_H = 24`, `IOT_REGION = us-east-2` |
| `smartloft_skill_lambda` | [lambda/skill](../lambda/skill/lambda_function.py) (zip con `ask-sdk-core`) | Alexa Skills Kit, con verificación del Skill ID | 10 s | `IOT_ENDPOINT`, `IOT_REGION = us-east-2`, `USER_TABLE = smartloft-user-thing` |

**Timeout.** Con el valor por defecto (3 s), la primera invocación de `smartloft_data_lambda` se cortó dos veces en 3000 ms: el arranque en frío (carga de boto3 y conexión a DynamoDB) tardó 3147 ms. Con 15 s guardó a la primera, y las invocaciones siguientes tardan entre 8 y 19 ms. Las Lambdas de las reglas se invocan de forma asíncrona, así que un timeout más largo no demora a nadie. La de la skill queda en 10 s: los 3 s de espera de confirmación más el arranque en frío, por debajo del límite de 8 s de Alexa en el caso normal.

**Paquete de la skill.** Desde la raíz del repo:

```powershell
python -m pip install -r lambda/skill/requirements.txt -t lambda/skill/package
```

Después se comprime el contenido de `lambda/skill/package` junto con `lambda/skill/lambda_function.py` en la raíz del zip (`lambda/skill/skill_deployment.zip`, que git ignora) y se sube con **Upload from → .zip file**.

## Permisos asignados frente a los mínimos

| Recurso | Asignado | Motivo | Mínimo |
|---|---|---|---|
| Política de IoT de los certificados | `Allow` `*` sobre `*` | Configuración inicial y pruebas con el MQTT test client; la consigna lo acepta si se documenta | Cada certificado solo puede conectarse con el client ID de su Thing y usar su Shadow, gracias a la variable `${iot:Connection.Thing.ThingName}` ([iot-policy.json](iot-policy.json)) |
| Rol de las tres Lambdas | **PowerUserAccess**, que la consola nueva de Lambda asigna por defecto al rol que crea, más los permisos de logs | Es lo que creó la consola; los permisos amplios se aceptan en desarrollo | Cada Lambda, solo lo que usa: datos `PutItem`; control `Query` en el índice y `UpdateThingShadow` en `-vent`; skill `Query`/`PutItem`/`DeleteItem` en su tabla y `DescribeThing`/`GetThingShadow`/`UpdateThingShadow` en `smartloft-*` |

**Riesgo de los permisos amplios.** Con `Allow * *`, quien robe el certificado de una placa puede publicar en el Shadow de **cualquier** Thing de la cuenta. Con PowerUserAccess, un error en una Lambda podría borrar tablas o funciones de toda la cuenta. Con los mínimos, el certificado de la placa 1 solo toca `smartloft-739264-vent`, y la Lambda de datos solo puede **agregar** ítems a `smartloft-data`: no puede leer, borrar ni mover un actuador.

**Por qué la Lambda de control solo puede escribir en `-vent`.** C1 solo cambia el modo de la ventilación; si la Lambda tuviera un error, no podría encender ni apagar luces.

**Por qué la skill necesita `iot:DescribeThing`.** Antes de guardar una vinculación comprueba que existan los dos Things del código (`LinkThingHandler`).

## Acceso a la cuenta

La cuenta de AWS es de un integrante (Andrés) y está dentro de una organización administrada por AWS cuya política de control de servicios **prohíbe crear contraseñas de consola para usuarios IAM** (`iam:CreateLoginProfile`, denegación explícita). Por eso el otro integrante no tiene usuario propio en la consola: trabaja sobre las placas y el firmware, y las verificaciones en AWS las hace el dueño de la cuenta.
