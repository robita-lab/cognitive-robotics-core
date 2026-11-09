# robita_cognitive

Capa cognitiva de ROBITA: decide **qué decir** (RAG + LLM). Implementa la
acción `Think` de `robita_interfaces` (D3) y, mientras llega el Behavior Tree,
un adaptador compatible con el `cognitive_node` de `udito_ros`.
Plan completo: `docs/PLAN_COGNITIVE_RAG_LLM.md`.

```
C.C. / BT ──Think──► cognitive_node ──► CognitiveEngine (robita_cognitive.core, Python puro)
C.C. actual ─topics─►      │              ├─ memoria por session_id (fuente de verdad, D5)
                           │              ├─ backends locales: rag_local → basic_qa
                           │              └─ backend remoto (P2): llm-engine por HTTP
```

## Estructura

| Ruta | Qué es |
|------|--------|
| `robita_cognitive/core/` | Motor, memoria, troceo en frases, backends. **Sin ROS**: se prueba con `pytest`. |
| `robita_cognitive/core/backends/legacy.py` | Envuelve el `rag-engine` actual (`01_SERVICES/rag-engine`): mismo comportamiento que `./UDITO`. |
| `robita_cognitive/think_server.py` | Nodo ROS 2 (`cognitive_node`): acción `Think` + adaptador de topics. |
| `robita_cognitive/think_client.py` | Cliente de prueba de `Think`. |
| `robita_cognitive/cli.py` | Prueba el motor sin ROS. |
| `docker/Dockerfile.humble` | Imagen de desarrollo con torch CPU + sentence-transformers + faiss y el modelo de embeddings dentro. |

## Interfaces

**Acción** `/udito/cognitive/think` (`robita_interfaces/action/Think`)
- Feedback: una frase completa por mensaje (`partial_text`, `index`), para que el TTS empiece con la primera.
- Resultado: `text`, `emotion`, `source` (`basic_qa | rag_local | rag_server | llm_local | llm_server | fallback`), `model_id`, `latency_ms`.
- Un goal nuevo interrumpe al que está en curso (abort); cancelar un goal lo marca como cancelado y no se guarda en memoria.

**Topics** (compatibles con `udito_ros`, `std_msgs/String` con JSON)
- `/udito/cognitive/query` ← `{"id","text"[,"session_id"]}`
- `/udito/cognitive/answer` → `{"id","text","emotion","source","detail","latency_ms","session_id"}`
- Sin `session_id`, se abre sesión nueva tras `topic_session_idle_s` de silencio.

Para usarlo con el C.C. de Danilo: lanzar este nodo **en lugar de**
`udito_ros cognitive_node` y poner `use_cognitive:=true` en `udito_cc_node`.

## Parámetros

Ver `config/cognitive.yaml`. Los importantes: `use_rag` (false = solo
respuestas fijas, arranque instantáneo), `repo_root` (o `$ROBITA_REPO_ROOT`),
`memory_turns`, `memory_ttl_s`.

El RAG tarda en cargar (embeddings + índice); mientras tanto contesta
`basic_qa`. El log avisa con `backends cargados: {...}`.

## Probar sin ROS

```bash
cd 05_ROS2/ros2_ws/src/robita_cognitive
uv run --no-project --with pytest python -m pytest -q test/   # 27 tests, sin modelos
python3 -m robita_cognitive.cli --no-rag "hola"               # solo respuestas fijas
```

## Probar sin Jetson (contenedor Humble)

```bash
# Imagen (una vez; ~2,2 GB):
docker build -t robita-cognitive:humble \
  -f 05_ROS2/ros2_ws/src/robita_cognitive/docker/Dockerfile.humble \
  05_ROS2/ros2_ws/src/robita_cognitive/docker/
# Prueba de punta a punta desde la raíz del repo; --network none = sin WiFi:
docker run --rm --network none -v "$PWD:/repo:ro" \
  -v robita-rag-cache:/robita/01_SERVICES/rag-engine/data \
  robita-cognitive:humble bash /repo/05_ROS2/ros2_ws/src/robita_cognitive/docker/e2e.sh
```

`docker/e2e.sh` compila los dos paquetes, lanza el nodo con el RAG y hace
varias preguntas por `Think`. A mano, dentro del contenedor:
`ros2 launch robita_cognitive cognitive.launch.py [use_rag:=false]` y
`ros2 run robita_cognitive think_client "¿Dónde está la universidad?"`.

## En la Jetson (pendiente de acceso)

1. `colcon build --packages-select robita_interfaces robita_cognitive` (Humble nativo, JetPack 6).
2. `export ROBITA_REPO_ROOT=<ruta al repo>`; con `--symlink-install` se autodetecta.
3. Dependencias del RAG: `01_SERVICES/rag-engine/requirements-jetson.txt`.
   **Ojo:** instalar torch con pip trae un `setuptools` que rompe `colcon build`
   (`TypeError: canonicalize_version() ... strip_trailing_zero`). Solución:
   `pip3 uninstall setuptools` para que quede el de apt.
4. Medir RAM/CPU con el RAG cargado antes de añadir más nodos (condición 3 de Danilo).

## Problemas conocidos

- **Calidad de las respuestas documentales:** el RAG actual, sin LLM, devuelve
  fragmentos literales (a veces cortados) y usa embeddings en inglés. Se
  arregla con embeddings multilingües (P1, paso 2) y con el LLM del servidor (P2).
- **Cancelación:** el RAG actual no se puede interrumpir a mitad; se comprueba
  la cancelación entre backends. La cancelación real (cerrar el stream del
  LLM) llega con P2.
- **Segfaults aleatorios al parsear PDF** (PyPDF2 y pypdf) dentro del
  contenedor ROS en el portátil de desarrollo (~15–30 % de ejecuciones); no
  ocurre en el host ni en `ubuntu:22.04`. Causa sin aclarar. Mitigación: la
  caché de texto por PDF (`rag-engine/data/rag_cache`) hace que solo haya que
  parsear una vez. Comprobar en la Jetson.
