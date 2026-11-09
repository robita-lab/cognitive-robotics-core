# Plan — Integración de RAG + LLM en ROS 2

**Encargo:** Javier F. Gorostiza (JFG), "Integración de un RAG+LLM en ROS".
**Responsable:** Luis Peña · **Rama:** `feature/cognitive-rag-llm` (desde `develop`)
**Estado:** v0.1 · 2026-11-09 · borrador para revisar con JFG y Danilo

Este plan es la parte cognitiva de la fase F2 del documento de consenso
(`docs/ARQUITECTURA_CONSENSO.md`, rama `feature/architecture-consensus`):
D2 (contrato tipado), D3 (acción `Think` interrumpible), D4 (control en el
robot, lo pesado en el servidor) y D5 (cognitive → HTTP con respaldo; la
memoria de conversación vive en el robot).

## 1. Restricciones

- **Sin Jetson por ahora.** JFG quiere el despliegue en la Jetson, pero aún no
  está disponible. Todo se deja **listo para integrar**: se compila y prueba
  en contenedores ROS (Humble hoy, Jazzy por D19) y se entrega una lista de
  pasos para la Jetson.
- **Vamos con retraso.** Se prioriza tener un camino de punta a punta
  funcionando (P1) antes que la calidad de los modelos.
- **No pisar el trabajo de Danilo.** Él lleva el C.C., el BT y la voz
  (`udito_ros`). Aquí se crean paquetes nuevos y la frontera es `Think`.

## 2. Qué hay hoy

| Pieza | Dónde | Estado |
|---|---|---|
| `cognitive_node` | rama de Danilo, `udito_ros` | Topics `String`+JSON. Respuestas fijas o RAG del repo (FAISS + TinyLlama). Desactivado en el C.C. (`use_cognitive=False`). |
| `rag-engine` | `01_SERVICES/` | ~3.200 líneas. Embeddings `all-MiniLM-L6-v2` (inglés) sobre documentos en español. LLM local TinyLlama/Gemma-2B, flojo en español. |
| `llm-engine` | `01_SERVICES/` | FastAPI + Ollama, `/chat` y `/chat/stream`. Guarda la memoria en el servidor (contrario a D5). |
| `llm_dialog_manager` | `05_ROS2/ros2_ws/src/` | A retirar; se reaprovechan `router.py` y `llm_client.py`. |
| `llm_fallback.py` | `03_ADAPTERS/robot-udit-physical/` | Ya implementa el enrutado: UDIT → RAG, resto → LLM, LLM caído → RAG. |

## 3. Arquitectura

```
C.C. / BT ──Think (acción, cancelable)──► robita_cognitive   (robot, Jetson)
                                            ├─ memoria de conversación (fuente de verdad)
                                            ├─ router
                                            ├─ basic_qa + RAG local mínimo   ← funciona sin WiFi
                                            └─ HTTP + timeout ──► llm-engine (servidor, sin estado)
                                                                    ├─ LLM 7B Q4 (Ollama)
                                                                    └─ RAG completo
```

- **`cognitive_core`**: librería Python pura (router, memoria, backends). Se
  prueba con `pytest` sin ROS.
- **`robita_cognitive`**: paquete ROS 2 fino. Servidor de la acción `Think`
  más un adaptador a `/udito/cognitive/query|answer`, para que el C.C. actual
  de Danilo funcione sin esperar al BT.
- **`robita_interfaces`**: contrato tipado (D2). De momento solo `Think.action`.

## 4. Fases

### P0 — Coordinación y contrato (1–2 días)
- [x] Rama `feature/cognitive-rag-llm` sobre `develop`.
- [x] `robita_interfaces` con `Think.action`; compila en `ros:humble-ros-base`.
- [ ] Revisar con JFG dónde vive `robita_interfaces` (reunión 2026-11-10).
- [ ] Acordar con Danilo la frontera `Think` y pedirle que actualice su rama
      con `develop` (merge de prueba: 2 conflictos fáciles, `llm_fallback.py`
      y `PROJECT_LAYOUT.md`).
- [ ] Comprobar `robita_interfaces` también en Jazzy.

