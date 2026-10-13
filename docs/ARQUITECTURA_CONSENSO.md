# Arquitectura UDITO — documento de consenso

**Estado:** v1.1 · D1–D13 y D17 aceptadas; D14–D16, D18 y D19 pendientes · **Fecha:** 2026-10-13 · **Redacta:** Luis Peña
**Rama:** `feature/architecture-consensus`
**Fuentes revisadas:** `develop` @ `37816c2`, `origin/feature/ros2-voice-orchestrator` @ `9074f6a` (Danilo),
`docs/Arquitectura en capas-ROBITA_LAB.jpg` (arquitectura v2), `01_SERVICES/llm-engine/ARCHITECTURE.md`,
y la propuesta de datos recibida (rosbag / DuckDB / Zenoh / InfluxDB / Grafana / MCAP / Polars).

> **Cómo usar este documento.** Cada decisión tiene un identificador (`D#`), opciones con pros y contras,
> un veredicto (✅ adoptar · ⚠️ adoptar con cambios · ❌ descartar) y un **estado**: *Aceptada*, *Descartada*
> o *Pendiente*. Se evalúan con el mismo criterio **todas** las propuestas, incluidas las mías
> (`llm-engine`, `llm_dialog_manager`).
>
> Las respuestas del equipo se conservan literalmente como **Decisión del equipo**. Cuando una decisión
> tiene consecuencias que no estaban a la vista, se añade una **Observación**. Las observaciones no
> reabren la decisión: señalan lo que hay que tener en cuenta al aplicarla.

### Historial

| Versión | Fecha | Cambio |
|---------|-------|--------|
| v0 | 2026-10-13 | Borrador inicial: D1–D13. |
| v1 | 2026-10-13 | Respuestas del equipo incorporadas. El modelo 3T se sustituye por una **arquitectura híbrida propia** (§4, D14). Nuevas D15–D19: red y seguridad, motor de BT, grabación sin NVMe, activación sin wakeword y migración a Jazzy. Interfaces renombradas a `robita_interfaces`. |
| v1.1 | 2026-10-13 | SSD en el Mini PC y compra de NVMe → D17 aceptada. Seta de emergencia por instalar → condición previa para el movimiento autónomo. **D16 rehecha**: qué controla el BT, rendimiento medido y **py_trees en lugar de BT.CPP**, con la lista de qué va en C++ y qué en Python. |

---

## 0. Resumen (TL;DR)

| # | Tema | Decisión | Estado |
|---|------|----------|--------|
| D1 | Esqueleto ROS 2 | 3T insuficiente → **arquitectura híbrida propia** (D14). `udito_ros` de Danilo es el punto de partida del código. `llm_dialog_manager` se retira y su lógica pasa a `cognitive`. | Aceptada (rehecha en v1) |
| D2 | Contrato de mensajes | Interfaces tipadas en el paquete **`robita_interfaces`**, con `header`, `session_id` y `turn_id`. Alinear con ROS4HRI cuando exista mensaje estándar. | Aceptada |
| D3 | Ejecutivo ↔ Cognitive | Acción ROS 2 **`Think`**, interrumpible. | Aceptada |
| D4 | Reparto de cómputo | Jetson y Mini PC controlan el robot en tiempo real. El servidor solo ejecuta lo pesado: LLM grande y RAG completo. **Se mantiene un RAG local mínimo** (observación). | Aceptada |
| D5 | Uso del servidor | `cognitive` en el robot → HTTP al servidor, con respaldo local. **La memoria de conversación pasa a ser del robot** (observación, cambia mi diseño de `llm-engine`). | Aceptada |
| D6 | Transporte WiFi | `zenoh-bridge-ros2dds` ahora; `rmw_zenoh` al migrar a Jazzy. | Aceptada |
| D7 | Grabación | rosbag2 + MCAP con store-and-forward. Sin NVMe → ver **D17**. | Aceptada |
| D8 | DuckDB en el robot | Descartada. | Descartada |
| D9 | Zenoh para postprocesado | Descartado. Zenoh solo como transporte (D6). | Descartada |
| D10 | Dashboard | **Foxglove** (licencia académica gratuita). InfluxDB descartado. Grafana solo sobre el *lake* y solo si hace falta. | Aceptada |
| D11 | Pipeline IA | MCAP → ingesta en el servidor → Parquet → DuckDB/Polars → PyTorch. | Aceptada |
| D12 | Trazas | Traza por turno + `/udito/meta` + reloj sincronizado + data card. Se añade **traza del BT** y `/diagnostics` (D14). | Aceptada |
| D13 | Privacidad | Clases C0/C1/C2. **Comité de ética + DPD** antes de grabar a participantes. | Aceptada |
| **D14** | **Modelo de arquitectura** | Híbrida en capas con **habilidades + ejecutivo BT + deliberativo acotado** y **cuatro planos transversales** (seguridad, modelo del mundo, modos y salud, observabilidad). | **Pendiente** |
| **D15** | **Red y seguridad (WiFi compartida)** | Túnel **WireGuard** robot↔servidor. Las conexiones las abre siempre el robot. Autenticación en `llm-engine`. | **Pendiente** |
| **D16** | **Motor de BT y lenguajes** | **py_trees + py_trees_ros** (medido: tick < 0,5 ms con 145 nodos). Todo lo que programamos, en Python. C++ solo para firmware, *plugins* de Nav2, `ros2_control` y paquetes estándar que solo se configuran. | **Pendiente** |
| D17 | Dónde se graba | Grabador en el **SSD del Mini PC**. Se compra un **NVMe para la Jetson** (sistema, modelos, JetPack 7.2). Nada en la microSD. | Aceptada |
| **D18** | **Activación sin wakeword** | No usar VAD continua en público. «Mantén para hablar» en sesiones supervisadas; **activación por atención** (presencia + DOA + VAD) como objetivo. | **Pendiente** |
| **D19** | **Migración a Jazzy** | Viable de forma nativa en la Orin Nano con **JetPack 7.2 (Ubuntu 24.04)**. Se mantiene enero de 2027, con condiciones previas. | **Pendiente** |

---

## 1. Requisitos y restricciones de partida

1. **Integración nativa en ROS 2.** Todo componente del robot es un nodo, o queda detrás de uno.
2. **Autonomía embarcada.** El robot debe funcionar completo **sin red**: Jetson Orin Nano más un Mini PC.
3. **Servidor opcional por WiFi** para tener más cómputo. Es una *mejora*, nunca una dependencia: si se cae la WiFi, el robot degrada y no se para.
4. **Trazas para evaluación externa.** Los datos deben poder reconstruir cada interacción, compararse entre versiones del software y entregarse a investigadores de la universidad.
5. **Plataforma:** ROS 2 Humble hoy (JetPack 6, Ubuntu 22.04). Humble termina soporte en mayo de 2027; **la migración a Jazzy está prevista para enero de 2027** (D19).
6. **Datos personales.** El robot capta voz y texto de personas reales en la universidad (D13).
7. **Datos del entorno** (respuestas del equipo, v1):

   | Recurso | Valor |
   |---------|-------|
   | Disco | **Sin NVMe** en la Jetson (arranca de microSD) |
   | Uso | **1–2 h de sesión al día** |
   | Servidor | Core i9-10900K, 32 GB de RAM, **Quadro RTX 4000 (8 GB de VRAM, Turing)** |
   | Red | **WiFi de la universidad**: compartida, con usuarios restringidos |

