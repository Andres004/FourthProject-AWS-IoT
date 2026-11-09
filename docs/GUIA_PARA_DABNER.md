# Guía para Dabner: conexión con AWS, Lambda y Alexa

**Práctica 3 SIS-234. Entrega: martes 10/11/2026, 17:45.**

Repositorio: <https://github.com/Andres004/ThirdProject-AWS-IoT>

El firmware del ESP32 ya está hecho y probado **en local** con servo, PIR y WiFi. **Todavía no se probó contra AWS**, porque faltan los datos de la sección 3.

## 1. Qué cambió respecto a la guía anterior

| Tema | Antes | Ahora |
|---|---|---|
| Caso de uso | Persiana, comedero o tanque | **Puerta de un monoambiente inteligente** |
| Sensor | Luz o HC-SR04 | **PIR AM312**, detecta presencia en la entrada |
| Actuador | Servo | Servo SG90 que abre y cierra la puerta |
| Atributo del actuador | `blind` o `gate` | **`door`** |
| Valor del sensor | `light_lux` o `level_pct` | **`presence`** (booleano) |
| Código de vinculación | `reported.link_code` | **Forma parte del nombre del Thing** y no va en el Shadow |
| Nombre del Thing | `smart-object` o similar | **`monoambiente-<6 dígitos>`** |

Ya no usamos el HC-SR04, así que no hay que justificar el ultrasónico. Queda como posible extensión en las recomendaciones del informe.

## 2. Contrato del Shadow

**No se cambia sin avisar**, porque el ESP32 y la Lambda dependen de él.

```json
{
  "state": {
    "desired":  { "door": "closed" },
    "reported": { "door": "closed", "servo_angle": 0, "presence": false }
  }
}
```

| Atributo | Sección | Tipo | Valores | Quién lo escribe |
|---|---|---|---|---|
| `door` | `desired` | string | `"open"` o `"closed"`, en minúsculas | Lambda |
| `door` | `reported` | string | `"open"` o `"closed"` | ESP32, cuando termina de mover |
| `servo_angle` | `reported` | entero | Ángulo real calibrado (por ahora 0 y 90) | ESP32 |
| `presence` | `reported` | booleano | `true` o `false` | ESP32 |

- **La Lambda nunca escribe en `reported`.**
- `presence` sigue en `true` durante 10 s después del último movimiento.
- Durante los primeros 30 s tras encender, el PIR se está estabilizando y `presence` queda en `false`.
- El ESP32 reporta al cambiar de estado, con mínimo 1 s entre mensajes, y además cada 60 s.

## 3. Lo que Andrés necesita para terminar el firmware

- [ ] **Thing principal** `monoambiente-<código>`, con **Shadow clásico**.
- [ ] **Segundo Thing** con otro código, sin hardware, para probar varios usuarios.
- [ ] El **código** tiene 6 dígitos y no empieza en 0, por ejemplo `monoambiente-482731`. No uses ese ejemplo: elige números difíciles de adivinar.
- [ ] **Shadow inicial** en ambos Things:

  ```json
  {"state":{"desired":{"door":"closed"},"reported":{"door":"closed"}}}
  ```

- [ ] **Endpoint** `iot:Data-ATS`, en AWS IoT → Conectarse → Configuraciones de dominio.
- [ ] Confirmar que la **región** es `us-east-2`. IoT Core, Lambda y DynamoDB deben estar en la misma.
- [ ] **Tres archivos por canal privado, nunca por el repositorio:** `AmazonRootCA1.pem`, `...-certificate.pem.crt` y `...-private.pem.key`.
- [ ] **Política de IoT** asociada al certificado, y su JSON para el informe.
- [ ] **Usuario de GitHub** para agregarte al repositorio.

Los nombres de los Things no se pueden cambiar. Si ya creaste uno con otro nombre, hay que crear uno nuevo. Sin Shadow inicial, `get_thing_shadow` devuelve `ResourceNotFoundException`.

## 4. Vinculación

1. El usuario dice: "vincula mi casa con el código cuatro ocho dos siete tres uno".
2. El slot `code` es de tipo `AMAZON.NUMBER`.
3. La Lambda valida que tenga 6 dígitos y arma `thing_name = "monoambiente-" + code`.
4. Llama a `describe_thing` para comprobar que exista (RF9).
5. Si existe, guarda `userId → thingName` en DynamoDB. Volver a vincular reemplaza el registro, y eso cubre "cambiar la vinculación".

El ESP32 imprime su código por Serial al arrancar: `LINK_CODE 482731`.

## 5. DynamoDB

| Campo | Valor |
|---|---|
| Clave de partición | `userId` (String) |
| Clave de ordenamiento | Ninguna |
| Otros atributos | `thingName`, `fechaVinculacion` |

## 6. Lambda

