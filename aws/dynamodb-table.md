# Tabla de vinculaciones `user_thing`

Región `us-east-2` (Ohio), capacidad por defecto de la consola (**Default settings**).

| Propiedad | Valor |
|---|---|
| Nombre | `user_thing` |
| Clave de partición | `userId` (String): el `context.System.user.userId` que envía Alexa |
| Clave de ordenamiento | ninguna: cada usuario tiene como máximo un Thing vinculado |
| Atributos (no declarados, los escribe la Lambda) | `thingName` (String), `fechaVinculacion` (String, ISO 8601 en UTC) |

Ejemplo de ítem (capturado en la prueba [A01](../docs/evidencias/A01/README.md)):

```json
{
  "userId": "amzn1.ask.account.AMASSKDEAA…",
  "thingName": "monoambiente-518306",
  "fechaVinculacion": "2026-11-10T02:39:04.497180+00:00"
}
```

| Operación | Cuándo | Método en la Lambda |
|---|---|---|
| `GetItem` | En cada solicitud que necesita el Thing del usuario (RF8) | `LinkRepository.find_thing()` |
| `PutItem` | Al vincular o cambiar la vinculación; reemplaza el ítem anterior (RF7, RF9) | `LinkRepository.save()` |
| `DeleteItem` | Al desvincular (RF9) | `LinkRepository.delete()` |

La Lambda nunca hace `Scan` ni `Query`: siempre accede por clave, así que el costo por solicitud es constante.