---

## 2. Qué tenemos hoy

### 2.1 En `develop` conviven **tres caminos de diálogo**

| Camino | Dónde | Estado | Problema |
|--------|-------|--------|----------|
| A. `./UDITO` (un solo proceso Python) | `03_ADAPTERS/robot-udit-physical/udito_standalone.py` (+ `llm_fallback.py`, opcional) | **Producción actual** en la Jetson | No es ROS: no genera bags ni trazas estándar. |
| B. ROS legado con `ComAct` | `05_ROS2/.../multimodal_expression`, `speech_to_text`, `llm_dialog_manager` | Sin verificar con `colcon build` en la Jetson | Rutas fijas `/home/udito/OneDrive/...`. `llm_dialog_manager` llama a `com_act_server` **directamente**, saltándose cualquier ejecutivo. |
| C. 3T de Danilo | `05_ROS2/.../udito_ros` (rama sin mergear) | Funciona en el módulo 1 (órdenes por voz, sin RAG) | Ver §2.2. |

**Tres caminos son demasiados.** El código de C es el punto de partida; A se congela cuando C alcance paridad; B se archiva.

### 2.2 La rama de Danilo (`feature/ros2-voice-orchestrator`): evaluación crítica

**Qué aporta:** el paquete `udito_ros` con los nodos `udito_stt` (Whisper), `udito_tts` (Piper), `udito_cc` (orquestador con `intents.yaml`), `udito_cognitive` (RAG o respuestas fijas), `udito_console` y `body_example`. Incluye el documento `docs/Arquitectura_3T_UDITO_distribucion_v1.md` con el reparto Jetson / Mini PC. También borra 62 ficheros (Dockerfiles de los servicios, `wakeword-engine`, partes de `rag-engine`, `example/`, scripts).

**A favor**

- Respeta la regla de la arquitectura v2: las órdenes bajan, los datos suben y solo el C.C. manda a los actuadores. Es el único de los tres caminos que la cumple.
- `intents.yaml` está guiado por datos: añadir una orden no exige tocar código.
- No duplica los motores (Whisper, Piper, RAG): los importa desde `01_SERVICES/`.
- Decisiones prácticas buenas: modo «mantén para hablar», el C.C. cierra el micrófono mientras el robot habla, consola de operador y un ejemplo listo para quien haga el cuerpo.
- El reparto físico es sensato: el C.C. va junto a los motores.

**En contra / riesgos**

1. **Todo viaja como `std_msgs/String` con JSON.** No hay contrato verificable, los bags son opacos y no existe versión de esquema. → D2.
2. **No se puede reconstruir un turno.** El texto del STT, la consulta a Cognitive y la orden de TTS llevan identificadores distintos y sin enlazar. El único `stamp` es `time.time()` en `/udito/intent`.
3. **Respuestas obsoletas.** `_on_answer` no comprueba el `id`, y no hay timeout ni cancelación. → D3.
4. **Seguridad del movimiento.** `follow`, `go_to` y `rotate` se lanzan a partir de una coincidencia aproximada (`difflib` ≥ 0.72) sobre la salida del STT, sin confirmación ni supervisor. → D14, plano de seguridad.
5. **El C.C. es monolítico.** Es un `if/else` sobre intenciones: no puede hacer dos cosas a la vez (mirar a quien habla *mientras* habla) ni se puede interrumpir de forma estructurada. → D14.
6. **Memoria de la Jetson.** Whisper, Piper, RAG y un LLM local comparten 8 GB unificados y nadie ha medido el total.
7. **Borrados masivos mezclados con la feature.** Nada en `develop` fuera de `_archive` usa lo borrado (comprobado con `git grep`), pero deberían ir en un commit `chore` aparte. La retirada del wakeword queda confirmada por el equipo (D18).
8. **El contrato de topics del código no coincide con el del doc v1.** Se resuelve con `robita_interfaces` (D2).

### 2.3 Cómo encaja `cognitive_node` con `llm-engine` y `llm_dialog_manager`

- **`llm-engine`** sigue siendo un servicio HTTP que `cognitive` usa como *backend*. La frontera ROS es `cognitive`.
- **`llm_dialog_manager` se retira como nodo.** Decide qué decir *y* manda a `ComAct`, rompiendo la regla de un único ejecutivo. Su `router.py` y su `llm_client.py` pasan a `cognitive`.
- **`llm_fallback.py`** se mantiene mientras `./UDITO` sea producción.
- La regla de `llm_fallback` («las preguntas de UDIT van a RAG, el LLM solo responde las generales, y si falla se usa la respuesta de RAG») es la lógica de enrutado de `cognitive`.

---

## 3. Decisiones D1–D13

### D1 — Esqueleto ROS 2 · *Aceptada (rehecha en v1)*

| Opción | A favor | En contra |
|--------|---------|-----------|
| a) 3T `udito_ros` (Danilo) | Cumple la regla de la v2. Funciona hoy. | Contrato débil (D2/D3). Ejecutivo `if/else`. |
| b) ROS legado + `ComAct` + `llm_dialog_manager` | Mensajes tipados. | Rutas fijas. Sin ejecutivo real. Nadie lo mantiene. |
| c) Seguir con `./UDITO` | Funciona en el robot. | No es ROS. Sin trazas estándar. |

> **Decisión del equipo:** «Hay que evaluar otras posibles arquitecturas y probablemente crearnos una propia de control del robot. 3T es un poco antigua y convendría ver otras opciones hibridas más modernas orientadas a software embarcado.»

**Observación.** Estoy de acuerdo en que la propuesta actual es floja, pero conviene precisar **por qué**. La separación en capas deliberativa / ejecutiva / reactiva no es lo que falla: es el esqueleto de casi todas las arquitecturas híbridas actuales, incluida **Nav2** (navegador BT = ejecutivo, planificadores = deliberativo, controladores = reactivo). Lo que falla es lo que la propuesta de Danilo **no** tiene: un modelo de comportamiento, concurrencia, un modelo de personas, seguridad por construcción, gestión de modos y observabilidad. "Crear una propia" debe significar **componer piezas estándar de ROS 2 con contratos nuestros**, no inventar un framework. Desarrollado en **§4 y D14**.

### D2 — Contrato de mensajes tipado · *Aceptada*

Interfaces propias con `std_msgs/Header`, `session_id` y `turn_id`. Mínimo inicial: `Utterance.msg`, `TurnTrace.msg` y `Think.action` (D3).

> **Decisión del equipo:** «Correcto interfaces propias en una paquete específco de ROS.» + (pregunta 5) «se va a llamar robita_interfaces.»

**Observación.**

1. Prefijo `robita_` para el paquete y **namespace `/udito/` para los topics**: el robot es UDITO; el laboratorio podrá tener otros robots con las mismas interfaces.
2. **No reinventar lo que ya es estándar.** Para la representación de personas, voces y caras existe **ROS4HRI (REP-155, paquete `hri_msgs`, disponible en Humble)**. Antes de cerrar `Utterance.msg`, hay que comprobar si `hri_msgs` (voces y habla) cubre el caso. Si lo cubre, `robita_interfaces` solo añade lo que falta (`session_id`, `turn_id`). Alinearse con ROS4HRI hace que nuestros datasets sean comparables con los de otros laboratorios de HRI, lo que conviene a la evaluación externa.

