# Mockups de reportes (RF15)

Cuatro reportes que se pueden construir con el modelo de datos de `smartloft-data` ([aws/dynamodb-tables.md](../../aws/dynamodb-tables.md)). Cada elemento indica, en el recuadro punteado, la consulta que lo alimenta (patrones P1–P4). **Los números son ilustrativos**: los reportes no se implementan en esta práctica.

| Mockup | Decisión que apoya | Datos |
|---|---|---|
| [01_seguridad_gas.png](01_seguridad_gas.png) | ¿Hay una fuga recurrente? ¿Revisar la instalación? ¿Los umbrales están bien? | P2 `gas_alarm_on/off`, `window_changed`, `mode_changed`; P1 pico de `gasPct` |
| [02_uso_luces.png](02_uso_luces.png) | Qué zona queda encendida sin uso (ahorro) | P2 `light_changed`, sumando intervalos on → off |
| [03_actividad_entrada.png](03_actividad_entrada.png) | Horarios de ocupación; movimiento cuando la casa debería estar vacía | P2 `presence_detected`; P3 última detección |
| [04_modo_ventilacion.png](04_modo_ventilacion.png) | ¿La ventilación queda en manual demasiado tiempo? ¿Cuántas veces intervino C1? | P2 `mode_changed` con su `origin` |

Las imágenes se generan desde los `.html` de esta carpeta (HTML y SVG sin librerías externas), con Edge en modo headless:

```powershell
& "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --headless=new --hide-scrollbars --window-size=1200,900 --screenshot="$PWD\01_seguridad_gas.png" "file:///$PWD/01_seguridad_gas.html"
```
