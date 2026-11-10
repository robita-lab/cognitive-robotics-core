#!/bin/bash
# Prueba de punta a punta de cognitive_language por ROS, sin red.
# Se ejecuta DENTRO de la imagen cognitive-language:humble. Desde la raíz del repo:
#
#   docker run --rm --network none -v "$PWD:/repo:ro" cognitive-language:humble \
#     bash /repo/05_ROS2/ros2_ws/src/cognitive_language/docker/e2e.sh [normativa|legacy|none]
#
# "legacy" necesita la imagen con LEGACY_RAG=1 y un repo escribible (el rag-engine
# guarda su caché junto al código): ver README.
set -e
BACKEND=${1:-normativa}
mkdir -p /ws/src
cp -r /repo/05_ROS2/ros2_ws/src/cognitive_language_interfaces /repo/05_ROS2/ros2_ws/src/cognitive_language /ws/src/
find /ws/src -name __pycache__ -prune -exec rm -rf {} +
cd /ws && source /opt/ros/$ROS_DISTRO/setup.bash
colcon build --packages-select cognitive_language_interfaces cognitive_language > /tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
source install/setup.bash
export COGNITIVE_REPO_ROOT=${COGNITIVE_REPO_ROOT:-/repo} PYTHONDONTWRITEBYTECODE=1

ros2 launch cognitive_language cognitive.launch.py rag_backend:=$BACKEND > /tmp/node.log 2>&1 &
T0=$(date +%s)
until grep -q "backends cargados" /tmp/node.log; do
  sleep 1; [ $(( $(date +%s) - T0 )) -gt 400 ] && { echo TIMEOUT; tail -30 /tmp/node.log; exit 1; }
done
echo "== carga en $(( $(date +%s) - T0 )) s: $(grep -o 'backends cargados.*' /tmp/node.log)"

ask() { echo; echo "== $1"; ros2 run cognitive_language think_client --session e2e "$1" 2>&1 | grep -vE '^\s+\[[0-9]+\]'; }
ask "hola"
ask "¿Cuál es el horario de secretaría?"
ask "¿Dónde está la universidad?"
ask "¿Tengo que traducir mis documentos si están en otro idioma?"
ask "¿Cuántas horas equivalen a un crédito ECTS?"
ask "¿La matrícula incluye seguro escolar?"
ask "¿Hay convocatoria de gracia en titulaciones a extinguir?"
ask "¿Quién ganó el mundial de 2010?"

PID=$(pgrep -f 'lib/cognitive_language/cognitive_node' | head -1)
[ -n "$PID" ] && echo && echo "== memoria del nodo: $(( $(awk '/VmRSS/{print $2}' /proc/$PID/status) / 1024 )) MB RSS"
echo; echo "== errores en el log"; grep -iE 'error|traceback' /tmp/node.log | head -5 || true
kill %1 2>/dev/null || true