### D3 — Interfaz ejecutivo ↔ Cognitive · *Aceptada*

```
# robita_interfaces/action/Think.action
string session_id
string turn_id
string text
---
string text
string emotion
string source        # basic_qa | rag_local | rag_server | llm_local | llm_server | fallback
string model_id
float32 latency_ms
---
string partial_text  # feedback: frase completa lista para TTS
```

> **Decisión del equipo:** «Si correcto, acción Think pensada para poder ser interrumpida.»

**Observación.** Que sea interrumpible exige más que declarar una acción: el servidor de `Think` debe **propagar la cancelación** a la llamada HTTP en curso (cerrar el stream de `llm-engine`). Si no lo hace, el servidor sigue generando y ocupando la única GPU. Esto va en el criterio de salida de F2.

### D4 — Reparto de cómputo · *Aceptada*

> **Decisión del equipo:** «Correcto despliegue de solo lo pesado al servidor (modelo LLM grande y RAG/Vectorización completo). Jetson y mini-pc controlan el robot en tiempo real.»

**Observaciones.**

1. **El RAG completo puede ir al servidor, pero el robot debe conservar un RAG local mínimo** (respuestas de UDIT y `basic_qa`). Si no, sin WiFi el robot no sabe responder sobre la universidad, que es su función principal, y se incumple el requisito 2. Hay dos índices, así que la **versión de cada índice debe registrarse** en `/udito/meta` y en la traza (`source = rag_local | rag_server`).
2. **Límites del servidor.** La Quadro RTX 4000 tiene **8 GB de VRAM** y es Turing (sin bf16). El techo práctico es un modelo de **7–8B cuantizado a 4 bits** (por ejemplo `qwen2.5:7b-instruct`) más los *embeddings* y el *reranker* del RAG, todo compartiendo una sola GPU. Los modelos de 14B o más ya no caben enteros en VRAM. Con un único robot es suficiente; con varios robots o evaluaciones en paralelo habrá colas.
3. Los 8 GB del servidor son un límite real para la idea de un LLM como planificador (§4.2-f): los modelos pequeños hacen *tool calling* de forma poco fiable.

### D5 — Cómo usa el robot el servidor · *Aceptada*

`cognitive` vive en el robot y llama a `llm-engine` en el servidor por HTTP, con timeout y respaldo local.

> **Decisión del equipo:** «Correcto vamos con a)»

**Observación (autocrítica de `llm-engine`).** El diseño actual de `llm-engine` (`ARCHITECTURE.md` §2) hace que **el servidor sea el dueño de la memoria de conversación** (Redis) y que el nivel local no tenga estado. Eso **contradice el requisito 2**: si la WiFi cae a mitad de una conversación, el robot pierde el contexto. Hay que cambiarlo:

- La **memoria de conversación vive en `cognitive`**, en el robot. Es la fuente de verdad.
- Se envía como contexto en cada petición.
- El servidor pasa a ser **sin estado** respecto al diálogo; Redis queda, como mucho, de caché.

Además, el robot pasa a ser el único lugar donde están las transcripciones (datos C1), lo que facilita cumplir D13.

### D6 — Transporte robot ↔ servidor · *Aceptada*

> **Decisión del equipo:** «De momento el bridge pero si pasamos a Jazzy montamos rmw_zenoh.»

**Observaciones.**

1. `rmw_zenoh` necesita un **router Zenoh** (`zenohd`) en marcha. En una WiFi compartida, el router debe ir en el servidor y el robot conectarse como cliente (conexión saliente, ver D15).
2. Cambiar el RMW afecta también al bucle de control entre la Jetson y el Mini PC, que va por Ethernet. Antes de adoptarlo en producción hay que probarlo con Nav2 y con la grabación.

### D7 — Grabación: rosbag2 + MCAP · *Aceptada*

rosbag2 con almacenamiento MCAP, en el robot, con *store-and-forward* hacia el servidor. Perfil con lista blanca de topics, división por tiempo o tamaño y compresión zstd.

> **Decisión del equipo:** «Ok vamos rosbag2 y store-and-forward.»

**Observación.** Sin NVMe, **dónde** se graba es una decisión en sí misma → **D17**.

### D8 — DuckDB embebida en el robot · *Descartada*

> **Decisión del equipo:** «Descartada»

### D9 — "Zenoh para postprocesado" · *Descartada*

> **Decisión del equipo:** «Ok, lo indicado en D6»

### D10 — Dashboard · *Aceptada*

Foxglove para el trabajo en vivo y sobre MCAP. InfluxDB descartado. Grafana solo si hace falta un panel de indicadores, y leyendo del *lake*.

> **Decisión del equipo:** «Foxglove parece que tiene una version gratis para investigación: https://foxglove.dev/pricing#:~:text=Academic%20and%20nonprofit»

**Observación.** Correcto. El riesgo de depender de un proveedor es bajo porque los datos quedan en **MCAP, que es un formato abierto**; si cambian las condiciones, la alternativa abierta es Lichtblick. Hay que confirmar si la licencia académica cubre a todos los miembros del equipo y si permite el panel de audio y la conexión remota.

### D11 — Pipeline de datos para IA · *Aceptada*

```
ROBOT                                   SERVIDOR (ingesta y análisis)
rosbag2 (MCAP, zstd)  ──subida por WireGuard──▶  data/raw/<fecha>/<session>.mcap   (inmutable, con checksum)
                                                   │ ingesta (Python: mcap + mcap-ros2-support / rosbags)
                                                   ▼
                                                 data/lake/<tabla>/date=…/session=…/*.parquet
                                                   │  tablas: sessions, turns, utterances, bt_transitions,
                                                   │          events, diagnostics
                                                   ▼
                                                 DuckDB / Polars  ──▶ notebooks, informes, PyTorch Dataset
                                                   ▼
                                                 datasets/<nombre>-v<N>/ (Parquet) + data card ──▶ investigadores
```

> **Decisión del equipo:** «Adoptar los cambios si se ajustan a las decisiones.» + (pregunta 2) Parquet como formato de entrega.

**Observación.** Ajustado a D15 (subida por el túnel), D17 (origen de la grabación) y D14 (tabla nueva `bt_transitions`). El borrado en el robot se hace **solo después de verificar el checksum** en el servidor.

### D12 — Trazas para evaluación externa · *Aceptada*

1. **`/udito/trace/turn`** (`robita_interfaces/TurnTrace`): uno por turno, con textos, ruta, origen, modelo, latencias por etapa, interrupción y error.
2. **`/udito/meta`** (*transient local*): `git_sha`, versiones de modelos, versión de los índices RAG, hash de la configuración y `robot_id`.
3. **Reloj sincronizado** con chrony entre la Jetson, el Mini PC y el servidor.
4. **Data card** por dataset.
5. `session_id` y `turn_id` se propagan a `llm-engine`.

> **Decisión del equipo:** «vamos con la propuesta de traza por turnos.»

