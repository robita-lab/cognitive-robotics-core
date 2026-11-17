# Despliegue de `cognitive_language` — servidor y Jetson

Rama: `feature/cognitive-rag-llm` (aún no está en `develop`: el merge se hace
después de estas pruebas, acuerdo del 2026-11-10). Orden recomendado:
**1) servidor, 2) Jetson sin red, 3) Jetson con el servidor**.

Robot y servidor van en la misma WiFi propia. El servidor escucha en HTTP con
clave de API; nada se expone fuera de esa red.

## 1. Servidor del laboratorio (Quadro RTX 4000, 8 GB)

Requisitos: Docker con `docker compose` v2, driver NVIDIA y
`nvidia-container-toolkit` (`docker run --rm --gpus all ubuntu nvidia-smi`
debe mostrar la GPU).

```bash
git clone git@github.com:robita-lab/cognitive-robotics-core.git   # o git fetch si ya está
cd cognitive-robotics-core
git fetch origin && git switch feature/cognitive-rag-llm && git pull

cd 01_SERVICES/llm-engine
cp .env.example .env
# En .env: LLM_API_KEYS=<clave larga>   (p. ej. `openssl rand -hex 24`)
#          API_PORT=8080                 (cámbialo si el puerto está ocupado)
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build -d
docker compose exec ollama ollama pull qwen3:4b-instruct-2507-q4_K_M   # 2,5 GB, una vez

curl http://localhost:8080/readyz                        # {"ready":true,"llm":true,...}
docker compose logs api | grep -i "LLM_API_KEYS vacía"   # no debe salir nada
```

Medir calidad y latencia desde cualquier máquina de la WiFi (el portátil o la
Jetson). Sale una tabla comparable con `docs/RAG_NORMATIVA.md` §8:

```bash
cd 05_ROS2/ros2_ws/src/cognitive_language
COGNITIVE_LLM_API_KEY=<clave> uv run --no-project --with numpy --with onnxruntime --with tokenizers \
  python -m cognitive_language.tools.eval_llm --url http://<ip-servidor>:8080 --label quadro-qwen3-4b \
  --out /tmp/quadro.jsonl
```

Referencia (RTX 4080 Laptop): 15/15 normativa, primera frase 0,68 s p50. En la
Quadro espero algo más de 1 s.

## 2. Jetson sin red (solo lo local)

La Jetson tiene `develop` en `/opt/robita-lab` para `./UDITO`. Para no
tocarlo, la rama va en un *worktree* aparte:

```bash
cd /opt/robita-lab
git fetch origin
git worktree add /opt/cognitive-language origin/feature/cognitive-rag-llm
cd /opt/cognitive-language
```

### Opción A — Docker (lo más rápido para validar)

La misma imagen que en el portátil; `ros:humble-ros-base` es multi-arquitectura
y hay wheels arm64 de onnxruntime y tokenizers.

```bash
cd 05_ROS2/ros2_ws/src/cognitive_language
docker build -t cognitive-language:humble -f docker/Dockerfile.humble .   # con red, una vez
cd /opt/cognitive-language
docker run --rm --network none -v "$PWD:/repo:ro" cognitive-language:humble \
  bash /repo/05_ROS2/ros2_ws/src/cognitive_language/docker/e2e.sh
```

Debe acabar con respuestas citando artículos, `memoria del nodo: ~870 MB RSS`
(valor en x86) y sin errores en el log. **Apunta la memoria que da en la
Jetson.**

### Opción B — ROS 2 Humble nativo

```bash
source /opt/ros/humble/setup.bash
pip3 install "numpy<2" "onnxruntime>=1.17" "tokenizers>=0.15"
python3 -m pip show setuptools   # si vino de pip con torch y colcon falla: pip3 uninstall setuptools

cd /opt/cognitive-language/05_ROS2/ros2_ws
colcon build --symlink-install --packages-select cognitive_language_interfaces cognitive_language
source install/setup.bash

python3 -m cognitive_language.tools.fetch_model      # con red, una vez (~490 MB)
#   sin red: copiar ~/.cache/cognitive_language/models/ desde el portátil
export COGNITIVE_REPO_ROOT=/opt/cognitive-language   # con --symlink-install se autodetecta

ros2 launch cognitive_language cognitive.launch.py   # terminal 1
ros2 run cognitive_language think_client "¿La matrícula incluye seguro escolar?"   # terminal 2
```

Medir: `ps -o rss,pcpu,cmd -p $(pgrep -f cognitive_node | head -1)` (o `tegrastats`) con el nodo
cargado, y repetirlo con Whisper y Piper cargados cuando Danilo tenga
`voice_skills` en su sitio (su condición 3). Si no cabe: el modelo int8 ahorra
unos 340 MB (`docs/RAG_NORMATIVA.md` §4).

## 3. Jetson con el servidor

Con el nodo de la opción B (o el e2e de la opción A con `--network host`):

```bash
export COGNITIVE_LLM_URL=http://<ip-servidor>:8080
export COGNITIVE_LLM_API_KEY=<clave>
ros2 launch cognitive_language cognitive.launch.py
ros2 run cognitive_language think_client "¿Tengo que traducir mis documentos?"   # source=llm_server
```

Prueba completa (general, normativa, memoria, cancelación, servidor caído):

```bash
docker run --rm --network host -v "$PWD:/repo:ro" \
  -e COGNITIVE_LLM_URL=http://<ip-servidor>:8080 -e COGNITIVE_LLM_API_KEY=<clave> \
  cognitive-language:humble bash /repo/05_ROS2/ros2_ws/src/cognitive_language/docker/e2e_llm.sh
```

Apaga el servidor a mitad (`docker compose stop api`): el robot debe seguir
respondiendo la normativa en local y no reintentar durante 30 s.

## Qué anotar para cerrar

| Medida | Dónde | Referencia (portátil) |
|---|---|---|
| Normativa correcta y primera frase p50 | servidor, `eval_llm` | 15/15 · 0,68 s |
| RAM del nodo | Jetson | ~870 MB |
| RAM total con Whisper + Piper | Jetson | pendiente (Danilo) |
| e2e sin red y con servidor | Jetson | todo en verde |

Con esto en verde: merge `--no-ff` de la rama a `develop` (ver `GIT-FLOW.md`).
