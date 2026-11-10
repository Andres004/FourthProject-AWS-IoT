# Evidencia A07: Caída de WiFi con orden pendiente

Prueba A07 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09–10/11/2026, 23:53–00:08 (hora de Bolivia; 03:53–04:08 UTC del 10/11). La red de la ESP32 es el hotspot de un iPhone; la PC con el simulador estaba en otra red.

| Archivo | Qué muestra |
|---|---|
| A07_01_intento1_aviso_2min.png | Intento 1: con la ESP32 sin red, "hay alguien en la puerta" → "…Ojo: tu casa no se reporta desde hace 2 minutos…" |
| A07_02_intento1_comando_tras_reconectar.png | Intento 1: "abre la puerta" enviado justo después de volver a encender el hotspot → confirmado (no quedó pendiente) |
| A07_03_aviso_3min.png | Intento 2: aviso de RF11 con 3 minutos sin reportes |
| A07_04_orden_encolada.png | Intento 2: "cierra la puerta" → "Envié la orden, pero tu casa está desconectada. Se aplicará apenas vuelva a conectarse." |
| A07_05_shadow_delta_closed.png | Shadow con la orden pendiente: `desired.door = "closed"`, `reported.door = "open"`, `delta.door = "closed"` |
| A07_ESP32.log, A07_analisis.txt | Log y análisis de los intentos 1 y 2 (firmware anterior a la corrección) |
| A07_video_reconexion_aplica_orden.mp4 | Intento 3: se enciende el hotspot y la puerta se abre sola |
| ../A08/A08_01_intento1_sin_confirmacion.png (burbuja superior) | Intento 3: "abre la puerta" con la ESP32 sin red desde hacía menos de 150 s → "Envié la orden para abrir la puerta, pero todavía no recibo la confirmación…" (camino de RF10, no de RF11) |
| A07_ESP32_tras_correccion.log, A07_analisis_tras_correccion.txt | Log y análisis del intento 3, con el firmware corregido |

## Resultados

| Intento | Orden pendiente | WiFi: reintentos | `WIFI_CONNECTED` → `MQTT_CONNECTED` | `WIFI_CONNECTED` → puerta movida | Veredicto |
|---|---|---|---|---|---|
| 1 | ninguna (el comando se dio con la red ya de vuelta) | 6 intervalos, todos de 10 000 ms | 4117 ms | 4846 ms (orden dada en ese momento) | INFO |
| 2 | `closed`, escrita a las 04:00:57 con la casa desconectada | 10 intervalos de 9999–10 000 ms | 3203 ms | **3848 ms** | PASS (RNF5) |
| 3 | `open`, escrita a las 04:04:33 con la casa desconectada | 11 intervalos de 10 000 ms | 2088 ms | **3297 ms** | PASS (RNF5) |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Aviso de casa desconectada (> 150 s) | "…desde hace 2 minutos" y "…desde hace 3 minutos" | aviso presente | PASS (RF11) |
| Comando con la casa desconectada | `queued_offline`, sin esperar los 3 s de confirmación | aviso de encolado | PASS (RF11) |
| Reintento de WiFi | 10 000 ms en 27 intervalos | 10 000 ± 500 ms | PASS (RNF5) |
| Orden pendiente aplicada desde `WIFI_CONNECTED` | 3848 y 3297 ms | ≤ 10 000 ms | PASS (RNF5) |
| Reinicios durante los cortes | 0 | 0 | PASS |

En el intento 2, AWS entregó el `delta` pendiente apenas se suscribió la ESP32, antes de la respuesta a `/get`. En el intento 3 llegó primero la respuesta a `/get` (versión 577) y la puerta se movió con ella. Los dos caminos funcionan: el número de versión evita aplicar dos veces la misma orden.

Con el hotspot del iPhone apagado, primero se cae MQTT (`MQTT_LOST`, el teléfono deja de dar internet) y entre 35 y 120 s después se cae el WiFi (`WIFI_LOST`). Durante ese tramo, la ESP32 reintenta MQTT cada 5 s.

## Defecto encontrado y corregido

En el intento 2, las líneas `HEALTH` registraron `max_loop_ms=7010` y `7032`. Con el WiFi asociado pero sin internet, cada `MQTT_CONNECTING` esperaba unos 7 s a que fallara la consulta DNS (`hostByName(): DNS Failed`). Como el intervalo de 5 s entre reintentos se medía desde el **inicio** del intento, el siguiente empezaba de inmediato: 03:57:55 → 03:58:02 → 03:58:09… Durante casi 2 minutos, `loop()` pasó la mayor parte del tiempo bloqueado, sin leer el PIR ni actualizar el LED. El watchdog de 30 s no llegó a actuar.

**Corrección:** [ShadowClient::connect()](../../../src/ShadowClient.cpp) toma la hora después de que el intento termina, así entre dos intentos siempre quedan 5 s libres para el resto del `loop()`.

**Verificación (intento 3):** los `MQTT_CONNECTING` quedaron separados por 5 000–5 016 ms medidos desde el fin del intento anterior, y las líneas `HEALTH` durante el corte marcaron `max_loop_ms` de 23 y 17 ms. En este intento, el DNS falló en unos 16 ms en lugar de 7 s, así que el peor caso no se repitió exactamente. La corrección garantiza los 5 s libres en cualquier caso. El `max_loop_ms=2111` posterior corresponde a la conexión TLS que tuvo éxito: es el bloqueo que sigue existiendo, porque PubSubClient conecta de forma sincrónica (ver recomendaciones).