**Observación.** Con el ejecutivo en BT (D14/D16) se añaden dos fuentes **casi gratis**:

- Las **transiciones del árbol** (qué comportamiento estaba activo y por qué cambió).
- **`/diagnostics`** (`diagnostic_updater`, estándar de ROS) para la salud de cada nodo.

Con las tres fuentes, el evaluador puede responder no solo «qué dijo el robot» sino también «qué estaba haciendo y en qué estado estaba».

### D13 — Privacidad (RGPD) · *Aceptada*

| Clase | Contenido | Por defecto | Hacia los investigadores |
|-------|-----------|-------------|--------------------------|
| C0 Telemetría | Latencias, estados, BT, diagnósticos | Siempre se graba | ✅ |
| C1 Texto | Transcripciones y respuestas | Se graba | ⚠️ Pseudonimizado y revisado |
| C2 Crudo | Audio, imagen | **No se graba**, salvo sesión con consentimiento (un *flag* del perfil de grabación) | Solo con aprobación específica |

> **Decisión del equipo:** «Hay que evaluar y pasar por el comite de ética de la universidad.» + (pregunta 2) «El audio puede ser necesario, pero no lo sabemos todavía.»

**Observaciones.**

1. **El comité de ética y el DPD son dos validaciones distintas y se necesitan las dos.** El comité evalúa la investigación con personas; el DPD, el tratamiento de datos (base legal, información, retención y probablemente una evaluación de impacto). Una no sustituye a la otra.
2. **El audio debe quedar diseñado desde ya aunque esté apagado.** El topic de audio existe y se puede grabar activando el *flag*. Así, si el comité lo aprueba, habilitarlo es un cambio de configuración y no de código, y la solicitud al comité puede describir exactamente qué se grabaría.
3. Retirar el wakeword **empeora** la privacidad si se sustituye por VAD continua: el robot transcribiría a cualquiera que pase cerca. → D18.

---

## 4. Modelo de arquitectura: más allá del 3T (D14)

### 4.1 Diagnóstico: qué le falta al 3T actual

| # | Carencia | Consecuencia en UDITO |
|---|----------|------------------------|
| 1 | **Sin modelo de comportamiento.** El ejecutivo es `if/else` sobre intenciones. | Cada comportamiento nuevo (seguir, atender, presentarse) toca código del C.C. No hay forma de interrumpir de manera estructurada. |
| 2 | **Sin concurrencia.** Una tubería en serie: oír → decidir → hablar. | Un robot social tiene que mirar a quien habla, parpadear y mantener la atención *mientras* habla o piensa. |
| 3 | **Sin modelo de personas ni del mundo.** | No sabe cuánta gente hay, quién habla ni si alguien le está prestando atención. |
| 4 | **Seguridad por convención** («solo el C.C. manda»). | Nada impide *técnicamente* que un nodo publique en `/cmd_vel`. Un «para» por voz llega en segundos (latencia de Whisper), así que **no es un mecanismo de seguridad**. |
| 5 | **Sin gestión de modos ni de salud.** | Ante una caída de la WiFi o de un nodo, el comportamiento no está definido. |
| 6 | **Sin observabilidad de diseño.** | Las trazas son un añadido posterior (D12). |
| 7 | **Papel del LLM sin definir.** | O es solo charla, o se le deja decidir acciones sin control. |

### 4.2 Alternativas evaluadas

| Opción | Qué es | A favor | En contra | Veredicto |
|--------|--------|---------|-----------|-----------|
| a) **3T clásico** (la propuesta actual) | Deliberativo / ejecutivo / reactivo con ejecutivo hecho a mano | Simple y conocido. | Carencias 1–7. | ⚠️ El esqueleto sí, la implementación no. |
| b) **Subsumción / basada en comportamientos pura** (Brooks) | Capas reactivas que se inhiben entre sí, sin planificación | Muy reactiva y robusta. | No hay sitio para el diálogo ni para la deliberación. | ❌ |
| c) **Máquinas de estados jerárquicas** (SMACH, FlexBE, YASMIN) | El ejecutivo como HSM | Muy legible para **protocolos experimentales con guion**. | Explosión de estados. Interrupciones y concurrencia incómodas. | ❌ como ejecutivo principal. Los protocolos se modelan como subárboles BT. |
| d) **Behavior Trees** como ejecutivo (BT.CPP v4, py_trees) | Árbol reactivo que se reevalúa en cada *tick* | Estándar de facto en ROS 2 (Nav2). Interrumpible, modular y con concurrencia (`Parallel`). Árboles en XML que se editan sin recompilar. Las transiciones se registran y visualizan. | Hay que aprender a modelar en BT. El diálogo largo no encaja directamente y se delega a `Think`. | ✅ |
| e) **Basada en habilidades** (*skill-based*) | Cada capacidad es una habilidad con un contrato uniforme (acción ROS) y un catálogo | Componible, probable por separado y con un catálogo explícito de lo que el robot sabe hacer. | Disciplina en las interfaces. | ✅ en combinación con d): las hojas del árbol son habilidades. |
| f) **LLM como planificador / agente** (estilo ROSA, *tool calling* sobre ROS) | El LLM decide qué acciones ejecutar | Flexible y "moderno". | No determinista, lento, **difícil de evaluar y de certificar como seguro**. Los modelos que caben aquí (1.5B local, 7–8B en el servidor) hacen *tool calling* de forma poco fiable. | ❌ como ejecutivo. ✅ **acotado**: puede *proponer* una habilidad del catálogo, que el ejecutivo valida igual que una orden por voz (fase F5). |
| g) **Arquitecturas cognitivas** (SOAR, ACT-R, CRAM/KnowRob) | Modelos completos de cognición | Modelos de memoria y razonamiento. | Excesivas para el equipo y el hardware. Curva de aprendizaje muy alta. | ❌ Se toma solo la idea de memoria y modelo del mundo. |
| h) **Modelos fundacionales extremo a extremo** (VLA) | Un modelo de percepción a acción | Frontera de investigación. | No caben en este hardware ni son evaluables ni seguros para esta tarea. | ❌ |
| i) **ROS4HRI** (REP-155) | No es una arquitectura: es un **estándar de representación** de personas, caras, cuerpos, voces y nivel de atención (*engagement*) | Interoperable con otros laboratorios de HRI. Paquetes en Humble. Datasets comparables. | Hay que producir esos topics, empezando por voz y presencia. | ✅ para el **plano del modelo del mundo**. |

### 4.3 Propuesta: arquitectura híbrida ROBITA

**Idea:** **cuatro capas** por las que bajan las órdenes y suben los datos, más **cuatro planos transversales** que no dependen de qué comportamiento esté activo. Todo se construye con piezas estándar de ROS 2; lo propio es la composición y los contratos (`robita_interfaces`).

