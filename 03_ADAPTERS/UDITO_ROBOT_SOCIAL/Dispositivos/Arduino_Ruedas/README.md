# Arquitectura híbrida - UDITO · Arduino de las ruedas

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales. Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

**Papel:** capa 0 (plataforma). Controla los motores de la base con PID de velocidad y envía la odometría al MiniPC por USB serie.

## Contenido

| Carpeta | Qué es |
|---------|--------|
| [`firmware/`](firmware/) | Sketches de Arduino de la base (antes `base-wheels`, dentro de la carpeta `robot-udit-physical` de 03_ADAPTERS) |

> **Por completar por el responsable del cuerpo:** cuál de los sketches es el que está cargado hoy en la placa,
> cómo cargarlo (placa y puerto en Arduino IDE o `arduino-cli`) y los parámetros PID en uso (`firmware/PID_tunning.txt`).
