# Arquitectura híbrida - UDITO · Entorno ROS 2 para todas las terminales y todos los usuarios.
# Se instala en /etc/profile.d/ (ver README.md de esta carpeta).
[ -f /opt/ros/humble/setup.bash ] && . /opt/ros/humble/setup.bash
export ROBITA_ROOT=/opt/cognitive-robotics-core
[ -f "$ROBITA_ROOT/05_ROS2/ros2_ws/install/setup.bash" ] && . "$ROBITA_ROOT/05_ROS2/ros2_ws/install/setup.bash"