```
             ┌────────────────────────────────────────────────────────────────┐
  CAPA 3     │ DELIBERATIVA — cognitive (acción Think)                        │
  ¿QUÉ?      │ router · basic_qa · RAG local/servidor · LLM local/servidor ·  │
             │ memoria de conversación (en el robot) · [F5: propone habilidad]│
             └───────────────▲──────────────────────────┬─────────────────────┘
                     contexto│                 propuesta│ (texto / habilidad del catálogo)
             ┌───────────────┴──────────────────────────▼─────────────────────┐
  CAPA 2     │ EJECUTIVA — Behavior Tree (py_trees_ros, D16)                  │
  ¿CÓMO,     │ Inactivo → Atención → Conversación (turnos) → Tarea (seguir…)  │
  CUÁNDO?    │ coordinador de expresión (voz + cara + cuello sincronizados)   │
             │ catálogo de órdenes (intents.yaml) · protocolos = subárboles   │
             └───────────────▲──────────────────────────┬─────────────────────┘
             percepción/estado│                  objetivos│ (acciones robita_interfaces / Nav2)
             ┌───────────────┴──────────────────────────▼─────────────────────┐
  CAPA 1     │ HABILIDADES (nodos lifecycle, contrato uniforme)               │
             │ percepción: escuchar (VAD+STT) · DOA · presencia (lidar)       │
             │ acción: decir · expresar · mirar · gesto · navegar (Nav2)      │
             │ reflejos declarados e inhibibles (p. ej. el cuello sigue el DOA)│
             └───────────────▲──────────────────────────┬─────────────────────┘
             ┌───────────────┴──────────────────────────▼─────────────────────┐
  CAPA 0     │ PLATAFORMA — drivers: Arduino (ruedas, cuello, ojos), lidar,   │
             │ audio (ReSpeaker, altavoz), pantalla                           │
             └────────────────────────────────────────────────────────────────┘

  PLANOS TRANSVERSALES (independientes del comportamiento activo)
  ┌──────────────────┬──────────────────────┬────────────────────┬───────────────────────┐
  │ A. SEGURIDAD     │ B. MODELO DEL MUNDO  │ C. MODOS Y SALUD   │ D. OBSERVABILIDAD     │
  │ twist_mux por    │ ROS4HRI: personas,   │ nodos lifecycle    │ TurnTrace · transic.  │
  │ prioridad · Nav2 │ voces, atención      │ modos: COMPLETO /  │ del BT · /diagnostics │
  │ collision_monitor│ estado de sesión     │ LOCAL / DEGRADADO /│ /udito/meta · rosbag2 │
  │ watchdog cmd_vel │ estado del robot     │ SEGURO · latido    │ (MCAP) · chrony       │
  │ seta de emergencia│                     │ del servidor       │                       │
  └──────────────────┴──────────────────────┴────────────────────┴───────────────────────┘
```

**Reglas de la arquitectura** (sustituyen a «solo el C.C. manda»):

1. **Una sola fuente de objetivos por actuador, impuesta técnicamente.** Las velocidades pasan por `twist_mux` con prioridades: emergencia > supervisor > teleoperación > BT/Nav2. Ningún nodo publica directamente al driver.
2. **La seguridad no depende del software de comportamiento.** El plano A funciona aunque el BT, `cognitive` o la WiFi fallen:
   - `collision_monitor` de Nav2 con el lidar;
   - límite de velocidad;
   - watchdog: sin órdenes recientes, parada;
   - **seta de emergencia física** (por instalar: hasta que esté montada, **no se activan órdenes de movimiento autónomo** —`follow`, `go_to`, `rotate`— en sesiones con público).
   El «para» por voz se mantiene como comodidad, **no como medida de seguridad**.
3. **El deliberativo propone y el ejecutivo dispone.** `cognitive` nunca ordena a una habilidad. Devuelve texto y, en F5, como mucho una habilidad del catálogo, que el BT valida con las mismas reglas que una orden por voz.
4. **Los reflejos están permitidos en la capa 1**, siempre que se declaren y el BT pueda inhibirlos. Ejemplo: el cuello sigue el DOA durante la conversación y el BT lo inhibe mientras navega. Esto responde a la pregunta abierta 2 del doc v1 de Danilo.
5. **Los modos son explícitos.**
   - COMPLETO (con servidor) → LOCAL (sin servidor) → DEGRADADO (falla una habilidad no crítica) → SEGURO (falla algo crítico: parada y aviso).
   - Cada cambio de modo se publica y queda en la traza.
6. **Todo comportamiento es observable por construcción.** Si un turno no genera su `TurnTrace` y sus transiciones de árbol, el turno no está terminado.

**Despliegue:**

| Máquina | Capa / plano | Nodos |
|---------|--------------|-------|
| **Jetson Orin Nano** | Capas 1 y 3 | Habilidades de voz (VAD/STT, TTS), cara, DOA; `cognitive` (basic_qa, RAG local, LLM pequeño); memoria de conversación |
| **Mini PC** | Capas 0, 1 y 2; planos A, C y D | BT ejecutivo, `twist_mux`, `collision_monitor`, Nav2, base, cuello y ojos, gestor de modos, **grabador rosbag2** (D17) |
| **Servidor** | Capa 3 (opcional) y plano D | `llm-engine` (7–8B), RAG completo, ingesta y *lake*, Foxglove |

### 4.4 Crítica de esta propuesta

| Riesgo | Mitigación |
|--------|------------|
| **Complejidad excesiva para un equipo pequeño.** Cuatro capas y cuatro planos son muchos nodos y conceptos. | Por fases (§5). El mínimo viable es BT + habilidades + `twist_mux`/watchdog + traza. ROS4HRI, modos y LLM proponente llegan después. |
| **Un BT en Python** puede bloquearse por una hoja mal escrita, y sus herramientas visuales son más pobres que Groot2. | Hojas no bloqueantes como regla de revisión, instantáneas del árbol en el bag y criterio de salida medible (D16.4). |
| **Más procesos en la Jetson**, cada uno con su propio intérprete de Python. | Las habilidades de voz se agrupan en un proceso con componentes, o se comparten modelos. Hay que medir la memoria en F1 (riesgo 6 de §2.2). |
| **"Arquitectura propia" puede acabar en algo inventado aquí que nadie más entiende.** | Solo se inventan los contratos. Todo lo demás es estándar documentado: py_trees_ros, Nav2, `twist_mux`, ROS4HRI, `diagnostic_updater`, lifecycle. |
| **Modelar diálogo en BT** puede volverse incómodo. | El BT solo gestiona los turnos (quién habla y cuándo se interrumpe). El contenido del diálogo vive en `cognitive`. |

**Veredicto:** ✅ adoptar como arquitectura objetivo. *Pendiente* de revisión del equipo (Danilo en especial, porque cambia su C.C.).

---

## 5. Decisiones nuevas D15–D19

### D15 — Red y seguridad en la WiFi compartida · *Pendiente*

Con una WiFi compartida (pregunta 3) aparecen problemas que la v0 no contemplaba:

- **`llm-engine` no tiene autenticación**: cualquier usuario de la red podría usar la GPU.
- **Las transcripciones (C1) viajarían en claro** por una red compartida, lo que es un problema de RGPD.
- Las redes corporativas suelen **aislar a los clientes y bloquear el multicast**: DDS sería imposible, y Zenoh solo funciona si el robot inicia la conexión.

