# B03 — Secretos en el repositorio y en su historial

- Fecha y hora: 24/11/2026, 07:41 (Bolivia) / 11:41 UTC
- Responsable: Dabner
- Requisito: RNF6 (seguridad)
- Herramienta: [check_secrets.py](../../../tools/check_secrets.py)
- Archivo: [B03_salida.txt](B03_salida.txt)
- Comando: `python tools/check_secrets.py -o docs/evidencias_p4/B03/B03_salida.txt`

El script busca claves privadas, certificados, access keys de AWS, números de cuenta dentro de ARNs, endpoints reales de IoT y contraseñas de WiFi en todos los archivos que git publica y en el diff de **cada commit** del historial. También comprueba que los archivos de secretos estén ignorados y que las plantillas estén publicadas.

| Comprobación | Resultado | Criterio | Veredicto |
|---|---|---|---|
| Secretos en los archivos publicados | 0 en 236 archivos | 0 | PASS |
| Secretos en el historial | 0 en 66 commits (de los dos integrantes) | 0 | PASS |
| Rutas de secretos ignoradas por git (`secrets_*.h`, `certificados-*/`, `*.pem`, `*.key`, `*.zip`…) | 9/9 | todas | PASS |
| Plantillas publicadas (`secrets_vent.example.h`, `secrets_lights.example.h`) | 2/2 | publicadas | PASS |
| Control positivo sobre los `secrets_*.h` reales (no publicados) | Detecta la clave privada y el certificado de cada placa | Detectar los secretos que contiene | Ver nota |

**Nota sobre el control positivo.** El control demuestra que el escáner no es ciego: se le pasan los `secrets_*.h` reales, que **no** están en el repositorio, y tiene que encontrar sus secretos. En esta corrida encontró la **clave privada y el certificado** de las dos placas. Marca FAIL porque espera además el endpoint y la contraseña WiFi, que en este momento esos archivos tienen como valores de la plantilla (las placas se probaron en `local_test`, sin conexión). Se vuelve a correr cuando los `secrets_*.h` tengan el endpoint y el WiFi: ⟨resultado final⟩.

**Veredicto: PASS** en las cuatro comprobaciones del repositorio (0 secretos publicados).
