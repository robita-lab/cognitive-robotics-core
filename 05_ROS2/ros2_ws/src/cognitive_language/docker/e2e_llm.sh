#!/bin/bash
# Prueba de P2 por ROS: cognitive_language + llm-engine (/v2/turn).
# Desde la raíz del repo, con el llm-engine levantado en el host (puerto 18080):
#
#   docker run --rm --network host -v "$PWD:/repo:ro" \
#     -e COGNITIVE_LLM_URL=http://127.0.0.1:18080 -e COGNITIVE_LLM_API_KEY=<clave> \
#     cognitive-language:humble bash /repo/05_ROS2/ros2_ws/src/cognitive_language/docker/e2e_llm.sh
#
# Casos: (1) pregunta general → LLM sin contexto; (2) normativa → LLM con los
# fragmentos; (3) servidor caído → respuesta local; (4) cancelación a mitad.
# COGNITIVE_LLM_TIMEOUT alto si el LLM corre en CPU (por defecto aquí 40 s).
# CANCEL_AFTER / BARGE_DELAY (s): cuándo cancelar y cuándo lanzar el segundo goal; los
# valores por defecto son para LLM en GPU (respuestas de ~1,5 s). En CPU: 5 y 3.
set -e
mkdir -p /ws/src
cp -r /repo/05_ROS2/ros2_ws/src/cognitive_language_interfaces /repo/05_ROS2/ros2_ws/src/cognitive_language /ws/src/
cd /ws && source /opt/ros/$ROS_DISTRO/setup.bash
colcon build --packages-select cognitive_language_interfaces cognitive_language > /tmp/build.log 2>&1 || { tail -30 /tmp/build.log; exit 1; }
source install/setup.bash
export COGNITIVE_REPO_ROOT=${COGNITIVE_REPO_ROOT:-/repo} PYTHONDONTWRITEBYTECODE=1 COGNITIVE_LLM_TIMEOUT=${COGNITIVE_LLM_TIMEOUT:-40}
export ROS_DOMAIN_ID=${ROS_DOMAIN_ID:-42}
CANCEL_AFTER=${CANCEL_AFTER:-0.9}; BARGE_DELAY=${BARGE_DELAY:-0.3}   # --network host: no mezclarse con otros nodos de la máquina

start_node() {  # $1 = URL del LLM
  ros2 run cognitive_language cognitive_node --ros-args -p llm_url:="$1" > /tmp/node.log 2>&1 &
  NODE=$!
  T0=$(date +%s)
  until grep -q "backends cargados" /tmp/node.log; do
    sleep 1
    if [ $(( $(date +%s) - T0 )) -gt 120 ]; then echo TIMEOUT; tail -20 /tmp/node.log; exit 1; fi
  done
  return 0
}
stop_node() {  # ros2 run no reenvía la señal al proceso Python: matarlo por nombre
  pkill -f 'lib/cognitive_language/cognitive_node' || true
  while pgrep -f 'lib/cognitive_language/cognitive_node' > /dev/null; do sleep 0.2; done
}
ask() { echo; echo "== $1"; shift; ros2 run cognitive_language think_client --timeout 90 --session e2e "$@" 2>&1; }

echo "##### llm-engine en $COGNITIVE_LLM_URL"
start_node "$COGNITIVE_LLM_URL"
ask "(1) general → LLM" "¿Qué es un agujero negro?"
ask "(2) normativa → LLM con fragmentos" "¿Tengo que traducir mis documentos si están en otro idioma?"
ask "(2b) memoria de sesión" "¿Y si el documento es de Francia?"
ask "(guarda) UDIT sin dato → sin LLM" "¿Hay cafetería en la universidad?"
ask "(4) cancelación a los $CANCEL_AFTER s" --cancel-after $CANCEL_AFTER "Cuéntame con detalle la historia de la exploración espacial desde el Sputnik hasta hoy."
sleep 2
echo; echo "== (5) un goal nuevo interrumpe al anterior (barge-in)"
ros2 run cognitive_language think_client --timeout 90 --session e2e "Explícame con detalle cómo funciona un motor de combustión." > /tmp/goal_a.log 2>&1 &
A=$!
sleep $BARGE_DELAY
ros2 run cognitive_language think_client --timeout 90 --session e2e "hola" > /tmp/goal_b.log 2>&1
wait $A || true
echo "  goal A (largo): $(grep -a status= /tmp/goal_a.log)   [6 = ABORTED]"
echo "  goal B (nuevo): $(grep -a status= /tmp/goal_b.log)"
sleep 2
echo; echo "== log del nodo (LLM)"; grep -aE "llm_server|LLM|cancel" /tmp/node.log | tail -8
stop_node

echo; echo "##### (3) servidor caído (puerto cerrado)"
start_node "http://127.0.0.1:18089"
ask "(3) normativa con servidor caído → local" "¿Tengo que traducir mis documentos si están en otro idioma?"
ask "(3b) segundo turno: ni lo intenta (servidor marcado como caído)" "¿Qué es un agujero negro?"
grep -aE "no disponible|no lo intento|→" /tmp/node.log | tail -4
stop_node
