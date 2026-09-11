# Carpeta para la integración en ROS2

Esta carpeta contiene el código necesario para integar el código desarrollado por el GI dentro del ecosistema ROS2-humble.

Por tanto, resulta importante leer la documentación relacionada:
https://docs.ros.org/en/humble/index.html

En la máquina en la que se ejecuten o lancen (launch) los nodos, topics, servidores, etc de ROS2, éste tiene que estar instalado (ver documentación en el enlace anterior)

El código se compila utilizando `colcon` [https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Colcon-Tutorial.html] **IMPORTANTE: no subir al control de versiones (git) archivos binarios compilados**

La carpeta "ros2_ws" contiene el "workspace" de ROS2, esto es, una subcarpeta "src", que incluye los paquetes ROS2 generados. Éstos implementan nodos, mensajes, topics, servidores, clientes y otros elementos del ecosistema ROS2.

## Contenido de las carpetas
En **05_ROS2** solamente debe subirse código exclusivo de ROS2. Dentro de este código, se hará uso de clases y otras implementaciones, en otras carpetas (01_SERVIES,...). Para que todo compile, se deberá utilizar variables de entorno.

- launch: esta carpeta implementa los ficheros que lanzan nodos ROS. se divide en subcarpetas por cada **agente** del sistema (udito, web-admisiones, etc)
- log: puede incluirse o no en el repositorio. Aquí es donde vuelcan los logs la ejecución de los distintos nodos ROS.
- ros2_ws: este es el workspace de ROS, esto es, donde se debe implementar cada proyecto de ROS. Cada proyecto de ROS estará en una carpeta.
>IMPORTANTE: los proyectos de ROS deben ser carpetas que estén dentro de ros2_ws/src y no directamente en ros2_ws.

Para compilar los proyectos de ROS, se utiliza **colcon**. Más información en:
https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Colcon-Tutorial.html



## TODOs

- Generar variables de entorno como alguna tipo **PATH_COGNITIVE_ROBOTICS_CORE**, que sea utilizada por el código para poder acceder a ficheros y clases de una carpeta a otra, y sea válido para distinas máquinas, en local.


