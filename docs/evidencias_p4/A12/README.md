# A12 — Exactitud del PIR (presencia en la entrada)

- Fecha y hora: 24/11/2026, 07:08–07:32 (Bolivia) / 11:08–11:32 UTC
- Responsable: Dabner
- Commit del firmware: `435c9fb` (entorno `lights_local_test`; el PIR y su lógica son los mismos que en `lights`)
- Requisitos: RF1 (presencia), RNF2 (exactitud del sensor)
- Estímulo: la mano pasada frente al PIR AM312 a unos 20 cm, en un solo movimiento, y retirada hacia el costado. En la maqueta el PIR mira una entrada pequeña, por eso se usa la mano y no una persona caminando
- Archivos:
  - [A12_lights_ESP32.log](A12_lights_ESP32.log): log completo de la placa 2 (todas las fases)
  - [A12_video_1.mp4](A12_video_1.mp4): video de la primera tanda de pasadas
- Reloj: `millis()` de la placa 2. La placa se reinició a las 07:08:06 (t = 0)

## Fases y resultados

| Fase | Tramo del log (ms) | Hora (Bolivia) | Qué se hizo | Resultado | ¿Vale? |
|---|---|---|---|---|---|
| Calentamiento | 0 – 30 028 | 07:08:06 – 07:08:36 | Nada | `PIR_READY` a los 30 028 ms; 0 detecciones antes | Sí |
| Pasadas, 1.ª tanda | 30 028 – 303 000 | 07:08:36 – 07:13:13 | 15 pasadas cada ~15 s | 12 episodios: varias pasadas quedaron dentro del episodio anterior | No (ver abajo) |
| Sin nadie, 1.ª | 303 000 – 603 000 | 07:13:13 – 07:18:13 | 5 min | 1 detección a los 356 430 ms; en el video se ve movimiento frente al sensor | No: se repitió |
| **Sin nadie, repetida** | **696 000 – 996 000** | **07:19:40 – 07:24:40** | **5 min alejado del escritorio** | **0 detecciones** | **Sí** |
| **Pasadas, 2.ª tanda** | **996 000 – 1 430 124** | **07:24:40 – 07:31:59** | **16 pasadas cada ~25 s** | **16 episodios** | **Sí** |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Detecciones / pasadas (2.ª tanda) | 16 / 16 (100 %) | 100 % | PASS |
| Falsos positivos en 5 min sin nadie (repetida) | 0 | 0 | PASS |
| Calentamiento (`PIR_READY`) | 30 028 ms | ≥ 30 000 ms | PASS |
| Duración de cada episodio (`PRESENCE_DETECTED` → `PRESENCE_CLEARED`) | mín. 13 250 / mediana 13 700 / máx. 14 050 ms | ≥ 10 000 ms (retención) | PASS |

Los tramos se analizaron con [analyze_log.py](../../../tools/analyze_log.py) (`--from-ms 996000 --to-ms 1430124`, sección "RNF2 PIR") y contando las líneas `PRESENCE_DETECTED` del log.

## Análisis

- **Duración de cada episodio (≈ 13.7 s).** Son unos 3.7 s en los que la salida del AM312 se mantiene activa después del movimiento, más los 10 s de retención del firmware (`pir::PRESENCE_HOLD_MS`). Es decir, después de una pasada la placa sigue informando "hay alguien" durante unos 14 s.
- **Primera tanda (resultado negativo explicado).** Con pasadas cada ~15 s, cualquier movimiento al retirar la mano alargaba el episodio, y la pasada siguiente caía dentro de él: 15 pasadas produjeron 12 episodios (el primero duró 36 s). El sensor no falló: mientras el episodio estaba activo, la placa informaba presencia y una consulta por voz habría respondido "sí". Pero así no se puede contar 1 detección por pasada, por eso se repitió con 25 s entre pasadas, más que la duración de un episodio.
- **Primera fase sin nadie (invalidada).** La única detección coincide con un movimiento visible en el video; no es un falso positivo del sensor. La fase se repitió alejándose del escritorio y dio 0 detecciones en 5 min.
- **Conclusión para el diseño.** La resolución del PIR para contar personas es de una cada ~14 s: suficiente para "¿hay alguien en la puerta?", que es el único uso del PIR en SmartLoft (no acciona nada).

**Veredicto: PASS** (RF1, RNF2).
