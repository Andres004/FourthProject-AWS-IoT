# Guía AWS IoT Core + Alexa para Andrés (consola en inglés)

**Práctica 3 SIS-234: puerta inteligente con servo y PIR.**
Entrega: martes 10/11/2026, 17:45.

Los nombres de botones están en inglés, tal como salen en tu consola. Si AWS cambió alguna etiqueta, busca la más parecida.

## 0. Valores que vas a usar

Copia estos valores exactamente como están:

| Dato | Valor |
|---|---|
| Región | `US East (Ohio)` / `us-east-2` |
| Thing principal | `monoambiente-739264` |
| Código para Alexa | `739264` |
| Thing de prueba | `monoambiente-518306` |
| Código de prueba | `518306` |
| Política | `monoambiente-policy` |
| Tabla | `user_thing` |
| Función Lambda | `monoambiente-skill` |
| Invocación | `monoambiente inteligente` |

`include/config.h` ya tiene el código `739264`; no tienes que cambiarlo.

Esta guía se hace en tu cuenta de AWS. Antes de cada servicio, mira arriba a la derecha y confirma que diga **United States (Ohio)**. Si dice otra región, haz clic ahí y elige **US East (Ohio) us-east-2**.

Orden de trabajo: IoT Core → ESP32 → DynamoDB → skill → Lambda → permisos → disparador → endpoint → simulador.

## 1. AWS IoT Core

### 1.1 Crear la política

1. Abre **AWS IoT** → **Security** → **Policies** → **Create policy**.
2. **Policy name:** `monoambiente-policy`.
3. En **Policy document**, modo **Builder**: **Policy effect** `Allow`, **Policy action** `*`, **Policy resource** `*`.
4. Pulsa **Create**.

El enunciado acepta permisos amplios si el informe los justifica y explica los mínimos (sección 9).

### 1.2 Crear el Thing principal

1. **Manage** → **All devices** → **Things** → **Create things**.
2. Elige **Create single thing** → **Next**.
3. **Thing name:** `monoambiente-739264`.
4. En **Device Shadow**, elige **Unnamed shadow (classic)**.
5. Abre **Edit shadow statement** y pega exactamente:

   ```json
   {"state":{"desired":{"door":"closed"},"reported":{"door":"closed"}}}
   ```

6. **Next** → **Auto-generate a new certificate (recommended)** → **Next**.
7. Marca `monoambiente-policy` y pulsa **Create thing**.
8. En **Download certificates and keys**, descarga:
   - **Device certificate** (`...-certificate.pem.crt`)
   - **Private key file** (`...-private.pem.key`)
   - **Amazon Root CA 1** (RSA 2048)
9. Mueve los tres archivos a una carpeta nueva en tu Escritorio llamada `certificados-aws` y pulsa **Done**. No los pongas dentro del proyecto.

**La clave privada solo se puede descargar en ese momento.**

### 1.3 Crear el Thing de prueba

Repite el paso 1.2 completo, pero en **Thing name** escribe `monoambiente-518306`. Este Thing no tendrá hardware; sirve para demostrar que la skill atiende a varios usuarios. Descarga sus certificados en otra carpeta del Escritorio llamada `certificados-prueba`; no se usarán en el ESP32.

### 1.4 Copiar el endpoint

**Connect** → **Domain configurations** → fila `iot:Data-ATS` → copia el **Domain name** completo y guárdalo en un Bloc de notas. Lo usarás en las secciones 2 y 6. Termina en `-ats.iot.us-east-2.amazonaws.com`.

### 1.5 Probar el Shadow desde la consola

1. **Test** → **MQTT test client**.
2. En **Subscribe to a topic**, suscríbete a:

   ```text
   $aws/things/monoambiente-739264/shadow/#
   ```

3. En **Publish to a topic**, usa `$aws/things/monoambiente-739264/shadow/update` y publica:

   ```json
   {"state":{"desired":{"door":"open"}}}
   ```

4. Debe llegar un mensaje en `/update/delta`.
5. Para cerrar la prueba, publica:

   ```json
   {"state":{"desired":{"door":"closed"}}}
   ```

## 2. Conectar el ESP32

