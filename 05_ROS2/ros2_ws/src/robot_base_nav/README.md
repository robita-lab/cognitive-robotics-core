# robot_base_nav

Paquete ROS 2 (Humble) para navegación SLAM de una base diferencial de 2 ruedas
(BLDC + ZS-X11H vía Arduino con PID de velocidad) y lidar LDRobot.


## Base de dos ruedas

La base del robot está modelada como un archivo URDF en [robot.urdf](.\description\robot.urdf.xacro)

El nodo que la controla está en [serial_bridge_node.py](.\robot_base_nav\serial_bridge_node.py), y hace de puente entre TOPICS de navegación de ROS y el puerto serie para comunicación con Arduino.

El código que va a la placa Arduino que controla los motores de las ruedas está en [mainBasePIDControl.ino](..\03_ADAPTERS\robot-udit-physical\base-wheels\mainBasePIDcontrol\mainBasePIDcontrol.ino)

Los topics que recibe el nodo para mover la base son:
- Topic de movimiento: `cmd_vel` de tipo Twist definido en el estándar de ROS: `geometry_msgs.msg`

Los topics que envía el nodo son:
- Odometria: `odom`, de tipo Odometry definido en el estándar de ROS: `nav_msgs.msg`
- Estado de los GDL: `joint_states`, de tipo JointState definido en el estándar de ROS: `sensor_msgs.msg`


## Lidar

Integrado con el driver `ldlidar_node` del repo `Myzhar/ldrobot-lidar-ros2`:

- Topic de scan: `/ldlidar_node/scan` (ya configurado en Nav2 y slam_toolbox).
- El driver publica por su cuenta la TF `ldlidar_base -> ldlidar_link`.
- Nuestro URDF (modelo físico de la base del robot) aporta `base_link -> ldlidar_base` (ver `ldlidar_base_joint`).
- `bringup.launch.py` incluye `ldlidar_with_mgr.launch.py`, que añade el
  lifecycle_manager necesario para que el nodo pase a estado *active*.

Antes de lanzar, ajusta el puerto serie y el modelo del lidar en el `ldlidar.yaml`
del propio paquete `ldlidar_node`.

## Arbol de TF resultante

```
map (slam_toolbox)
 |__ odom (serial_bridge_node)
      |__ base_link (robot_state_publisher)
           |__ wheel_left_link / wheel_right_link
           |__ ldlidar_base
                |__ ldlidar_link (driver del lidar)
```

## Ajustar antes de usar

- `wheel_radius`, `wheel_separation`, `serial_port`: argumentos de `bringup.launch.py`.
- `description/robot.urdf.xacro`: dimensiones reales y posicion del lidar
  (`ldlidar_base_joint`).
- `config/nav2_params.yaml`: `robot_radius`, `max_vel_x`, `acc_lim_x`.

## Compilar

```bash
cd ~/ros2_ws
rosdep install --from-paths src --ignore-src -r -y
colcon build --symlink-install
source install/setup.bash
```

## Lanzar (una terminal por bloque, todas con el workspace sourceado)

```bash
# Terminal 1 - base + lidar
ros2 launch robot_base_nav bringup.launch.py serial_port:=/dev/ttyACM0

# Terminal 2 - SLAM (publica map -> odom)
ros2 launch robot_base_nav slam.launch.py

# Terminal 3 - Nav2
ros2 launch robot_base_nav navigation.launch.py

# Terminal 4 - RViz2, para visualizar los datos (opcional)
rviz2
```

Espera a que cada bloque este estable antes de lanzar el siguiente: Nav2 necesita
que ya existan los frames `odom` y `map`.

## Mover el robot y mapear

Teleoperacion por teclado:

```bash
sudo apt install ros-humble-teleop-twist-keyboard -y
ros2 run teleop_twist_keyboard teleop_twist_keyboard
```

Guardar el mapa cuando termines:

```bash
ros2 run nav2_map_server map_saver_cli -f ~/mi_mapa
```

Navegar despues con el mapa guardado en vez de SLAM en vivo:

```bash
ros2 launch robot_base_nav navigation.launch.py map:=/home/TU_USUARIO/mi_mapa.yaml
```

## Verificaciones utiles

```bash
ros2 topic hz /odom                  # odometria publicandose
ros2 topic hz /ldlidar_node/scan     # lidar publicando
ros2 run tf2_tools view_frames       # genera frames.pdf con el arbol de TF
ros2 run tf2_ros tf2_echo odom base_link
ros2 node list
```
