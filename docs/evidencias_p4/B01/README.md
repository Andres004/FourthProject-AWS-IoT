# B01 — Pruebas unitarias de las tres Lambdas

- Fecha y hora: 24/11/2026, 07:40 (Bolivia) / 11:40 UTC
- Responsable: Dabner (ejecución); el código y las pruebas son de Ricardo
- Requisitos: RF4–RF14 (lado de la Nube)
- Archivo: [B01_salida.txt](B01_salida.txt) (salida completa con `-v`)
- Comando, desde la raíz del repositorio:

```powershell
python -m pip install -r lambda/skill/requirements.txt -t lambda/skill/package
python -m unittest discover -s lambda/tests -v
```

La primera línea instala `ask-sdk-core` en `lambda/skill/package/` (ignorada por git), que las pruebas de la skill agregan al camino de búsqueda. Las pruebas no usan AWS: DynamoDB, AWS IoT y el reloj se reemplazan por dobles, así que corren sin cuenta ni conexión.

| Archivo de pruebas | Lambda | Clases | Casos | Resultado |
|---|---|---|---|---|
| [test_data_lambda.py](../../../lambda/tests/test_data_lambda.py) | `smartloft_data_lambda` | `DataLambdaTest` | 34 | 34 OK |
| [test_control_lambda.py](../../../lambda/tests/test_control_lambda.py) | `smartloft_control_lambda` | `ControlLambdaTest` | 13 | 13 OK |
| [test_skill_lambda.py](../../../lambda/tests/test_skill_lambda.py) | `smartloft_skill_lambda` | `LinkingTests` (7), `LightTests` (12), `WindowTests` (6), `GasTests` (4), `ModeAndThresholdTests` (7), `GeneralTests` (3) | 39 | 39 OK |
| **Total** | | | **86** | **86 OK** |

| Medida | Valor | Criterio | Veredicto |
|---|---|---|---|
| Casos que pasan | 86/86 | todos | PASS |
| Duración | 0.04 s | — | INFO |

**Entorno:** Python 3.13.7 en Windows 11; `ask-sdk-core` 1.19.0.

**Veredicto: PASS.**
