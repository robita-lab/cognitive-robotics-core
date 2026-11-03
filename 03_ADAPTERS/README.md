# Arquitectura híbrida - UDITO · 03_ADAPTERS

> **Arquitectura híbrida** = evolución del modelo 3T acordada en el consenso de ROBITA-lab (D14):
> cuatro capas (plataforma, habilidades, ejecutiva con Behavior Tree y deliberativa) y cuatro
> planos transversales (seguridad, modelo del mundo, modos y salud, observabilidad).
> Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../docs/Arquitectura_hibrida_UDITO_v2.png)

## Qué es un *adapter*

Un **adapter** es cualquier dispositivo, físico o de software, que se beneficia de UDITO:
un robot social, una web, un tótem, una app… Cada adapter tiene su carpeta.

| Adapter | Qué es |
|---------|--------|
| [`UDITO_ROBOT_SOCIAL/`](UDITO_ROBOT_SOCIAL/) | El robot social UDITO: Jetson, MiniPC, Arduinos, servidor… |
| `web-portal-university/` | Portal web de la universidad |

## Qué va aquí y qué no

| ✅ Va en 03_ADAPTERS | ❌ No va en 03_ADAPTERS |
|----------------------|-------------------------|
| Cómo **instalar y configurar** cada dispositivo para que funcione | Código de funcionamiento del robot → `05_ROS2/` |
| Ajustes del sistema operativo (servicios de arranque, reglas udev) | Motores de IA (Whisper, Piper, RAG) → `01_SERVICES/` |
| **Firmware** que se carga en un microcontrolador (Arduino) | Conocimiento y datos → `04_KNOWLEDGE_CORE/` |
| **Lista de componentes** y dónde conseguirlos (`COMPONENTES.md`) | Agentes → `02_AGENTS_FACTORY/` |

**Regla práctica:** si se estropea o se cambia una pieza, la carpeta del dispositivo debe decir
qué pieza es, de dónde sacarla y cómo dejar el nuevo equipo funcionando igual que el anterior.
