# ROBITA-SW

## Implementación de una arquitectura de control para Robots Sociales para Interacción Humano-Robot

Este repositorio contiene la programación pertinente para implementar una Arquitectura de Control que permita a los Robots Sociales interactuar con el ser humano de igual a igual.

Esta implementación software está integrada en [ROS2](https://docs.ros.org/en/humble/), y funciona, de forma general, para diversas máquinas que configuran robots y agentes virtuales.

## ROBOTS
### UDITO
Robot Social móvil que cuenta con la siguiente arquitectura Hardware:
...


## Estructura del proyecto

```
├── 01_SERVICES/          # Servicios que ofrece el robot/agente. Ejm: wakeword, STT, TTS, RAG (librerías locales)
│   └── llm-engine/       # LLM conversacional (HTTP, opcional — ROBITA_LLM_URL)
├── 03_ADAPTERS/   # Software específico de un robot o computador. Ejm: udito_standalone.py, robot_common.py
├── 04_KNOWLEDGE_CORE/    # textos + PDFs RAG
├── 05_ROS2/              # Implementación de packetes en ROS2, dentro del ros_ws
│   └── launch/       # donde residen los ``launchers`` o ficheros principales de ejecución.
│   └── log/       # Carpeta donde automáticamente se guardan todos los logs del sistema.
│   └── ros_ws/       # WorkSpace del sistema. Implementación por paquetes
```

## Modus operandi
El desarrollo se hace mediante ramas de desarrollo para funcionalidades concretas.

| Rama | Contenido |
|------|-----------|
| **`main`** | Releases más reciente |
| **`develop`** | Trabajo activo — **solo offline** en Jetson |
| **`develop-base`** | Referencia histórica; incluye `_archive/` con modo servidor |


## Computadores
Cada ordenador/computador/máquina debe incluir iuna variable MACHINE_ID que sirva para que el sistema ROBITA-SW reconozca dónde se está ejecutando, qué tiene que ejecutar (launchers de ROS) y cómo ejectuarlo (parámetros)

| Tipo | MACHINE_ID| Uso |
|---------|-----|-----|
| miniPC | "UDIT_BASE" | Se encarga del control de movimiento de la base del robot UDITO.|
| JetsonNano ORIN | |


