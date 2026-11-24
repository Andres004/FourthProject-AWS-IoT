# B03 — Secretos en el repositorio y en su historial

- Fecha y hora: 24/11/2026, 07:53 (Bolivia) / 11:53 UTC
- Responsable: Dabner
- Requisito: RNF6 (seguridad)
- Herramienta: [check_secrets.py](../../../tools/check_secrets.py)
- Archivo: [B03_salida.txt](B03_salida.txt)
- Comando: `python tools/check_secrets.py -o docs/evidencias_p4/B03/B03_salida.txt`

El script busca claves privadas, certificados, access keys de AWS, números de cuenta dentro de ARNs, endpoints reales de IoT y contraseñas de WiFi en todos los archivos que git publica y en el diff de **cada commit** del historial. También comprueba que los archivos de secretos estén ignorados y que las plantillas estén publicadas.

| Comprobación | Resultado | Criterio | Veredicto |
|---|---|---|---|
| Secretos en los archivos publicados | 0 en 240 archivos | 0 | PASS |
| Secretos en el historial | 0 en 68 commits (de los dos integrantes) | 0 | PASS |
| Rutas de secretos ignoradas por git (`secrets_*.h`, `certificados-*/`, `*.pem`, `*.key`, `*.zip`…) | 9/9 | todas | PASS |
| Plantillas publicadas (`secrets_vent.example.h`, `secrets_lights.example.h`) | 2/2 | publicadas | PASS |
| Control positivo sobre los `secrets_*.h` reales (no publicados) | Detecta la clave privada, el certificado, el endpoint y la contraseña WiFi de cada placa | Detectar los 4 tipos | PASS |

**Control positivo.** Demuestra que el escáner no es ciego: se le pasan los `secrets_*.h` reales, que **no** están en el repositorio, y encuentra en cada uno los cuatro tipos de secreto. Una primera corrida (07:41) dio FAIL en este control porque esos archivos todavía tenían el endpoint y el WiFi de la plantilla; la corrida guardada en [B03_salida.txt](B03_salida.txt) es la de 24/11/2026, 07:53 (Bolivia), con los archivos completos.

**Veredicto: PASS** (5 de 5 comprobaciones; 0 secretos publicados).
