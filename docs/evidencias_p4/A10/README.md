# A10 — Hardware y calibración del MQ-2

- Fecha y hora: 22/11/2026 19:27 → 24/11/2026 (precalentamiento, calibración y comprobaciones)
- Responsables: Ricardo (calibración del MQ-2 con `mq2_probe`), Dabner (comprobaciones con el firmware de las placas)
- Requisito: RNF2 (exactitud de sensores y actuadores); fundamenta los umbrales de E1 y `WARMUP_MS`
- Herramientas: [tools/mq2_probe/](../../../tools/mq2_probe/) (una lectura promediada por segundo, 20 muestras cada 50 ms, `SUPPLY_MV = 5340`); multímetro UNI-T UT890D
- Archivos: [A10_01_clean_air_baseline.png](A10_01_clean_air_baseline.png) (aire limpio), [A10_02_lighter_response.png](A10_02_lighter_response.png) (respuesta a un ciclo de gas de encendedor)
- Registros crudos con el firmware final (mismo muestreo que `mq2_probe`: 20 lecturas cada 50 ms, promedio de 1 s, una línea `GAS_SAMPLE` por segundo):
  - [A08_vent_ESP32.log](../A08/A08_vent_ESP32.log): 66 min, **3853 lecturas en aire limpio**
  - [A05_vent_ESP32.log](../A05/A05_vent_ESP32.log) y [A05_intento1_ESP32.log](../A05/A05_intento1_ESP32.log): **19 ciclos con gas de encendedor**, segundo a segundo

## Calibración del MQ-2

| Medida | Valor | Cómo |
|---|---|---|
| Precalentamiento previo | ≈ 24 h continuas (22/11 19:27 → 23/11 ≈ 19:25) | Sensor alimentado sin interrupción |
| Alimentación del módulo | 5.337 V sin carga en el jack de la fuente externa | Multímetro |
| Aire limpio | `ao_pct` = 4.44 % (`pin_mv` = 142, `ao_mv` = 237) plano en 720 muestras; `min_mv` = `max_mv` en cada ventana | `mq2_probe`, [A10_01](A10_01_clean_air_baseline.png) |
| Gas de encendedor (sin llama) | 11 ciclos, picos de 9 % a 73 % según la cantidad de gas | `mq2_probe` |
| Respuesta al gas | 2–3.5 s hasta el pico | `mq2_probe` con marcas del botón BOOT |
| Recuperación | 3–5 s hasta volver a la línea base | `mq2_probe` |
| Arranque en frío (15 min apagado) | Sin transitorio apreciable | `mq2_probe` |

### Registros crudos del firmware

| Medida | Valor | Registro |
|---|---|---|
| Aire limpio: lecturas | 3853 (66 min, sin calentamiento ni gas) | [A08_vent_ESP32.log](../A08/A08_vent_ESP32.log) |
| Aire limpio: índice | 3850 lecturas en **4.4 %**, 3 entre 4.5 y 4.7 %; promedio 4.40 %, desviación estándar 0.006 puntos | ídem |
| Aire limpio: tensión en D34 | `pin_mv` 142 mV (149–151 mV en 3 lecturas); `min_mv` = `max_mv` dentro de la ventana en 3847 de 3853 | ídem |
| Ciclos de gas | 15 ciclos estandarizados (A05) + 4 del primer intento | [A05](../A05/README.md) |
| Picos | 16.8 % a 85.9 % (15 ciclos estandarizados) | ídem |
| Respuesta (línea base → alarma) | 1.0–3.0 s (promedio 1.5 s) | ídem |
| Recuperación (fin de la alarma → línea base) | 1.0–2.0 s (promedio 1.3 s) | ídem |

La deriva de la línea base durante 66 min fue nula dentro de la resolución del ADC (4.4 % de principio a fin). Los tiempos de respuesta y recuperación medidos con el firmware son algo menores que los de la calibración (2–3.5 s y 3–5 s), porque allí se tomaron con las marcas manuales del botón BOOT y aquí desde la primera lectura sobre la línea base hasta el cruce del umbral.

**Ejemplo de un ciclo** ([A10_02](A10_02_lighter_response.png)): 4.44 % → 14.57 % (primer segundo con gas) → 56.18 % → **84.36 %** de pico a los 4 s → 16.85 % → 8.93 % → 4.68 % a los 14 s del inicio. El pico dio `pin_mv` = 2703 mV en D34, por debajo de 3.3 V.

**Decisiones que salen de la calibración** (en [config_vent.h](../../../include/config_vent.h)):

| Constante | Valor | Justificación |
|---|---|---|
| `gas::SUPPLY_MV` | 5340 | Tensión medida de la fuente; el mismo valor en `mq2_probe` y en el firmware, para que los umbrales signifiquen lo mismo |
| `vent_defaults::GAS_HIGH_PCT` | 15 | Bien por encima del aire limpio (4.4 %, sin ruido) y por debajo de casi todos los picos de gas (9–73 %) |
| `vent_defaults::GAS_LOW_PCT` | 8 | Banda de histéresis de 7 puntos, mucho mayor que el ruido medido (0 en aire limpio); la alarma se apaga cuando el gas ya se disipó |
| `gas::WARMUP_MS` | 60 000 | El arranque en frío no mostró transitorio; 60 s quedan como margen |

**Limitación.** El aire limpio da 142 mV en D34, por debajo de ~150 mV, donde el ADC del ESP32 con 11 dB es poco lineal: la línea base queda plana en 4.4 % y no se puede medir una deriva menor. No afecta la detección, porque el gas da tensiones mucho mayores. El índice no es una concentración en ppm.

## Comprobaciones del hardware con las placas

| Medida | Valor | Fuente | Veredicto |
|---|---|---|---|
| Divisor del MQ-2 (seguridad de D34) | No se midió con la punta AO en +5 V (sin multímetro ese día). Indirecta: el mayor índice registrado, 86 % (`gas_mv` = 4590), equivale a 2.75 V en D34; en la calibración, 2.70 V | [A05](../A05/README.md), A10_02 | PASS (< 3.3 V) |
| Lectura del ADC en aire limpio | `pin_mv` = 142, `n` = 20 por ventana | [B02](../B02/README.md), [A05](../A05/README.md) | PASS |
| Servo: tiempo del movimiento | 400–411 ms en todos los movimientos | B02, A03, A05, A06, A09 | PASS |
| Servo: ángulos | 0° y 90° por defecto; no calibrados ni medidos (la ventana de la maqueta no se montó) | — | No verificado |
| PIR: salida | Detecta solo con movimiento; 0 detecciones en 5 min sin nadie | [A12](../A12/README.md) | PASS |
| LEDs de las zonas | Los 5 encienden desde su GPIO; 220 Ω frente a 110 Ω sin diferencia visible de brillo → 220 Ω | Prueba de montaje, [foto](../A02/A02_07_foto_cinco_luces.webp) | PASS |
| Bus de 5 V con el servo y el MQ-2 funcionando | No medido (sin multímetro) | — | Pendiente como recomendación |

**Defecto de montaje encontrado (D-03 del informe).** El módulo MQ-2 no encendía en la fuente externa: un jumper macho-hembra usado como extensión de su GND no hacía contacto. Se diagnosticó moviendo un LED de prueba a las filas de VCC y GND del módulo y se resolvió cambiando el jumper.

**Veredicto: PASS** en la calibración del MQ-2, el divisor (verificación indirecta), el PIR, los LEDs y el tiempo del servo. Los ángulos del servo y el bus con carga quedan declarados como no medidos.