| Opción | A favor | En contra |
|--------|---------|-----------|
| Puertos abiertos + clave de API | Simple. | Tráfico en claro salvo que se añada TLS. Hay que pedir puertos a TI. |
| TLS/mTLS en cada servicio (HTTP y Zenoh) | Estándar. | Hay que gestionar certificados en cada servicio. |
| **Túnel WireGuard robot↔servidor** (o Tailscale/Headscale) | **Un único mecanismo** cifra y autentica todo: HTTP, Zenoh, subida de MCAP, SSH. Direcciones estables. El robot inicia la conexión, así que el aislamiento de clientes no afecta. | Una pieza de infraestructura más. Hay que confirmar con TI que se permite UDP saliente. |

**Veredicto:** ✅ WireGuard, más una **clave de API en `llm-engine`** como defensa adicional. Regla: **todas las conexiones las abre el robot**; el servidor nunca inicia contacto.

### D16 — Motor de Behavior Trees y reparto Python / C++ · *Pendiente (recomendación revisada en v1.1)*

> **Petición del equipo:** «evalúa el rendimiento necesario y qué control debe manejarse por medio de ellos por si es viable migrarlos a Python por tema de homogeneizar el lenguaje de programación; si no es buena opción documentamos qué debe ir en C++ y qué no, aunque parece que no es mala opción BT.CPP y habilidades en Python.»

#### D16.1 Qué controla el BT y qué no

El error que hay que evitar es meter en el BT bucles que no le corresponden. **El BT de interacción solo toma decisiones discretas a escala humana**: qué comportamiento está activo, cuándo empieza o se interrumpe un turno y qué habilidad se lanza o se cancela. Todo bucle con requisitos de tiempo más estrictos vive en otro sitio:

| Bucle / reacción | Frecuencia o latencia | Dónde vive | Lenguaje | ¿Pasa por el BT? |
|------------------|-----------------------|------------|----------|------------------|
| PWM y encoders de motores, servos | ≥ 1 kHz | Firmware Arduino | C++ (Arduino) | No |
| **Seta de emergencia** | Inmediata | **Hardware**: corta la potencia de los motores | — | **No** |
| Prioridad de velocidades y watchdog | 20–50 Hz, < 50 ms | `twist_mux` (con *timeout* por entrada) | C++ (paquete ROS, solo configuración) | No |
| Parada por obstáculo | 20 Hz, < 100 ms | Nav2 `collision_monitor` + lidar | C++ (Nav2, solo configuración) | No |
| Navegación: controlador / planificador / BT interno | 20 Hz / 1 Hz / 100 Hz | Nav2 | C++ (Nav2) | Solo la **orden** (`NavigateToPose`) |
| Velocidad → serie, odometría | 20–50 Hz | Driver de la base | Python (hoy) | No |
| Tramas de audio, VAD | 10–30 ms por trama | Habilidad de voz | Python + librerías nativas | No |
| **Interrumpir al robot mientras habla** (*barge-in*) | < 200 ms | **Reflejo** en la habilidad de voz (para el TTS y avisa) | Python | Se le **informa** |
| Cuello que sigue el DOA | 10–20 Hz | Reflejo en la habilidad de cabeza, inhibible | Python | Lo activa o inhibe |
| Animación de cara y ojos | 30 fps | Habilidad de cara | Python | Solo cambia la expresión |
| **BT de interacción** | **Tick a 10–20 Hz; reacción ≤ 1–2 ticks (50–200 ms)** | Mini PC | **a decidir** | — |
| Cognitive (`Think`) | 0,5–10 s | Jetson / servidor | Python | Acción lanzada desde el BT |

**Regla derivada:** toda reacción que necesite menos de unos 100 ms o funcionar sin el BT es un **reflejo de la habilidad** o va al **plano de seguridad**, nunca al árbol. Con esta regla, el BT no tiene requisitos de tiempo real.

#### D16.2 Rendimiento necesario y medido

- **Requisito:** árbol de 100–200 nodos, tick a 20 Hz (50 ms de presupuesto) y hojas **no bloqueantes**, es decir, clientes de acción asíncronos.
- **Medición** (`docs/bench/bt_tick_bench.py`): py_trees 2.6.0 sobre Python 3.11, árbol de interacción realista de **145 nodos**. El árbol tiene una rama paralela de atención, una rama de prioridades con modo seguro, 25 órdenes del catálogo y una secuencia de conversación, con datos de pizarra cambiando en cada tick. 20 000 ticks:

  | Máquina | Media | p50 | p99 | Máx. | CPU a 20 Hz |
  |---------|-------|-----|-----|------|-------------|
  | i9-13900H (portátil de desarrollo) | 316 µs | 340 µs | 477 µs | 1,3 ms | 0,6 % de un núcleo |
  | Jetson Orin Nano / Mini PC | *pendiente de medir con el mismo script* | | | | estimación: 3–5× más lento → p99 ≈ 1,5–2,5 ms |

- **Conclusión:** incluso en el peor caso estimado, el tick en Python usa **menos del 5 % del presupuesto**. BT.CPP sería entre 10 y 50 veces más rápido, pero **esa diferencia no se nota a 20 Hz**.
- **Lo que el benchmark no mide** es `rclpy`, que sí puede ser el cuello de botella real de un nodo Python: el *executor* es lento y además está el GIL. Se evita así:
  1. el proceso del BT **no se suscribe a topics de alta frecuencia** (audio, scans del lidar). Las habilidades los convierten en eventos de baja frecuencia (`Utterance`, cambios de atención, DOA a ≤ 10 Hz);
  2. ninguna hoja hace trabajo bloqueante ni llamadas síncronas;
  3. el tick va en un *timer* del mismo nodo.

#### D16.3 Comparación (con correcciones a la v1)

Dos argumentos de la v1 a favor de BT.CPP **eran más débiles de lo que parecían**:

- *«Una sola tecnología de BT con Nav2».* El BT de Nav2 es **interno** a `bt_navigator`. Nuestro ejecutivo habla con Nav2 por la acción `NavigateToPose`, y eso se hace igual desde cualquier motor. Solo haría falta C++ si escribiéramos *plugins* para el BT de Nav2, y eso es independiente de qué motor usemos para la interacción.
- *«Solo unas pocas hojas en C++».* En BT.CPP **toda condición, decorador o acción propia es C++**. El lenguaje de *scripting* de la v4 cubre condiciones simples sobre la pizarra, pero nada más. En la práctica, **toda la lógica del ejecutivo estaría en C++**, no solo unos *wrappers*.

