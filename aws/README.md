# Configuración de AWS y Alexa exportada

`<account-id>` reemplaza el número de cuenta de AWS, que no se publica. Ningún archivo contiene certificados, claves ni access keys.

| Archivo | Qué es |
|---|---|
| [iot-policy-usada.json](iot-policy-usada.json) | Política `monoambiente-policy` **tal como está en AWS** (`Allow * *`), asociada al certificado del Thing |
| [iot-policy.json](iot-policy.json) | Política **mínima** equivalente para producción |
| [lambda-role-policy.json](lambda-role-policy.json) | Permisos **mínimos** del rol de la Lambda `monoambiente-skill` |
| [dynamodb-table.md](dynamodb-table.md) | Definición de la tabla de vinculaciones `user_thing` |
| [../alexa/interaction-model.es-US.json](../alexa/interaction-model.es-US.json) | Modelo de interacción de la skill (Spanish US) |

## Permisos asignados y por qué

| Recurso | Asignado | Motivo | Mínimo para producción |
|---|---|---|---|
| Política de IoT del certificado | `Allow` `*` sobre `*` | Simplifica la configuración inicial y las pruebas con el MQTT test client; la consigna lo acepta si se documenta (§3.2) | `iot:Connect` solo con client ID `monoambiente-739264`; `iot:Publish`, `iot:Receive` y `iot:Subscribe` solo en `$aws/things/monoambiente-739264/shadow/*` ([iot-policy.json](iot-policy.json)) |
| Rol de la Lambda | Políticas administradas `AWSIoTFullAccess` y `AmazonDynamoDBFullAccess`, más `AWSLambdaBasicExecutionRole`, que crea la consola | Es lo que se usó en clase y evita errores de permisos durante el desarrollo | `iot:GetThingShadow`, `iot:UpdateThingShadow` e `iot:DescribeThing` sobre `thing/monoambiente-*`; `dynamodb:GetItem`, `PutItem` y `DeleteItem` sobre `table/user_thing`; escritura de logs en su grupo de CloudWatch ([lambda-role-policy.json](lambda-role-policy.json)) |

**Riesgo de los permisos amplios.** Con `Allow * *`, quien obtenga el certificado y la clave de la ESP32 puede publicar en cualquier tema y modificar el Shadow de **cualquier** Thing de la cuenta, no solo el suyo. Con la política mínima, ese certificado solo puede operar sobre `monoambiente-739264`. Del mismo modo, `AmazonDynamoDBFullAccess` permite que un error en la Lambda borre cualquier tabla de la cuenta; el rol mínimo solo toca `user_thing` y únicamente con las tres operaciones que usa el código.

**Por qué la Lambda necesita `iot:DescribeThing`.** Es la validación de RF9: antes de guardar una vinculación, comprueba que `monoambiente-<código>` exista como Thing ([lambda_function.py](../lambda/lambda_function.py), `ThingGateway.exists()`).

## Datos de la configuración

| Elemento | Valor |
|---|---|
| Región | `us-east-2` (Ohio) para IoT Core, Lambda y DynamoDB |
| Things | `monoambiente-739264` (con la ESP32) y `monoambiente-518306` (sin hardware, para probar varios usuarios), ambos con Shadow clásico |
| Certificado | Uno por dispositivo, activo, asociado a `monoambiente-739264` y a `monoambiente-policy`; en la ESP32 está en `include/secrets.h`, que git ignora |
| Lambda | `monoambiente-skill`, Python 3.14, handler `lambda_function.lambda_handler`, timeout 7 s; variables `IOT_ENDPOINT`, `IOT_REGION`, `TABLE_NAME` |
| Disparador | Alexa Skills Kit, con verificación del Skill ID |
| Skill | `monoambiente inteligente`, Spanish (US), endpoint = ARN de la Lambda |
