# Evidencia B03: Secretos en el repositorio

Prueba B03 del [plan de pruebas](../../PLAN_DE_PRUEBAS.md). Fecha: 09/11/2026.

| Archivo | Qué muestra |
|---|---|
| B03_salida.txt | Salida de `python tools/check_secrets.py` |

[check_secrets.py](../../../tools/check_secrets.py) busca claves privadas, certificados, access keys de AWS, números de cuenta dentro de ARNs, endpoints reales de AWS IoT y contraseñas WiFi, en los archivos que git publica y en cada commit del historial. También comprueba que los archivos de secretos estén ignorados por git.

Como control positivo, analiza el `include/secrets.h` real, que existe en la PC pero no se publica: si no detectara ahí los cuatro tipos de secreto, un `PASS` no demostraría nada. El script solo imprime el tipo de secreto encontrado, nunca su valor.

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Secretos en archivos publicados | 0 de 38 archivos | 0 | PASS |
| Secretos en el historial | 0 en 12 commits | 0 | PASS |
| Rutas de secretos ignoradas por git | 5/5 | todas | PASS |
| Plantilla `include/secrets.example.h` publicada | sí | sí | PASS |
| Control: `secrets.h` real detectado | clave privada, certificado, endpoint, contraseña WiFi | los 4 | PASS |

> Se repite antes de la entrega, sobre el último commit, para cubrir los archivos agregados después.
