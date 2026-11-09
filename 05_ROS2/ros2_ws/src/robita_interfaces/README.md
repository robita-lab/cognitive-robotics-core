# robita_interfaces

Contrato de mensajes tipado de ROBITA-LAB (decisión **D2** de
`docs/ARQUITECTURA_CONSENSO.md`). Solo contiene ficheros IDL (`.msg`, `.srv`,
`.action`); no tiene código propio.

| Interfaz | Tipo | Quién la usa |
|----------|------|--------------|
| `Think` | acción | El ejecutivo (C.C. hoy, Behavior Tree en F2) pide a `cognitive` una respuesta. Interrumpible (D3). |

Pendiente de acordar con el equipo (F1): `Utterance.msg` y `TurnTrace.msg`,
alineados con `hri_msgs` (ROS4HRI) donde sea posible.

## Reglas

- Todo mensaje nuevo lleva `std_msgs/Header`, `session_id` y `turn_id` cuando
  pertenece a un turno de interacción.
- Nada exclusivo de Humble: el paquete debe compilar también en Jazzy (D19).
- Cambiar un campo existente rompe los bags grabados: añade campos nuevos en
  lugar de renombrar, y anótalo en el historial de versiones.

## Compilar

```bash
cd 05_ROS2/ros2_ws
colcon build --packages-select robita_interfaces
source install/setup.bash
ros2 interface show robita_interfaces/action/Think
```
