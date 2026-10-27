#!/usr/bin/env bash
# Arquitectura 3T - UDITO · Instalador de ROS 2 Humble para Ubuntu 22.04
# Sirve para la Jetson (aarch64) y para cualquier PC Ubuntu 22.04 (x86_64).
# Si ROS 2 Humble ya está instalado, solo añade lo que falte (colcon).
set -euo pipefail

. /etc/os-release
if [[ "${VERSION_CODENAME:-}" != "jammy" ]]; then
  echo "ROS 2 Humble requiere Ubuntu 22.04 (jammy). Detectado: ${PRETTY_NAME:-?}"; exit 1
fi

if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo "==> Instalando ROS 2 Humble (ros-base)…"
  sudo apt update
  sudo apt install -y software-properties-common curl
  sudo add-apt-repository -y universe
  ROS_APT_SOURCE_VERSION=$(curl -s https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest \
    | grep -F '"tag_name"' | awk -F'"' '{print $4}')
  curl -L -o /tmp/ros2-apt-source.deb \
    "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.jammy_all.deb"
  sudo dpkg -i /tmp/ros2-apt-source.deb
  sudo apt update
  sudo apt install -y ros-humble-ros-base
else
  echo "==> ROS 2 Humble ya instalado."
fi

echo "==> Herramientas de compilación…"
sudo apt install -y python3-colcon-common-extensions python3-rosdep

echo "OK. Siguiente: ./scripts/setup/jetson.sh (motores IA) y ./scripts/ros2/udito-ros.sh"
