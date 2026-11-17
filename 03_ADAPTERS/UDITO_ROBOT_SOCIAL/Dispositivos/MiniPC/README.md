# Arquitectura híbrida - UDITO · MiniPC

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales. Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

**Papel:** el «cuerpo» y el ejecutivo del robot.

| Capa / plano | Qué corre aquí |
|--------------|----------------|
| Capa 2 · Ejecutiva | Behavior Tree de interacción (`py_trees_ros`, fase F2) |
| Capa 1 · Habilidades | Base (Nav2), cuello y ojos (habla con los Arduinos) |
| Plano A · Seguridad | `twist_mux`, `collision_monitor`, watchdog de velocidad |
| Plano C · Modos y salud | Gestor de modos COMPLETO / LOCAL / DEGRADADO / SEGURO |
| Plano D · Observabilidad | Grabador rosbag2 (MCAP) en el SSD |

| Dato | Valor |
|------|-------|
| Sistema | Ubuntu 22.04 · ROS 2 Humble (Ubuntu 24.04 · Jazzy en la migración de enero de 2027) |
| Arquitectura | Intel x86_64 |
| Conexiones | Ethernet con la Jetson · USB serie con `Arduino_Ruedas` y `Arduino_Cuello` · lidar LD19 |

## Instalación

> Por completar por el responsable del cuerpo: instalación de ROS 2, Nav2, permisos de los puertos serie
> (`dialout`), reglas udev con nombre fijo para cada Arduino y para el lidar, sincronización de reloj (chrony)
> y carpeta de grabación en el SSD.

## Seta de emergencia

Es **hardware**: corta la potencia de los motores sin pasar por ningún software. Hasta que esté montada,
no se activan órdenes de movimiento autónomo (`follow`, `go_to`, `rotate`) con público (consenso, plano A).
Cableado y pieza: ver `COMPONENTES.md`.
