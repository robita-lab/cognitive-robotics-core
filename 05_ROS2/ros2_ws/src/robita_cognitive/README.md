# robita_cognitive

Capa cognitiva de ROBITA: decide **qué decir** (RAG + LLM). Implementa la
acción `Think` de `robita_interfaces` (D3) y, mientras llega el Behavior Tree,
un adaptador compatible con el `cognitive_node` de `udito_ros`.
Plan: `docs/PLAN_COGNITIVE_RAG_LLM.md` · Evaluación del RAG: `docs/RAG_NORMATIVA.md`.

```
C.C. / BT ──Think──► cognitive_node ──► CognitiveEngine (robita_cognitive.core, Python puro)
C.C. actual ─topics─►                    ├─ memoria por session_id (fuente de verdad, D5)
                                         ├─ local: rules → normativa   (sin red)
                                         └─ remoto (P2): llm-engine por HTTP
```

## Backends locales (`rag_backend`)

| Valor | Qué hace | Dependencias |
|---|---|---|
| `normativa` (defecto) | `rules` (respuestas fijas, chistes, sedes, horarios: las reglas del rag-engine, sin modelos) + `normativa` (índice por artículos con e5-small ONNX; responde citando el artículo o se abstiene) | numpy, onnxruntime, tokenizers |
| `legacy` | `RAGSystem` completo de `01_SERVICES/rag-engine` (lo que usa `./UDITO`) | torch, sentence-transformers, faiss, PyPDF2 |
| `none` | solo `rules` | stdlib |

## Estructura

| Ruta | Qué es |
|------|--------|
| `robita_cognitive/core/` | Motor, memoria, frases, embeddings, índice y backends. **Sin ROS**. |
| `robita_cognitive/core/embeddings.py` | e5-small en ONNX Runtime (revisión del modelo fijada). |
| `robita_cognitive/core/knowledge.py` | Índice de conocimiento: carga, búsqueda densa/híbrida, BM25. |
| `robita_cognitive/core/backends/` | `rules`, `normativa`, `legacy`. |
| `robita_cognitive/tools/` | `fetch_model` (descarga el modelo), `build_index`, `eval_index`. |
| `robita_cognitive/think_server.py` | Nodo ROS 2 (`cognitive_node`): acción `Think` + adaptador de topics. |
| `robita_cognitive/think_client.py` | Cliente de prueba de `Think`. |
| `robita_cognitive/cli.py` | Prueba el motor sin ROS. |
| `docker/` | Imagen de desarrollo (`Dockerfile.humble`) y prueba de punta a punta (`e2e.sh`). |
| `04_KNOWLEDGE_CORE/indexes/` (raíz del repo) | `normativa.sources.json`, banco `normativa.eval.json` e índice versionado `normativa/`. |

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

`detail` dice de dónde sale cada respuesta, p. ej. `normativa:ACC:7@deee5efafe`
(artículo 7 de acceso, índice con esa huella) o `knowledge_horarios`.

## Parámetros

Ver `config/cognitive.yaml`: `rag_backend`, `index_dir`, `repo_root` (o
`$ROBITA_REPO_ROOT`), `memory_turns`, `memory_ttl_s`. El modelo se busca en
`$ROBITA_MODELS_DIR` (por defecto `~/.cache/robita/models`).

## Probar sin ROS

```bash
cd 05_ROS2/ros2_ws/src/robita_cognitive
UV="uv run --no-project --with numpy --with onnxruntime --with tokenizers"
$UV --with pytest python -m pytest -q test/          # 43 tests, sin modelo
$UV python -m robita_cognitive.tools.fetch_model     # una vez, con red (~490 MB)
$UV python -m robita_cognitive.cli "¿Tengo que traducir mis documentos?"
$UV python -m robita_cognitive.tools.eval_index -v   # mide el índice con el banco de preguntas
```

## Actualizar la normativa (índice)

1. Copiar el PDF a `04_KNOWLEDGE_CORE/raw-docs/` y declararlo en
   `04_KNOWLEDGE_CORE/indexes/normativa.sources.json` (código, título que se
   dirá en voz alta, estructura `articulos | puntos | entero`).
2. `$UV --with pypdf python -m robita_cognitive.tools.build_index 04_KNOWLEDGE_CORE/indexes/normativa.sources.json`
   (se ejecuta en el portátil o el servidor, **no** en el robot).
3. Añadir preguntas al banco `normativa.eval.json` y comprobar que las métricas
   no empeoran con `eval_index`.
4. Commitear `04_KNOWLEDGE_CORE/indexes/normativa/` (≈ 260 KB). El robot solo lo carga.

## Probar sin Jetson (contenedor Humble)

```bash
cd 05_ROS2/ros2_ws/src/robita_cognitive
docker build -t robita-cognitive:humble -f docker/Dockerfile.humble .        # ~1,6 GB, sin torch
cd ../../../..   # raíz del repo; --network none = sin WiFi
docker run --rm --network none -v "$PWD:/repo:ro" robita-cognitive:humble \
  bash /repo/05_ROS2/ros2_ws/src/robita_cognitive/docker/e2e.sh
```

`e2e.sh` compila los dos paquetes, lanza el nodo, hace preguntas por `Think` e
imprime la memoria del nodo. Para el backend `legacy`: imagen con
`--build-arg LEGACY_RAG=1` (~2,2 GB) y ver el comentario de `e2e.sh`.

## En la Jetson (pendiente de acceso)

1. `colcon build --packages-select robita_interfaces robita_cognitive` (Humble nativo, JetPack 6).
2. `pip3 install "numpy<2" onnxruntime tokenizers` (o `onnxruntime-gpu` de Jetson Zoo para usar la GPU).
3. `python3 -m robita_cognitive.tools.fetch_model` con red, o copiar `~/.cache/robita/models/`.
4. `export ROBITA_REPO_ROOT=<ruta al repo>` (con `--symlink-install` se autodetecta).
5. Medir RAM/CPU con el nodo cargado (condición 3 de Danilo). Referencia en x86: 868 MB RSS con e5 fp32;
   si no cabe, int8 (ver `docs/RAG_NORMATIVA.md` §4).

Solo para `legacy`: instalar torch con pip trae un `setuptools` que rompe
`colcon build` (`TypeError: canonicalize_version() ... strip_trailing_zero`);
`pip3 uninstall setuptools` deja el de apt.

## Problemas conocidos

- **Respuestas extractivas:** el artículo es el correcto en el 78 % (95 % entre
  los 3 primeros), pero la frase elegida no siempre contesta exactamente.
  Siguiente paso: fichas por artículo revisadas por una persona (`docs/RAG_NORMATIVA.md` §6) y LLM del servidor (P2).
- **Cancelación:** se comprueba entre backends; la cancelación real (cerrar el
  stream del LLM) llega con P2. Las rutas de cancelar/interrumpir del servidor
  `Think` aún no se han probado con un backend lento.
- **Segfaults aleatorios de Python en contenedores `ros:humble` del portátil de
  desarrollo** (también en `colcon build`); no en el host. Si una prueba en
  Docker muere con `Segmentation fault`, repetirla. Comprobar en la Jetson.
