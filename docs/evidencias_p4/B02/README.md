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

⟨Pendiente de correr.⟩