1. En VS Code abre `include/secrets.h`. No cambies `WIFI_SSID` ni `WIFI_PASSWORD`, porque ya pusiste tu hotspot.
2. En la línea `AWS_IOT_ENDPOINT`, borra `xxxxxxxx-ats.iot.us-east-2.amazonaws.com` y pega tu **Domain name**. Las comillas deben quedar.
3. En tu carpeta `certificados-aws`, abre `AmazonRootCA1.pem` con Bloc de notas y copia todo con `Ctrl+A` y `Ctrl+C`.
4. En `secrets.h`, en el bloque `ROOT_CA`, selecciona desde `-----BEGIN CERTIFICATE-----` hasta `-----END CERTIFICATE-----`, incluidas esas dos líneas, y pega con `Ctrl+V`.
5. Haz lo mismo con el archivo que termina en `-certificate.pem.crt`, en el bloque `DEVICE_CERTIFICATE`.
6. Haz lo mismo con el archivo que termina en `-private.pem.key`, en el bloque `DEVICE_PRIVATE_KEY`. Selecciona desde `-----BEGIN RSA PRIVATE KEY-----` hasta `-----END RSA PRIVATE KEY-----`.
7. Guarda con `Ctrl+S`. No deben quedar textos que empiecen con `PASTE_`.
8. Con la ESP32 conectada, ejecuta en la terminal de VS Code:

   ```bash
   pio run -e esp32doit-devkit-v1 -t upload -t monitor --upload-port COM3 --monitor-port COM3
   ```

9. Debes ver, en este orden: `WIFI_CONNECTED`, `MQTT_CONNECTED`, `GET_TX`, `GET_RX` y `REPORT_TX`.

| Log | Revisa |
|---|---|
| `MQTT_CONNECT_FAILED` | Endpoint, internet, certificados pegados incompletos, o certificado sin activar o sin política |
| Conecta y se cae enseguida | Otro cliente está usando el mismo Client ID, o la política |
| `GET_REJECTED` con 404 | El Thing no tiene Shadow; el primer reporte lo crea |

### Pruebas de esta fase

**Comando:** publica `{"state":{"desired":{"door":"open"}}}` en `/update`. El servo debe moverse, el log debe mostrar `DELTA_RX` y `ACTUATOR_DONE`, y en **Manage → Things → tu Thing → Device Shadows → Classic Shadow** debe verse `reported.door = "open"` sin `delta`.

**Reconexión:**
1. Apaga el hotspot.
2. Publica `{"state":{"desired":{"door":"closed"}}}` desde la consola.
3. Enciende el hotspot.
4. Sin hacer nada más, la puerta debe cerrarse y el log debe mostrar `MQTT_CONNECTED`, `GET_RX` y `ACTUATOR_DONE`.

Guarda capturas y logs: esta prueba se evalúa en la demo.

## 3. DynamoDB

1. Abre **DynamoDB** → **Tables** → **Create table**.
2. **Table name:** `user_thing`.
3. **Partition key:** `userId`, tipo **String**.
4. **Sort key:** vacío.
5. Deja **Default settings** y pulsa **Create table**.
6. Espera a que el estado sea **Active**.

`thingName` y `fechaVinculacion` no se declaran; se crean cuando la Lambda guarda un registro.

## 4. Crear la skill

Hazlo antes de la Lambda porque el disparador necesita el **Skill ID**.

1. Entra a <https://developer.amazon.com/alexa/console/ask> → **Create Skill**.
2. **Skill name:** `monoambiente inteligente`. **Primary locale:** `Spanish (US)`.
3. **Type of experience:** `Other`. **Model:** `Custom`. **Hosting service:** `Alexa-hosted (Python)`. **Hosting region:** `US East (N. Virginia)`.
4. **Template:** `Start from Scratch` → **Review** → **Create Skill**. Tarda cerca de un minuto.
5. Ve a **Build** → **Interaction Model** → **JSON Editor**, reemplaza todo por este modelo y pulsa **Save**:

