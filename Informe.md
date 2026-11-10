# Práctica 3 - Integración de Objetos Inteligentes con Alexa y AWS IoT Core

**Puerta inteligente de un monoambiente: sensor de presencia PIR y servomotor en un ESP32 sincronizados con un Device Shadow de AWS IoT Core y controlados por voz con una skill de Alexa**


|  |  |
| --- | --- |
| **Universidad** | Universidad Católica Boliviana “San Pablo” |
| **Carrera** | Ingeniería de Sistemas |
| **Asignatura** | SIS-234 Internet de las Cosas / 2-2026 |
| **Fecha de entrega** | 10 de noviembre de 2026 |
| **Repositorio** | [https://github.com/Andres004/ThirdProject-AWS-IoT](https://github.com/Andres004/ThirdProject-AWS-IoT) |
| **Grupo** | 1 |
| **Integrantes** | Ricardo Andres Andrade Vargas · Dabner Eliezer Orozco Veizaga |

---
## Resumen ejecutivo

_Pendiente (fase 9): arquitectura en pocas líneas, funcionamiento del sistema y tabla de cumplimiento de los requerimientos._

---
## Contenido

1. [Caso de uso y requerimientos](#1-caso-de-uso-y-requerimientos)
   - [1.1 Caso de uso y alcance](#11-caso-de-uso-y-alcance) · [1.2 Sensor y actuador](#12-justificación-del-sensor-y-el-actuador) · [1.3 Requerimientos funcionales](#13-requerimientos-funcionales) · [1.4 Requerimientos no funcionales](#14-requerimientos-no-funcionales) · [1.5 Matriz de trazabilidad](#15-matriz-de-trazabilidad)
2. [Análisis y diseño](#2-análisis-y-diseño)
   - [2.1 Arquitectura](#21-diagrama-de-arquitectura-del-sistema) · [2.2 Circuito](#22-diagrama-de-circuito) · [2.3 Clases](#23-diagramas-de-clases) · [2.4 Secuencia](#24-diagramas-de-secuencia) · [2.5 Shadow](#25-especificación-del-documento-shadow) · [2.6 Vinculación](#26-diseño-del-mecanismo-de-vinculación) · [2.7 Skill](#27-diseño-de-la-skill-de-alexa) · [2.8 Frecuencia de reporte](#28-frecuencia-de-reporte-y-consumo-de-mensajes)
3. [Desarrollo e implementación](#3-desarrollo-e-implementación)
   - [3.1 Entorno](#31-entorno-de-desarrollo) · [3.2 Repositorio](#32-estructura-del-repositorio) · [3.3 Módulos](#33-módulos-y-clases) · [3.4 AWS](#34-configuración-en-aws) · [3.5 Alexa](#35-configuración-en-alexa) · [3.6 Credenciales](#36-credenciales-y-secretos) · [3.7 Ejecución](#37-compilación-carga-y-despliegue) · [3.8 Fragmentos clave](#38-fragmentos-clave) · [3.9 Temporización](#39-temporización-sin-bloqueos) · [3.10 Logs](#310-registro-de-eventos-logs) · [3.11 Buenas prácticas](#311-buenas-prácticas-aplicadas) · [3.12 Cobertura](#312-cobertura-de-los-requerimientos)
4. [Pruebas y validaciones](#4-pruebas-y-validaciones)
   - [4.1 Plan de pruebas](#41-plan-de-pruebas) · [4.2 Físicas y de entorno](#42-a-pruebas-físicas-y-de-entorno) · [4.3 Automáticas](#43-b-pruebas-automáticas) · [4.4 Defectos corregidos](#44-defectos-encontrados-y-corregidos) · [4.5 Análisis de errores](#45-análisis-de-errores)
5. [Resultados](#5-resultados)
   - [5.1 Resultados consolidados](#51-resultados-consolidados) · [5.2 Análisis crítico](#52-análisis-crítico)
6. [Conclusiones](#6-conclusiones)
7. [Recomendaciones](#7-recomendaciones)
8. [Anexos](#8-anexos)

---

## 1. Caso de uso y requerimientos

### 1.1 Caso de uso y alcance

_Pendiente (fase 1)._

### 1.2 Justificación del sensor y el actuador

_Pendiente (fase 1)._

### 1.3 Requerimientos funcionales

_Pendiente (fase 1)._

### 1.4 Requerimientos no funcionales

_Pendiente (fase 1)._

### 1.5 Matriz de trazabilidad

_Pendiente (fase 1)._

---

## 2. Análisis y diseño

### 2.1 Diagrama de arquitectura del sistema

_Pendiente (fase 2)._

### 2.2 Diagrama de circuito

#### 2.2.1 Esquema eléctrico

_Pendiente (fase 2)._

#### 2.2.2 Pines y alimentación

_Pendiente (fase 2)._

#### 2.2.3 Montaje real

_Pendiente (fase 2)._

### 2.3 Diagramas de clases

#### 2.3.1 Firmware del objeto inteligente (ESP32)

_Pendiente (fase 3)._

#### 2.3.2 Función Lambda (backend de la skill)

_Pendiente (fase 3)._

### 2.4 Diagramas de secuencia

#### 2.4.1 Vinculación de un Thing

_Pendiente (fase 4)._

#### 2.4.2 Consulta del sensor

_Pendiente (fase 4)._

#### 2.4.3 Comando sobre el actuador

_Pendiente (fase 4)._

#### 2.4.4 Reconexión y aplicación del estado pendiente

_Pendiente (fase 4)._

### 2.5 Especificación del documento Shadow

_Pendiente (fase 5)._

### 2.6 Diseño del mecanismo de vinculación

_Pendiente (fase 5)._

### 2.7 Diseño de la skill de Alexa

_Pendiente (fase 5)._

### 2.8 Frecuencia de reporte y consumo de mensajes

_Pendiente (fase 5)._

---

## 3. Desarrollo e implementación

### 3.1 Entorno de desarrollo

_Pendiente (fase 6)._

### 3.2 Estructura del repositorio

_Pendiente (fase 6)._

### 3.3 Módulos y clases

_Pendiente (fase 6)._

### 3.4 Configuración en AWS

_Pendiente (fase 6): Thing, certificados, política de AWS IoT, función Lambda, tabla de DynamoDB y rol IAM, con la justificación de los permisos asignados y los permisos mínimos._

### 3.5 Configuración en Alexa

_Pendiente (fase 6): modelo de interacción y vinculación con la función Lambda._

### 3.6 Credenciales y secretos

_Pendiente (fase 6)._

### 3.7 Compilación, carga y despliegue

_Pendiente (fase 6)._

### 3.8 Fragmentos clave

_Pendiente (fase 6)._

### 3.9 Temporización sin bloqueos

_Pendiente (fase 6)._

### 3.10 Registro de eventos (logs)

_Pendiente (fase 6)._

### 3.11 Buenas prácticas aplicadas

_Pendiente (fase 6)._

### 3.12 Cobertura de los requerimientos

_Pendiente (fase 6)._

---

## 4. Pruebas y validaciones

### 4.1 Plan de pruebas

_Pendiente (fase 7)._

### 4.2 A. Pruebas físicas y de entorno

#### A01. Vinculación, cambio y desvinculación por voz

_Pendiente (fase 7)._

#### A02. Dos usuarios con Things distintos

_Pendiente (fase 7)._

#### A03. Consulta del sensor por voz

_Pendiente (fase 7)._

#### A04. Comandos y estado de la puerta

_Pendiente (fase 7)._

#### A05. Tiempo de respuesta extremo a extremo

_Pendiente (fase 7)._

#### A06. Exactitud del PIR y del servo

_Pendiente (fase 7)._

#### A07. Caída de WiFi con orden pendiente

_Pendiente (fase 7)._

#### A08. Corte de energía con orden pendiente

_Pendiente (fase 7)._

#### A09. Comandos inválidos desde AWS

_Pendiente (fase 7)._

#### A10. Estabilidad

_Pendiente (fase 7)._

### 4.3 B. Pruebas automáticas

#### B01. Pruebas unitarias de la Lambda

_Pendiente (fase 7)._

#### B02. Firmware con transporte serie

_Pendiente (fase 7)._

#### B03. Secretos en el repositorio

_Pendiente (fase 7)._

### 4.4 Defectos encontrados y corregidos

_Pendiente (fase 7)._

### 4.5 Análisis de errores

_Pendiente (fase 7)._

---

## 5. Resultados

### 5.1 Resultados consolidados

_Pendiente (fase 8)._

### 5.2 Análisis crítico

_Pendiente (fase 8)._

---

## 6. Conclusiones

_Pendiente (fase 8)._

---

## 7. Recomendaciones

_Pendiente (fase 8)._

---

## 8. Anexos

_Pendiente (fase 9)._
