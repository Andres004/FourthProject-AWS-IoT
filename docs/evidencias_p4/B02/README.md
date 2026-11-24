# B02 — Firmwares con transporte serie (`*_local_test`)

- Fecha y hora: 24/11/2026, 06:15 (Bolivia) / 10:15 UTC
- Responsable: Dabner
- Commit del firmware: `435c9fb`
- Requisitos: RF1–RF3, RF12–RF14, RNF4, contrato V1–V3
- Herramienta: [serial_check.py](../../../tools/serial_check.py)

## Placa 2 (luces y entrada) — `lights_local_test`

- Archivos: [B02_lights_salida.txt](B02_lights_salida.txt) (salida del script), [B02_lights_ESP32.log](B02_lights_ESP32.log) (log completo de la placa; las líneas `# TX` son lo que envió el script)
- Comando: `python tools/serial_check.py --board lights --port COM5 --log docs/evidencias_p4/B02/B02_lights_ESP32.log`

| Caso | Requisito | Qué comprueba | Resultado |
|---|---|---|---|
| L01 | RF2, V1 | Primer reporte `event=boot`, `origin=boot`, `seq=1`, con todos los atributos | PASS |
| L02 | RF2 | Las 5 `light_*` en `on`/`off` y `presence=false` al arrancar | PASS |
| L03–L07 | RF3, RF12 | Cada zona: `LIGHT_APPLIED`, reporte `light_changed` con `origin=voice`, `cmd_origin` borrado y `light_*` conservada en `desired` | PASS 5/5 |
| L08 | RF3 | Luz ya encendida: no cambia y se reporta para borrar el `delta` | PASS |
| L09 | RF3, RNF4 | "Todas apagadas" en un `delta`: 5 `LIGHT_APPLIED` y **un** reporte | PASS |
| L10–L12 | RF12 | `"ON"`, `1`, `"half"`: `INVALID_VALUE`, sin cambios | PASS 3/3 |
| L90 | RF12 | Versión repetida: `STALE_IGNORED` | PASS |
| L91–L93 | RF12 | JSON cortado, sin `state`, línea de 552 caracteres: `JSON_ERROR` | PASS 3/3 |
| L94 | V2 | 8 reportes con `seq` 1..8 sin huecos | PASS |
| L95 | RNF4, V3 | Separación mínima 999 ms; reporte más grande 243 bytes (< 1024) | PASS |
| L96 | RF2, RNF4 | Heartbeat 59 952 ms después del último reporte (60 000 ± 1500) | PASS |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Casos | 19/19 | todos | PASS |
| Separación mínima entre reportes | 999 ms | ≥ 1000 ms (tolerancia de 5 ms del registro) | PASS |
| Intervalo del heartbeat | 59 952 ms | 60 000 ± 1500 ms | PASS |
| Tamaño máximo del reporte | 243 bytes | < 1024 bytes | PASS |
| Calentamiento del PIR (`PIR_READY`) | 30 028 ms | ≥ 30 000 ms | PASS |

**Nota sobre los 999 ms.** El firmware espera `MIN_REPORT_INTERVAL_MS = 1000` entre publicaciones medidas con `millis()`. El script mide entre las líneas `LOCAL_REPORT`, que se imprimen después de armar el JSON; la diferencia de 1 ms es el tiempo de impresión del reporte anterior, no un reporte adelantado.

**Nota sobre el WiFi.** En `local_test` la placa intenta conectarse al WiFi de la plantilla (`WIFI_CONNECTING` aparece 7 veces) sin consecuencias: el Shadow es el puerto serie. El log no contiene credenciales ni el endpoint.

## Placa 1 (ventilación) — `vent_local_test`

- Fecha y hora: 24/11/2026, 06:35 (Bolivia) / 10:35 UTC; mismo commit `435c9fb`
- Archivos: [B02_vent_salida.txt](B02_vent_salida.txt), [B02_vent_ESP32.log](B02_vent_ESP32.log), [B02_vent_video.mp4](B02_vent_video.mp4) (servo y LED de gas durante la corrida)
- Comando: `python tools/serial_check.py --board vent --port COM7 --log docs/evidencias_p4/B02/B02_vent_ESP32.log`
- El gas se simula con `sim_gas_pct` (solo existe en `vent_local_test`): así se prueban las dos fronteras de la histéresis sin humo. La prueba usa umbrales de prueba 30 / 20 y al final deja la placa en `auto` con los calibrados 15 / 8.