```json
{
  "interactionModel": {
    "languageModel": {
      "invocationName": "monoambiente inteligente",
      "intents": [
        { "name": "AMAZON.CancelIntent", "samples": [] },
        { "name": "AMAZON.HelpIntent", "samples": [] },
        { "name": "AMAZON.StopIntent", "samples": [] },
        { "name": "AMAZON.NavigateHomeIntent", "samples": [] },
        { "name": "AMAZON.FallbackIntent", "samples": [] },
        {
          "name": "LinkThing",
          "slots": [{ "name": "code", "type": "AMAZON.NUMBER" }],
          "samples": [
            "vincula mi casa con el código {code}",
            "vincular mi casa con el código {code}",
            "cambia mi casa al código {code}",
            "mi código es {code}"
          ]
        },
        {
          "name": "UnlinkThing",
          "slots": [],
          "samples": ["desvincula mi casa", "elimina la vinculación", "desvincular mi casa"]
        },
        {
          "name": "GetPresence",
          "slots": [],
          "samples": [
            "hay alguien en la puerta",
            "hay alguien en la entrada",
            "detectas a alguien en la entrada",
            "hay presencia en la puerta"
          ]
        },
        {
          "name": "OpenDoor",
          "slots": [],
          "samples": ["abre la puerta", "abrir la puerta", "abre la puerta principal"]
        },
        {
          "name": "CloseDoor",
          "slots": [],
          "samples": ["cierra la puerta", "cerrar la puerta", "cierra la puerta principal"]
        },
        {
          "name": "GetDoorState",
          "slots": [],
          "samples": [
            "la puerta está abierta",
            "la puerta está cerrada",
            "cuál es el estado de la puerta",
            "cómo está la puerta"
          ]
        }
      ],
      "types": []
    }
  }
}
```

6. Pulsa **Build skill** y espera **Build successful**.
7. Ve a **Build** → **Endpoint** y copia **Your Skill ID**.

Cada vez que cambies intents o frases, vuelve a pulsar **Build skill**.

## 5. Código de la Lambda

El código ya está en tu proyecto: [lambda/lambda_function.py](../lambda/lambda_function.py) y [lambda/requirements.txt](../lambda/requirements.txt). No tienes que crear ni cambiar nada.

### Armar el paquete en Windows

En la terminal de VS Code, ejecuta estos tres comandos, uno por uno:

```bash
python -m pip install -r lambda/requirements.txt -t lambda/package
```

```bash
copy lambda\lambda_function.py lambda\package\
```

```bash
python -c "import shutil; shutil.make_archive('lambda/lambda_deployment', 'zip', 'lambda/package')"
```

Debe aparecer el archivo `lambda/lambda_deployment.zip`.

## 6. Crear la Lambda

1. Abre **Lambda** y confirma la región Ohio.
2. Pulsa **Create function** (en algunas consolas aparece como **Event Functions** → **Create event function**).
3. Elige **Author from scratch**.
4. **Function name:** `monoambiente-skill`. **Runtime:** `Python 3.14`. Si no aparece, elige el Python con el número más alto de la lista.
5. Pulsa crear y luego **Copy ARN**.
6. En la pestaña **Code**, elige **Upload from** → **.zip file** y sube `lambda_deployment.zip`.
7. Confirma que **Handler** sea `lambda_function.lambda_handler`.

**Variables:** **Configuration** → **Environment variables** → **Edit**.

| Key | Value |
|---|---|
| `IOT_ENDPOINT` | El **Domain name** que guardaste en la sección 1.4 |
| `IOT_REGION` | `us-east-2` |
| `TABLE_NAME` | `user_thing` |

**Tiempo máximo:** **Configuration** → **General configuration** → **Edit** → **Timeout**: `0` min `7` sec → **Save**.

**Permisos:**
1. **Configuration** → **Permissions** → abre el enlace del **Execution role**.
2. En IAM: **Permissions policies** → **Add permissions** → **Attach policies**.
3. Marca `AWSIoTFullAccess` y `AmazonDynamoDBFullAccess`.
4. Pulsa **Add permissions**.

**Disparador:**
1. En la Lambda, pulsa **Add trigger** y elige **Alexa**.
2. En **Skill ID verification**, deja **Enable (recommended)**.
3. Pega el **Skill ID** que copiaste en la sección 4 y pulsa **Add**.

**Endpoint de la skill:**
1. En Alexa, ve a **Build** → **Endpoint** → **AWS Lambda ARN**.
2. En **Default Region**, reemplaza el ARN por el de tu Lambda.
3. Pulsa **Save**.

### Probar la Lambda sin Alexa

En la pestaña **Test** de la Lambda, elige **Create new event**, pon como nombre `vincular1`, borra el JSON que aparece, pega este y pulsa **Test**:

```json
{
  "version": "1.0",
  "session": {
    "new": true,
    "sessionId": "test-session",
    "application": { "applicationId": "test-skill" },
    "user": { "userId": "test-user-1" }
  },
  "context": {
    "System": {
      "application": { "applicationId": "test-skill" },
      "user": { "userId": "test-user-1" },
      "apiEndpoint": "https://api.amazonalexa.com"
    }
  },
  "request": {
    "type": "IntentRequest",
    "requestId": "test-request",
    "timestamp": "2026-11-09T12:00:00Z",
    "locale": "es-US",
    "intent": {
      "name": "LinkThing",
      "confirmationStatus": "NONE",
      "slots": {
        "code": { "name": "code", "value": "739264", "confirmationStatus": "NONE" }
      }
    }
  }
}
```