### P1 — Cognitivo en local, sin servidor (prioridad)
- [x] Núcleo en Python puro (`robita_cognitive.core`): motor con enrutado
      local → remoto, memoria por `session_id`, troceo en frases, 27 tests.
      Los backends `rag_local` y `basic_qa` **envuelven el rag-engine actual**
      (paridad con `./UDITO`, condición 1 de Danilo).
- [x] Paquete `robita_cognitive`: servidor `Think` (feedback por frases, un
      goal nuevo interrumpe al anterior) + adaptador a
      `/udito/cognitive/query|answer` + launch + `config/cognitive.yaml`.
- [x] **Salida (2026-11-09):** en `ros:humble` con `--network none`, el nodo
      responde por `Think` horarios, sedes, normativa, chistes y saludos
      (`docker/e2e.sh`).
- [x] **Embeddings multilingües (2026-11-09):** `multilingual-e5-small` en
      ONNX, un trozo por artículo, índice versionado en
      `04_KNOWLEDGE_CORE/indexes/normativa/`, construido fuera del robot.
      hit@1 0,25 → 0,78; hit@3 0,55 → 0,95; abstención fiable (AUC 0,99).
      Backend por defecto `normativa` + `rules`, sin torch. Evaluación y
      comparación con hypatia en `docs/RAG_NORMATIVA.md`.
- [ ] Fichas por artículo (respuesta hablada + preguntas que responde),
      generadas fuera del robot y revisadas por una persona
      (`docs/RAG_NORMATIVA.md` §6).
- [ ] Probar con el C.C. de Danilo (`use_cognitive:=true`) cuando su rama
      esté al día con `develop`.

### P2 — Servidor
- [x] `llm-engine` **`POST /v2/turn` sin estado**: el robot manda historial y
      fragmentos de normativa (`context`); SSE; clave de API
      (`ROBITA_API_KEYS`). `/v1` se queda para `./UDITO`. 14 tests.
- [x] Backend `llm_server` (stdlib): frases del stream → `partial_text`;
      servidor caído → respuesta local y 30 s sin reintentar; stream cortado →
      se devuelve lo ya dicho. La normativa pasa sus 3 fragmentos al LLM para
      que redacte (arregla la "frase equivocada" de la respuesta extractiva).
- [x] `scope_guard`: preguntas de UDIT sin respuesta local → "no tengo ese
      dato", sin LLM (el 3B se inventaba la cafetería).
- [x] **Salida (2026-11-09, `docker/e2e_llm.sh`, qwen2.5 3B en CPU):**
      general → LLM, normativa → LLM con fragmentos, servidor caído → local,
      sin URL → local; cancelar `Think` y un goal nuevo abortan la generación
      en el servidor ("cancelado por el cliente tras 80 trozos").
- [ ] **Medir con 7B en GPU.** En CPU con 3B la primera frase con fragmentos
      tarda 12–14 s (≈1000 tokens de contexto) y la calidad es floja. El
      Docker de este portátil no tiene `nvidia-container-toolkit`; probar en
      el servidor (Quadro RTX 4000) o instalarlo aquí.
- [ ] RAG completo en el servidor (más documentos, embeddings mayores): hoy el
      servidor usa los fragmentos que le manda el robot, que bastan para la
      normativa actual.

### P3 — Preparar la Jetson y cerrar
- Imagen/instrucciones arm64 y lista de pasos para la Jetson (colcon build,
  modelos, variables de entorno, medida de memoria y CPU — condición 3 de
  Danilo).
- `TurnTrace` con ruta, origen, modelo y latencias.
- LLM local en la Jetson solo si la medida deja margen (`qwen2.5:1.5b`).
- Retirar `llm_dialog_manager`; congelar `llm_fallback` cuando ROS alcance
  paridad con `./UDITO`.

## 5. Riesgos

- **Memoria de la Jetson** (8 GB compartidos con Whisper y Piper): sin medir
  hasta tener acceso.
- **Calidad en español** de los modelos pequeños.
- **Red universitaria:** WireGuard pendiente de TI; mientras tanto, HTTP en la
  LAN si TI lo permite.