Lee la configuración desde variables de entorno: `IOT_ENDPOINT`, `IOT_REGION` y el nombre de la tabla. **No pongas access keys en el código.**

```python
import json
import boto3

iot = boto3.client("iot", region_name=IOT_REGION)
iot_data = boto3.client(
    "iot-data",
    region_name=IOT_REGION,
    endpoint_url="https://" + IOT_ENDPOINT,
)

# RF9: validate the Thing before linking.
# Raises iot.exceptions.ResourceNotFoundException if it does not exist.
iot.describe_thing(thingName=thing_name)

# RF4 and RF6: read the current state.
response = iot_data.get_thing_shadow(thingName=thing_name)
reported = json.loads(response["payload"].read())["state"].get("reported", {})

# RF5: send a command.
iot_data.update_thing_shadow(
    thingName=thing_name,
    payload=json.dumps({"state": {"desired": {"door": "open"}}}),
)
```

```python
# RF8: Alexa user identifier.
user_id = handler_input.request_envelope.context.system.user.user_id
```

Casos que debe manejar:

- **Usuario sin vincular:** indicarle cómo vincular su casa (RF8).
- **Código inválido o Thing inexistente:** responder en español y no guardar nada.
- **Falta un atributo en `reported`:** decir que todavía no hay datos, sin que falle la Lambda.
- **Después de un comando:** decir "enviando la orden" o "abriendo la puerta". El estado real se confirma en `reported`, que cambia después.
- **Consulta de la puerta o del sensor:** leer siempre `reported`, nunca `desired`.
- **ESP32 apagado:** el `desired` queda pendiente y el ESP32 lo aplica al reconectarse.

**Permisos del rol.** En clase se usaron `AWSIoTFullAccess` y `AmazonDynamoDBFullAccess`. El informe debe indicar también los mínimos:

- `iot:GetThingShadow`
- `iot:UpdateThingShadow`
- `iot:DescribeThing`
- `dynamodb:GetItem`
- `dynamodb:PutItem`
- `dynamodb:DeleteItem`

## 7. Skill de Alexa

Crear en **Spanish (US)**. El nombre de invocación debe tener al menos dos palabras; sugerencia: `monoambiente inteligente`. Después de cada cambio en los intents, hay que pulsar **Build skill**.

| Intent | RF | Frases sugeridas | Slot |
|---|---|---|---|
| `LinkThing` | RF7, RF9 | "vincula mi casa con el código {code}" | `code`: `AMAZON.NUMBER` |
| `UnlinkThing` | RF9 | "desvincula mi casa" | |
| `GetPresence` | RF4 | "hay alguien en la puerta", "detectas a alguien en la entrada" | |
| `OpenDoor` | RF5 | "abre la puerta" | |
| `CloseDoor` | RF5 | "cierra la puerta" | |
| `GetDoorState` | RF6 | "la puerta está abierta", "cuál es el estado de la puerta" | |

Además, los intents integrados de ayuda, cancelar y detener.

## 8. Cómo probar sin esperar al ESP32

Publica en `$aws/things/<thing>/shadow/update` desde el MQTT test client.

Para simular a la Lambda:

```json
{"state":{"desired":{"door":"open"}}}
```

Para simular al ESP32:

```json
{"state":{"reported":{"door":"open","servo_angle":90,"presence":true}}}
```

Prueba la Lambda con eventos de prueba antes de conectar Alexa. Como el simulador usa un solo `userId`, para probar varios usuarios usa eventos con `userId` distintos, o una segunda cuenta de Amazon, cada uno vinculado a un Thing diferente.

## 9. Pruebas conjuntas

1. Publicar `desired.door = "open"`: el servo se mueve, `reported.door` cambia y desaparece el `delta`.
2. Reconexión: apagar el WiFi, cambiar `desired`, volver a conectar y comprobar que la puerta aplique el cambio sola.
3. De punta a punta: decir el comando en el simulador y medir hasta el movimiento. Meta: 3 s o menos.
4. Cubrir RF4 a RF9 con las frases de la skill y guardar capturas de Skill I/O.

## 10. Qué debe quedar en el repositorio

Cada uno debe hacer **commits con su propia cuenta de GitHub**.

```text
lambda/lambda_function.py
lambda/requirements.txt
alexa/interaction-model.es-US.json
aws/iot-policy.json
aws/lambda-role-policy.json
aws/dynamodb-table.md
```

**Nunca subir** certificados, claves privadas, contraseñas de WiFi ni access keys.

## 11. Para acordar hoy

- [ ] Quién hace la Lambda y DynamoDB (Fase 3).
- [ ] Quién hace la skill (Fase 4).
- [ ] A qué hora probamos juntos el sistema completo.
- [ ] Cómo nos repartimos el informe y los diagramas.