Debe responder "Listo, tu casa quedó vinculada", y en **DynamoDB** → **Explore items** debe aparecer `test-user-1`. Para probar otro usuario, crea otro evento llamado `vincular2` con el mismo JSON, y cambia `test-user-1` por `test-user-2` en los dos lugares y `739264` por `518306`.

Si falla, revisa los logs en **CloudWatch** → **Log groups** → `/aws/lambda/monoambiente-skill`.

## 7. Probar en el simulador

Ve a la pestaña **Test**, elige **Development** y el idioma **Spanish (US)**. Marca **Skill I/O** para capturar evidencia.

| Frase | Resultado esperado | RF |
|---|---|---|
| "abre monoambiente inteligente" | Te pide vincular | RF8 |
| "abre la puerta" sin vincular | Te guía para vincular | RF8 |
| "vincula mi casa con el código 111111" | No encuentra la casa | RF9 |
| "vincula mi casa con el código 739264" | Vincula | RF7 |
| "abre la puerta" | El servo abre | RF5 |
| "la puerta está abierta" | Lee `reported` | RF6 |
| "hay alguien en la entrada" | Responde según el PIR | RF4 |
| "cierra la puerta" | El servo cierra | RF5 |
| "vincula mi casa con el código 518306" | Cambia la vinculación | RF9 |
| "desvincula mi casa" | Elimina la vinculación | RF9 |

Cierra y vuelve a abrir la skill después de vincular para demostrar que la vinculación persiste.

Si dice que hubo un problema, mira CloudWatch. Después de un comando, espera un momento antes de consultar el estado, porque `reported` cambia cuando el servo termina.

## 8. Mediciones para el informe

| Requisito | Cómo medirlo |
|---|---|
| Estabilidad | 10 min o más, con log guardado y sin `BOOT` nuevo |
| Exactitud del PIR | 20 pasadas y 20 periodos sin nadie: aciertos, falsos positivos y tiempo de detección |
| Tiempo de respuesta | Video desde el comando hasta el movimiento, 3 s o menos, con `DELTA_RX` y `ACTUATOR_DONE` como apoyo |
| Frecuencia de reporte | Evento inmediato con mínimo 1 s, heartbeat de 60 s, y su cálculo de mensajes |
| Reconexión | Prueba de la sección 2 |

## 9. Lo que debes exportar al repositorio

**Modelo de Alexa:** copia el contenido de **JSON Editor** en `alexa/interaction-model.es-US.json`.

**Permisos usados:** indica en el informe que se usó `Allow * *` en IoT y políticas administradas en el rol, y por qué.

**Política mínima de IoT.** Crea `aws/iot-policy.json` y pega esto tal cual; deja `<account-id>` escrito así para no publicar tu número de cuenta:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "iot:Connect",
      "Resource": "arn:aws:iot:us-east-2:<account-id>:client/monoambiente-739264"
    },
    {
      "Effect": "Allow",
      "Action": ["iot:Publish", "iot:Receive"],
      "Resource": "arn:aws:iot:us-east-2:<account-id>:topic/$aws/things/monoambiente-739264/shadow/*"
    },
    {
      "Effect": "Allow",
      "Action": "iot:Subscribe",
      "Resource": "arn:aws:iot:us-east-2:<account-id>:topicfilter/$aws/things/monoambiente-739264/shadow/*"
    }
  ]
}
```

**Permisos mínimos de la Lambda.** Crea `aws/lambda-role-policy.json` y pega esto tal cual:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["iot:GetThingShadow", "iot:UpdateThingShadow", "iot:DescribeThing"],
      "Resource": "arn:aws:iot:us-east-2:<account-id>:thing/monoambiente-*"
    },
    {
      "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:DeleteItem"],
      "Resource": "arn:aws:dynamodb:us-east-2:<account-id>:table/user_thing"
    }
  ]
}
```

**Tabla** (`aws/dynamodb-table.md`): nombre `user_thing`, clave de partición `userId` (String), atributos `thingName` y `fechaVinculacion`.

## 10. Seguridad

- **Nunca subas** `include/secrets.h`, `.pem`, `.crt`, `.key`, contraseñas ni access keys.
- Antes de cada `git push`, revisa `git status`.
- Configura una alerta de facturación en la cuenta, como recomienda el enunciado.
