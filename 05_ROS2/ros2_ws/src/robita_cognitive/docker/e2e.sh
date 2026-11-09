#!/bin/bash
# Prueba de punta a punta de robita_cognitive con el RAG completo, sin red.
# Se ejecuta DENTRO de la imagen robita-cognitive:humble. Desde la raíz del repo:
#
#   docker run --rm --network none -v "$PWD:/repo:ro" \
#     -v robita-rag-cache:/robita/01_SERVICES/rag-engine/data \
#     robita-cognitive:humble bash /repo/05_ROS2/ros2_ws/src/robita_cognitive/docker/e2e.sh
#
# Copia rag-engine y 04_KNOWLEDGE_CORE a /robita (el rag-engine escribe su caché
# junto al código y el repo va montado en solo lectura).
set -e
mkdir -p /robita/01_SERVICES /ws/src
cp -r /repo/01_SERVICES/rag-engine /robita/01_SERVICES/ && cp -r /repo/04_KNOWLEDGE_CORE /robita/
cp -r /repo/05_ROS2/ros2_ws/src/robita_interfaces /repo/05_ROS2/ros2_ws/src/robita_cognitive /ws/src/
find /ws/src /robita -name __pycache__ -prune -exec rm -rf {} +
cd /ws && source /opt/ros/$ROS_DISTRO/setup.bash
colcon build --packages-select robita_interfaces robita_cognitive > /tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
source install/setup.bash
export ROBITA_REPO_ROOT=/robita
# Precalienta la caché de PDFs (volumen persistente): el parseo de PDF da
# segfaults aleatorios en esta máquina; una vez cacheado ya no se parsea.
for n in 1 2 3 4 5 6 7 8; do
  if ros2 run robita_cognitive cognitive_cli "hola" >/tmp/warm.log 2>&1; then echo "== caché lista (intento $n)"; break; fi
  echo "   intento $n falló: $(grep -m1 -oE 'Segmentation fault|Aborted|Error.*' /tmp/warm.log || tail -1 /tmp/warm.log)"
done
ros2 launch robita_cognitive cognitive.launch.py > /tmp/node.log 2>&1 &
T0=$(date +%s)
until grep -q "backends cargados" /tmp/node.log; do sleep 2; [ $(( $(date +%s) - T0 )) -gt 400 ] && { echo TIMEOUT; tail -30 /tmp/node.log; exit 1; }; done
echo "== carga en $(( $(date +%s) - T0 )) s: $(grep -o 'backends cargados.*' /tmp/node.log)"
ask() { echo; echo "== $1"; ros2 run robita_cognitive think_client --session rag "$1" 2>&1 | grep -vE '^\s+\[[0-9]+\]'; }
ask "hola"
ask "¿Cuál es el horario de secretaría?"
ask "¿Cuáles son los requisitos de acceso a un máster?"
ask "¿Dónde está la universidad?"
ask "¿Qué es el RAC?"
ask "Cuéntame un chiste"
ask "¿Quién ganó el mundial de 2010?"
echo; echo "== errores en el log"; grep -iE 'error|traceback' /tmp/node.log | head -5 || true
kill %1 2>/dev/null || true
