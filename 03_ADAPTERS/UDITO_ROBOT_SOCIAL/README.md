# Arquitectura híbrida - UDITO · Robot social (dispositivos)

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas
> (0 plataforma · 1 habilidades · 2 ejecutiva BT · 3 deliberativa) + 4 planos transversales
> (A seguridad · B modelo del mundo · C modos y salud · D observabilidad).
> Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../docs/Arquitectura_hibrida_UDITO_v2.png)

Cada carpeta de `Dispositivos/` contiene **solo** lo necesario para que ese equipo funcione:
instalación, configuración, firmware y piezas. **El código del robot está en `05_ROS2/`.**

## Dispositivos

| Carpeta | Papel en la arquitectura | Qué corre ahí |
|---------|--------------------------|---------------|
| [`Jetson_Orin_Nano/`](Dispositivos/Jetson_Orin_Nano/) | Capas 1 y 3 | Habilidad de voz (STT + TTS), rostro, DOA; `cognitive` con RAG local y memoria de conversación. Hoy, también el C.C. (hasta F2) |
| [`MiniPC/`](Dispositivos/MiniPC/) | Capas 1 y 2 · planos A, C, D | Ejecutivo Behavior Tree, Nav2, `twist_mux`, `collision_monitor`, gestor de modos, grabación rosbag2 |
| [`Arduino_Ruedas/`](Dispositivos/Arduino_Ruedas/) | Capa 0 | Firmware de la base: PID de motores y odometría |
| [`Arduino_Cuello/`](Dispositivos/Arduino_Cuello/) | Capa 0 | Firmware del cuello (2 servos) y ojos (2 matrices LED) |
| [`Servidor_Laboratorio/`](Dispositivos/Servidor_Laboratorio/) | Capa 3 (opcional) · plano D | `llm-engine` (LLM 7–8B) y RAG completo; ingesta de datos |
| [`Raspberry/`](Dispositivos/Raspberry/) | Sin asignar | Reservado |

## Cómo se conectan

```
                    Servidor_Laboratorio (GPU)
                             ▲  HTTP por túnel WireGuard (lo abre siempre el robot)
                             │
  ReSpeaker + altavoz ── Jetson_Orin_Nano ══ Ethernet (ROS 2 / DDS) ══ MiniPC ── lidar LD19
  pantalla de rostro ──┘                                                 │  USB serie
                                                        ┌────────────────┴────────────────┐
                                                  Arduino_Ruedas                     Arduino_Cuello
                                               (motores BLDC + encoders)          (2 servos + 2 matrices LED)
                     Seta de emergencia: corta la potencia de los motores (hardware, sin pasar por software)
```

## Plantilla de cada dispositivo

| Archivo | Contenido |
|---------|-----------|
| `README.md` | Qué hace el equipo, cómo instalarlo desde cero y cómo comprobar que funciona |
| `COMPONENTES.md` | Piezas, modelo exacto, para qué sirve cada una y dónde conseguirla |
| Subcarpetas | `arranque/`, `entorno_ros2/`, `firmware/`… según lo que necesite |
