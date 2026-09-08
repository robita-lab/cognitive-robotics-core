# Carpeta para la integración en ROS2

Esta carpeta contiene el código necesario para integar el código desarrollado por el GI dentro del ecosistema ROS2-humble.

Por tanto, resulta importante leer la documentación relacionada:
https://docs.ros.org/en/humble/index.html

En la máquina en la que se ejecuten o lancen (launch) los nodos, topics, servidores, etc de ROS2, éste tiene que estar instalado (ver documentación en el enlace anterior)

El código se compila utilizando `colcon` [https://docs.ros.org/en/humble/Tutorials/Beginner-Client-Libraries/Colcon-Tutorial.html] **IMPORTANTE: no subir al control de versiones (git) archivos binarios compilados**

La carpeta "ros2_ws" contiene el "workspace" de ROS2, esto es, una subcarpeta "src", que incluye los paquetes ROS2 generados. Éstos implementan nodos, mensajes, topics, servidores, clientes y otros elementos del ecosistema ROS2.
