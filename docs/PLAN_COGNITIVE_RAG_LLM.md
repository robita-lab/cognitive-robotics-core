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
- `cognitive_core`: router, memoria por `session_id`, backends `basic_qa` y
  `rag_local`.
- Embeddings multilingües pequeños (p. ej.
  `paraphrase-multilingual-MiniLM-L12-v2`); versión del índice fijada.
- `robita_cognitive`: servidor `Think` + adaptador de topics + launch file.
- **Salida:** la demo responde preguntas de UDIT por ROS, sin WiFi (en
  contenedor).

### P2 — Servidor
- `llm-engine` sin estado: el robot envía el historial en cada petición.
  Clave de API. RAG completo en el mismo servicio (una sola GPU).
- Backend `llm_server` con streaming: cada frase completa sale como
  `partial_text` para que el TTS empiece con la primera.
- Cancelar `Think` cierra el stream HTTP y el servidor deja de generar.
- **Salida:** los 4 casos de respaldo vía `Think` (general → LLM,
  UDIT → RAG, LLM caído → RAG, sin URL → local) y la cancelación detiene la
  generación en el servidor.

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