| Criterio | BT.CPP v4 + BehaviorTree.ROS2 | py_trees + py_trees_ros |
|----------|-------------------------------|-------------------------|
| Lenguaje | Hojas y condiciones en C++. Árbol en XML. | **Todo en Python**, como las habilidades y `cognitive`. |
| Rendimiento | De sobra. | **De sobra** (D16.2). |
| Observabilidad en el MCAP (D12) | Groot2 usa ZMQ y los *loggers* escriben a fichero. Para tener las transiciones en el bag hay que escribir un *logger* propio en C++. | **Publica instantáneas del árbol como mensajes ROS**: entran solas en el bag. |
| Herramientas visuales | **Groot2**: editor y monitor muy buenos. Algunas funciones son PRO (por confirmar). | `py_trees_ros_viewer` y exportación a *dot*. Mucho más modestas. |
| Definición del árbol | XML: se edita sin recompilar, pero solo con nodos ya registrados en C++. | Código Python: se edita sin compilar. |
| Pizarra | Puertos tipados. | Claves con control de acceso (lectura/escritura), sin tipos. |
| Comunidad y mantenimiento | **Grande**: Nav2, industria. | Más pequeña. Paquetes para Humble y Jazzy disponibles. |
| Enlaces Python de BT.CPP | Hay una propuesta abierta (`pybt`, PR #1143, 2026) **sin publicar**. No es opción hoy. | — |

#### D16.4 Veredicto

✅ **py_trees + py_trees_ros para el ejecutivo de interacción.** Es viable en rendimiento con margen amplio, homogeneiza el lenguaje y mejora la observabilidad. Esto **cambia la inclinación inicial** («BT.CPP + habilidades en Python»): esa opción no es mala, pero sus dos ventajas principales pesan poco para nosotros y su coste real es tener toda la lógica del ejecutivo en C++.

**Condiciones y salvaguardas:**

1. **Hojas no bloqueantes** (regla de revisión de código). Una hoja bloqueante congela todo el árbol.
2. **El árbol solo conoce `robita_interfaces`.** Las hojas son envoltorios finos de las acciones y topics. Si algún día hay que pasar a BT.CPP (o salen los enlaces `pybt`), lo que se reescribe son las hojas, no las habilidades.
3. **Criterio de salida:** si el p99 del tick en el Mini PC supera **10 ms**, o el árbol pasa de unos **500 nodos**, se reevalúa.
4. Las herramientas visuales son peores; se compensa con las instantáneas en Foxglove y la exportación a *dot*.

#### D16.5 Qué va en C++ y qué en Python

| Va en **C++** (obligatorio u off-the-shelf) | Motivo |
|---------------------------------------------|--------|
| Firmware Arduino (base, cuello, ojos) | Plataforma. |
| `twist_mux`, Nav2 (incluido `collision_monitor`), rosbag2 | Paquetes estándar: **solo se configuran, no se programan**. |
| *Plugins* de Nav2 que escribamos (nodos del BT de Nav2, capas de *costmap* como una capa social o de proxemia, controladores) | `pluginlib` exige C++. |
| `ros2_control` *hardware interface* de la base, si se adopta | Exige C++. |
| Un nodo de seguridad propio, **si** hiciera falta más allá de configurar los anteriores | Comportamiento sin pausas de recolección de basura y más fácil de revisar. Preferible no necesitarlo. |
| Percepción de alta frecuencia que Python no aguante (nubes de puntos a 30 Hz, etc.) | Rendimiento. Hoy no hay ninguna: el lidar LD19 a 10 Hz se procesa bien con numpy. |

| Va en **Python** | |
|-------------------|-|
| **Ejecutivo BT de interacción** (py_trees_ros) | |
| Todas las habilidades: voz, cara, cabeza, presencia, expresión, driver de la base | |
| `cognitive` y `llm-engine` | |
| Ingesta MCAP → Parquet y análisis | |
| `robita_interfaces` | Ficheros `.msg/.action` (IDL). Se compila con `ament_cmake`, pero no tiene código C++ propio. |

**Pregunta para Danilo:** ¿de acuerdo con py_trees como ejecutivo? Su `udito_cc` actual se convierte casi directamente en el primer árbol: el catálogo de `intents.yaml` pasa a ser el selector de órdenes.

### D17 — Dónde se graba sin NVMe · *Pendiente*

Volumen estimado para 1–2 h al día: C0 + C1 (telemetría, texto, BT, diagnósticos) **< 50 MB/día**. Audio mono a 16 kHz **≈ 115 MB/h**; los 4–6 canales crudos del ReSpeaker, **4–6 veces más**. El volumen no es el problema. **El problema es la microSD:**

- Las escrituras sostenidas provocan **bloqueos de E/S que afectan en tiempo real** a Whisper y Piper en la Jetson.
- Las microSD se desgastan.
- Una SD corrupta deja al robot sin sistema.

| Opción | A favor | En contra |
|--------|---------|-----------|
| Grabar en la microSD de la Jetson | Nada que comprar. | Bloqueos, desgaste y riesgo para el sistema. ❌ |
| **Grabador en el Mini PC (SSD)** | Los topics llegan por DDS sobre Ethernet. Saca la escritura de la Jetson. El Mini PC además es donde está el ejecutivo. | Depende de que el Mini PC tenga un SSD con espacio (**por confirmar**). El audio crudo cruza la Ethernet, pero son ~32 KB/s por canal: despreciable. |
| **Añadir un NVMe a la Jetson** (ranura M.2 del kit de desarrollo, ~30–60 €) | Mejora todo el sistema: arranque, *swap* y modelos. Además, **JetPack 7.2 ya no ofrece imagen para SD** (se instala desde USB), así que la migración a Jazzy (D19) lo pide igualmente. | Un pequeño gasto y reinstalar. |

**Veredicto:** ✅ **las dos**: grabar en el Mini PC ya, y comprar el NVMe antes de la migración a Jazzy.

> **Decisión del equipo (v1.1):** el Mini PC tiene SSD; se compra un NVMe para la Jetson. → **Aceptada.** El grabador rosbag2 corre en el Mini PC. El NVMe de la Jetson se usa para sistema, modelos y *swap*, no para grabar.

### D18 — Activación sin wakeword · *Pendiente*

> **Decisión del equipo (pregunta 4):** «De momento si que se elimina.»

**Observación:** retirar el wakeword deja dos opciones, y ninguna sirve sola en un uso público:

| Opción | A favor | En contra |
|--------|---------|-----------|
| «Mantén para hablar» (consola) | Sin falsos disparos. Privacidad máxima. | **Necesita un operador**: solo vale para sesiones supervisadas. |
| VAD continua | Natural. | **Transcribe a cualquiera que hable cerca** (problema de RGPD y ante el comité de ética). Falsos disparos. Gasta CPU con Whisper sin parar. |
| **Activación por atención** (plano B): presencia (lidar) + persona orientada o cercana + DOA + VAD | Natural y acotada a quien interactúa. Es un indicador de HRI que interesa medir. | Hay que desarrollarla (F4). |

**Veredicto:** ✅ «mantén para hablar» en las sesiones supervisadas actuales. ❌ VAD continua en público. ✅ Activación por atención como objetivo (F4). Si antes de F4 hace falta funcionar sin operador, **reconsiderar el wakeword**: es la opción más barata y la mejor para la privacidad.

### D19 — Migración a Jazzy · *Pendiente*

> **Decisión del equipo (pregunta 6):** «Si, pero hay que evaluar si se puede montar en ubuntu 24.04 o hay que subir de version. Plan para enero de 2027.»

**Hecho verificado:** **JetPack 7.2 (Jetson Linux 39.2) añade soporte para la familia Orin con Ubuntu 24.04.** Jazzy puede ir **de forma nativa** en la Orin Nano, sin contenedores ni cambio de hardware. Condiciones:

- Ya **no hay imagen para SD**: se instala desde una ISO en USB (refuerza D17).
- Requiere el firmware UEFI de la generación JetPack 6 en el kit.
- Implica **reinstalar desde cero** la Jetson.
- Hay que comprobar que CUDA, faster-whisper/CTranslate2, Piper y Ollama funcionan en JetPack 7.2 antes de migrar.
- El Mini PC (Intel) pasa a 24.04 sin complicaciones.

**Veredicto:** ✅ enero de 2027 es viable. Para que la migración no sea doble trabajo, **todo paquete nuevo (`robita_interfaces`, BT, habilidades) debe evitar APIs exclusivas de Humble** y probarse en un contenedor Jazzy en CI o en un PC desde F1.

---

## 6. Plan incremental (actualizado)

| Fase | Contenido | Criterio de salida |
|------|-----------|--------------------|
| **F0 — Consenso** | Cerrar D14–D19. Separar los borrados de la rama de Danilo en un `chore`. Merge de `udito_ros`. Iniciar las solicitudes al **comité de ética y al DPD**, que tardan. | Documento con todas las decisiones *Aceptadas* o *Descartadas*. |
| **F1 — Contrato y base** | `robita_interfaces` (`Utterance`, `TurnTrace`, `Think`), alineado con `hri_msgs` donde se pueda. Migrar `udito_ros` a tipos. **Instalar la seta de emergencia.** `twist_mux` (con *timeouts*) + `collision_monitor`. Medir la memoria de la Jetson y ejecutar `docs/bench/bt_tick_bench.py` en el Mini PC y en la Jetson. | `colcon build` en Humble **y** en un contenedor Jazzy. Un turno completo trazable. Parada garantizada sin el BT. Seta probada. |
| **F2 — Ejecutivo y Cognitive** | Ejecutivo py_trees_ros con los comportamientos actuales del C.C. como subárboles (el catálogo de `intents.yaml` como selector de órdenes). `cognitive` con router, `Think` cancelable y **memoria en el robot**. Retirar `llm_dialog_manager`. `llm-engine` sin estado y con clave de API. | Los 4 casos de respaldo vía `Think`. La cancelación detiene la generación en el servidor. |
| **F3 — Datos y red** | WireGuard. Grabador MCAP en el SSD del Mini PC. chrony, `/udito/meta`, `/diagnostics`. Ingesta a Parquet. Foxglove. | Un dataset piloto (C0 + C1) con data card, **si hay aprobación ética**. |
| **F4 — Modelo del mundo y modos** | ROS4HRI (voces y presencia). Activación por atención. Gestor de modos COMPLETO / LOCAL / DEGRADADO / SEGURO. | Cambio de modo al cortar la WiFi, registrado en la traza. |
| **F5 — Jazzy y deliberativo acotado** | NVMe en la Jetson. Migración a JetPack 7.2 + Jazzy (enero de 2027) y `rmw_zenoh`. `cognitive` propone habilidades del catálogo, validadas por el BT. | Paridad funcional en Jazzy. Las propuestas del LLM, medidas en la traza. |

---

## 7. Preguntas abiertas

### Respondidas (v1)

| # | Pregunta | Respuesta | Efecto |
|---|----------|-----------|--------|
| 1 | NVMe y horas de uso | Sin NVMe; 1–2 h/día | D17 |
| 2 | Evaluadores y formato | Investigadores de la universidad; Parquet; el audio quizá | D11, D13 |
| 3 | Servidor y red | i9-10900K, 32 GB, Quadro RTX 4000; WiFi compartida | D4, D15 |
| 4 | Wakeword | Se elimina de momento | D18 |
| 5 | Paquete de interfaces | `robita_interfaces` | D2 |
| 6 | Jazzy | Sí, enero de 2027 | D19 |
| 7 | SSD en el Mini PC (v1.1) | Sí | D17 aceptada |
| 8 | Compra de NVMe (v1.1) | Sí | D17, D19 |
| 9 | Seta de emergencia (v1.1) | No hay; se instalará | Plano A: condición previa para el movimiento autónomo |

### Nuevas

1. **Danilo:** ¿de acuerdo con el BT como ejecutivo y con py_trees como motor? (D14, D16)
2. Seta de emergencia: ¿quién la monta y **qué corta exactamente**? Debe cortar la potencia de los motores, no enviar un mensaje a ROS.
3. ¿Espacio libre en el SSD del Mini PC? Holgado para C0/C1; solo importa si se aprueba el audio crudo (D13).
4. **TI de la universidad:** ¿se permite un túnel WireGuard saliente (UDP) desde la WiFi? ¿Puede el servidor tener IP fija? (D15)
5. ¿Quién inicia las solicitudes al **comité de ética** y al **DPD**, y cuál es el plazo habitual? (D13)
6. ¿Las sesiones a corto plazo son siempre **supervisadas** (con operador)? Si no, D18 se vuelve urgente.

---

## 8. Referencias

- rmw_zenoh, binarios para Rolling, Jazzy y Humble (aviso sobre el soporte de Humble): <https://discourse.ros.org/t/rmw-zenoh-binaries-for-rolling-jazzy-and-humble/41395>
- MCAP como formato por defecto de rosbag2 desde Iron: <https://foxglove.dev/blog/mcap-as-the-ros2-default-bag-format>
- Plugins de almacenamiento de rosbag2 (Humble, SQLite3 por defecto): <https://docs.ros.org/en/humble/p/rosbag2_storage_default_plugins>
- InfluxDB 3 Core: licencia y limitaciones de rango de consulta: <https://influxdata.com/blog/influxdb3-open-source-public-alpha-jan-27>
- zenoh-backend-influxdb (soporte completo de 1.x, parcial de 2.x): <https://github.com/eclipse-zenoh/zenoh-backend-influxdb>
- Bridge Zenoh para ROS 2 (`zenoh-plugin-ros2dds`): <https://discourse.ros.org/t/new-zenoh-bridge-for-ros-2/34163>
- Rosbag Resurrector (MCAP → Parquet + índice DuckDB): <https://discourse.openrobotics.org/t/rosbag-resurrector-pandas-like-analysis-for-mcap-ros-2-bag-files/54395>
- Foxglove, licencia académica y para organizaciones sin ánimo de lucro: <https://foxglove.dev/pricing>
- ROS4HRI / REP-155, paquete `hri_msgs` (Humble): <https://docs.ros.org/en/humble/p/hri_msgs> · <https://index.ros.org/p/hri_msgs/>
- JetPack 7.2 / Jetson Linux 39.2 con soporte para Orin (Ubuntu 24.04): <https://developer.nvidia.com/embedded/jetpack/downloads/archive-7.2> · <https://docs.nvidia.com/jetson/orin-nano-devkit/user-guide/latest/quick_start.html>
- Groot2 (registro de cambios, LogReplay y licencia PRO): <https://github.com/BehaviorTree/Groot2>
- Tutorial de Groot con Nav2 (Groot2 ↔ BT.CPP v4): <https://docs.nav2.org/tutorials/docs/using_groot.html>
- `system_modes` (modos sobre nodos lifecycle): <https://docs.ros.org/en/jazzy/p/system_modes>
- py_trees_ros (paquetes para Humble y Jazzy): <https://docs.ros.org/en/jazzy/p/py_trees_ros>
- Enlaces Python de BehaviorTree.CPP (`pybt`, PR abierta, sin publicar): <https://github.com/BehaviorTree/BehaviorTree.CPP/pull/1143>