| Caso | Requisito | Qué comprueba | Resultado |
|---|---|---|---|
| V01 | RF2, V1 | Primer reporte `event=boot`, `seq=1`, con los 13 atributos de la placa | PASS |
| V02 | E2 | Durante el calentamiento: `warming_up=true`, `gas_alarm=false` | PASS |
| V03 | E2, RF14 | `auto` y umbrales 30/20 aplicados; gas 5 %: fin del calentamiento, sin alarma, ventana cerrada | PASS |
| V04 | E1 | Gas 29 % (debajo del umbral alto): sin alarma | PASS |
| V05 | E1, RF12 | Gas 30 % (= alto): `GAS_ALARM_ON` → `ACTUATOR_DONE` en **411 ms**; reportes `gas_alarm_on` y `window_changed` con `origin=edge` | PASS |
| V06 | E1 | Gas 21 % (dentro de la banda): la alarma sigue | PASS |
| V07 | E1 | Gas 20 % (= bajo): fin de la alarma, la ventana se cierra (`origin=edge`) | PASS |
| V08 | §2.6 | `window=open` en `auto`: `COMMAND_REJECTED reason=auto_mode`, sin movimiento, `desired.window=null` | PASS |
| V09 | RF14 | `mode=manual` por voz: `MODE_APPLIED`, `mode_changed`, `desired.cmd_origin=null` | PASS |
| V10–V11 | RF3, RF12 | En `manual`, abrir y cerrar por voz: 400 ms cada movimiento, `origin=voice`, `desired.window=null` | PASS 2/2 |
| V12 | §2.5 | En `manual` con gas 40 %: alarma reportada y la ventana no se mueve sola | PASS |
| V13 | §2.6 | En `manual` con alarma, "cerrar": `COMMAND_REJECTED reason=gas_alarm` | PASS |
| V14 | C1, E1 | La Nube pone `auto` con gas alto: `mode_changed origin=cloud` y después `window_changed origin=edge`, **en dos reportes** (cola de eventos, defecto D-01) | PASS |
| V15 | RF14, E3 | Umbrales 40/25: `THRESHOLDS_APPLIED` y `thresholds_changed` | PASS |
| V16–V19 | RF14 | Bajo = alto, alto = 100, bajo = 0, alto = `"abc"`: `COMMAND_REJECTED invalid_thresholds` | PASS 4/4 |
| V20–V21 | RF12 | `mode=turbo`, `window=half`: `INVALID_VALUE` | PASS 2/2 |
| V22 | E3 | Tras un reinicio: `SETTINGS_LOADED mode=manual gas_high_pct=40 gas_low_pct=25` y reporte de arranque con esos valores | PASS |
| V90–V93 | RF12 | Versión repetida, JSON cortado, sin `state`, línea demasiado larga | PASS 4/4 |
| V94 | V2 | `seq` 1..4 sin huecos después del reinicio | PASS |
| V95 | RNF4, V3 | Separación mínima 999 ms; reporte más grande 275 bytes | PASS |
| V96 | RF2, RNF4 | Heartbeat 60 000 ms después del último reporte | PASS |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Casos | 29/29 | todos | PASS |
| Respuesta Edge con gas simulado (`GAS_ALARM_ON` → `ACTUATOR_DONE`) | 411 ms (líneas 50 → 55 del log) | ≤ 1000 ms | PASS |
| Duración del movimiento del servo | 400 ms (V10, V11) | 400 ± 60 ms | PASS |
| Intervalo del heartbeat | 60 000 ms | 60 000 ± 1500 ms | PASS |
| Tamaño máximo del reporte | 275 bytes | < 1024 bytes | PASS |

**Lectura con el sensor real antes de la prueba:** `GAS_SAMPLE pin_mv=142 ao_mv=237 gas_pct=4.4 n=20`, el mismo piso de aire limpio de la calibración (A10).

**Estado en que queda la placa:** `auto`, umbrales 15 / 8 guardados en la NVS y gas simulado en 2 %. Para usar el sensor real (A05) hay que reiniciar la placa o enviar `{"state":{"sim_gas_pct":-1}}`.
