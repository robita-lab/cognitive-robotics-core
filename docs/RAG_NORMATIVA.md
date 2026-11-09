# RAG de normativa en el robot: evaluación y decisión

**Estado:** v0.1 · 2026-11-09 · Luis Peña · rama `feature/cognitive-rag-llm`
**Contexto:** paso P1 de `docs/PLAN_COGNITIVE_RAG_LLM.md` (cambiar los embeddings) y
pregunta de si el enfoque de **hypatia** (la base de conocimiento de
literatura científica de Lurtis) sirve para la parte de normativa o conviene
algo más ligero.

## 1. Resumen

- **El RAG actual casi no encuentra el artículo correcto.** Con embeddings en
  inglés (`all-MiniLM-L6-v2`) y trozos de 1000 caracteres, el artículo
  correcto sale el primero en el **25 %** de las preguntas.
- **Cambio:** `intfloat/multilingual-e5-small` en ONNX, con un trozo por
  artículo. Ahora el artículo correcto sale el primero en el **78 %** y entre
  los tres primeros en el **95 %**. El robot sabe cuándo **no** tiene la
  respuesta (AUC 0,99) y se abstiene en vez de leer un texto que no viene al caso.
- **En el robot ya no hacen falta torch, faiss ni PyPDF2.** El índice
  (256 KB) se construye una vez fuera del robot y se versiona en git. El nodo
  carga en ~1–2 s y responde en ~5 ms (host) / 8–67 ms (contenedor ROS).
- **Hypatia:** no se despliega en el robot, pero se toman cuatro ideas suyas:
  - Relevancia calibrada con umbral de abstención.
  - Embeddings en ONNX, sin torch.
  - Unidades citables (aquí, artículos).
  - Fichas revisadas por una persona, como siguiente paso.

  El resto (docling, GROBID, bibliografía, huecos, servidor MCP) sobra para
  5 documentos con estructura de artículos.
- **Lo que queda flojo:** la respuesta es una frase literal de la normativa.
  En ~12 de 40 preguntas se elige el artículo bueno pero una frase que no
  contesta exactamente. Se arregla con **fichas por artículo** (sección 6) y,
  con red, con el LLM del servidor (P2).

## 2. Corpus

5 documentos, ~65.000 caracteres, 47 unidades citables:

| Código | Documento | Estructura |
|---|---|---|
| ACC | Normativa de acceso y admisión (grado y máster) | 8 artículos |
| RAC | Reconocimiento académico de créditos por actividades | 10 artículos |
| CON | Condiciones generales de admisión y matrícula 24/25 | 12 artículos |
| EXT | Normativa de extinción de titulaciones oficiales | 13 puntos numerados |
| POL | Política de calidad y medio ambiente (misión, visión, valores) | 1 página |

Fuentes declaradas en `04_KNOWLEDGE_CORE/indexes/normativa.sources.json`.

## 3. Banco de evaluación

`04_KNOWLEDGE_CORE/indexes/normativa.eval.json`: **40 preguntas respondibles**
formuladas como las haría un visitante ("¿Me dan créditos por hacer
deporte?"), cada una con su artículo correcto, y **10 no respondibles**
(mundial, parking, cafetería…).

**Limitación:** las preguntas las he escrito yo después de leer los
documentos, así que el banco favorece al sistema. Hay que añadir preguntas
reales de visitantes cuando las haya (D12, trazas por turno).

Métricas:
- **hit@1 / hit@3:** el artículo correcto sale el primero / entre los tres primeros.
- **MRR:** la media de 1/posición del artículo correcto.
- **AUC¬:** la probabilidad de que una pregunta respondible tenga más
  confianza que una no respondible; mide si un umbral puede separarlas.

## 4. Resultados

Exploración (sentence-transformers, mismo banco):

| Embeddings | Troceo | Búsqueda | hit@1 | hit@3 | MRR | AUC¬ |
|---|---|---|---|---|---|---|
| — | 1000 caract. | BM25 | 0,72 | 0,88 | 0,82 | 0,86 |
| all-MiniLM-L6-v2 (**actual**) | 1000 caract. | densa | **0,25** | 0,55 | 0,41 | 0,75 |
| all-MiniLM-L6-v2 | artículo | híbrida | 0,55 | 0,80 | 0,68 | 0,80 |
| paraphrase-multilingual-MiniLM-L12-v2 (el de hypatia) | 1000 caract. | híbrida | 0,78 | 0,88 | 0,84 | 0,91 |
| paraphrase-multilingual-MiniLM-L12-v2 | artículo | densa | 0,50 | 0,72 | 0,64 | 0,94 |
| **multilingual-e5-small** | **artículo** | **densa** | **0,78** | **0,93** | **0,86** | **0,99** |
| multilingual-e5-small | artículo | híbrida | 0,75 | 0,93 | 0,83 | 0,99 |
| paraphrase-multilingual-mpnet-base-v2 (278M, referencia) | 1000 caract. | híbrida | 0,75 | 0,97 | 0,85 | 0,95 |

Implementación final (ONNX, `python -m robita_cognitive.tools.eval_index`):
**hit@1 0,78 · hit@3 0,95 · MRR 0,86 · AUC¬ 0,99 · acierto respondo/me abstengo
con umbral 0,84: 0,92.**

Conclusiones:
- Lo que más pesa es **el modelo de embeddings**: con e5-small, hit@1 pasa de 0,25 a 0,78.
- **e5-small separa mucho mejor lo respondible** (AUC 0,99 frente a 0,91–0,94).
  Por eso el robot puede abstenerse con fiabilidad.
- **El troceo por artículo** apenas cambia las métricas, pero las mejora en la
  práctica: cada trozo es una unidad que se puede citar ("según el artículo 7…")
  y no corta frases a la mitad.
- **BM25 solo** ya llega a 0,72, porque el corpus es pequeño y tiene términos
  exactos. La búsqueda híbrida no mejora a e5 en este corpus. Está implementada
  (`search_mode: hybrid`) por si el corpus crece o aparecen más siglas.

### Cuantización (por si falta memoria en la Jetson)

| e5-small ONNX | Tamaño | hit@1 | hit@3 | Consulta (i9) | RSS proceso |
|---|---|---|---|---|---|
| fp32 (por defecto) | 470 MB | 0,78 | 0,95 | 4,9 ms | 868 MB (nodo ROS completo) |
| int8 dinámico | 118 MB | 0,70 | 0,88 | 2,9 ms | ~340 MB menos |

Se queda fp32. Si al medir en la Jetson falta memoria, se pasa a int8 con
`onnxruntime.quantization.quantize_dynamic`, que vale también en ARM, y se
reconstruye el índice con ese modelo.

## 5. ¿Hypatia o algo más ligero?

| Pieza de hypatia | ¿La usamos? | Por qué |
|---|---|---|
| Conversión de PDF con docling (layout) | **No** en el robot; quizá al construir | Los 5 PDFs tienen texto limpio con `ARTÍCULO N.`; pypdf más un filtro de cabeceras y pies basta. docling arrastra torch y modelos de layout. Sería útil para tablas: la de vías de acceso del art. 4 de ACC se aplana mal. |
| Búsqueda híbrida BM25 + densa | Implementada, **no por defecto** | En este corpus no mejora a e5 denso (sección 4). |
| `paraphrase-multilingual-MiniLM-L12-v2` | **No** → e5-small | e5: hit@1 0,78 frente a 0,50 por artículo; AUC 0,99 frente a 0,94. |
| Relevancia calibrada + `min_relevance` | **Sí** (`min_score` en el manifest) | Es lo que permite decir "no lo sé" en vez de leer algo sin relación. |
| Embeddings sin torch (fastembed/ONNX) | **Sí** (onnxruntime directo) | Memoria en la Jetson. Evita además el problema de setuptools con colcon y los segfaults al leer PDF. |
| Unidades citables (doc, sección, página) | **Sí**, versión ligera | "Según el artículo N de…" en la respuesta y `normativa:ACC:7@<huella>` en las trazas (D12). |
| Fichas por documento escritas por un LLM, con revisión | **El proceso sí, el formato no** → sección 6 | Las fichas de hypatia son de artículo científico (métodos, hallazgos). Aquí hace falta una ficha **por artículo** con la respuesta hablada. Del proceso nos quedamos con el origen (automática / revisada) y la regla de que la ficha es un índice y nunca la prueba. |
| Huecos, bibliografía, `assemble_document`, GROBID, varios temas | **No** | Propio de la literatura científica. |
| Servidor MCP remoto | **No** | El robot debe responder sin WiFi y en tiempo real. Hypatia está pensada para agentes, no para un turno de voz. |

**Decisión:** solución ligera inspirada en hypatia, dentro de
`robita_cognitive`:
- `core/knowledge.py`: el índice y la búsqueda.
- `core/embeddings.py`: e5 en ONNX.
- `core/backends/normativa.py`: el backend.
- `tools/build_index.py` y `tools/eval_index.py`: construir y medir el índice.

Hypatia podría servir **fuera del robot** si algún día hay que digerir PDFs
con tablas complejas (docling), pero hoy no compensa.

## 6. Siguiente paso recomendado: fichas por artículo

El fallo que queda es de redacción, no de búsqueda: el artículo es el bueno,
pero la frase elegida no contesta exactamente. Por ejemplo, "¿me devuelven la
matrícula?" responde con la renovación automática, cuando el mismo artículo
dice "la matrícula no es reembolsable salvo…". Sin LLM en el robot, la forma
de arreglarlo es preparar las respuestas de antemano:

```json
{"unit": "CON:3", "origin": "automatic|reviewed",
 "spoken": "La matrícula no se devuelve, salvo que no cumplas los requisitos de acceso, no se abra el grupo o te denieguen el visado.",
 "questions": ["¿me devuelven la matrícula?", "¿puedo recuperar el dinero si me doy de baja?"],
 "facts": [{"claim": "Recargo del 20 % por ECTS en segunda matrícula", "quote": "cada ECTS que se matricula en segunda o sucesivas ocasiones tendrá un incremento del 20%"}]}
```

- Se generan **fuera del robot** con un LLM a partir del texto literal; cada
  dato lleva su cita.
- Una persona las revisa (`origin: reviewed`) antes de que el robot las use.
  Es normativa: decir algo equivocado es peor que abstenerse.
- Las `questions` se indexan junto al artículo. Así mejora la búsqueda y se
  recuperan las 4 abstenciones injustas del banco.
- Con red, el LLM del servidor (P2) recibe los 3 artículos recuperados y
  redacta; sin red, el robot lee la ficha revisada.

## 7. Problemas conocidos

- **Segfaults aleatorios de Python en los contenedores `ros:humble` de este
  portátil** (i9-13900H, WSL2). Les pasa a PyPDF2, a pypdf y también a
  `colcon build`. No ocurre en el host ni en `ubuntu:22.04` sin ROS, ni
  siquiera con el entorno vacío. Causa sin aclarar.
  - Al construir el índice fuera del robot, en tiempo de ejecución ya no se lee ningún PDF.
  - Si falla una build de prueba, basta con repetirla.
  - Hay que comprobar si pasa en la Jetson.
- **Reglas antiguas por subcadena** (`load_responses.match_knowledge_text`):
  "hora" casaba con "horas" y "campus" con "parking del campus". Corregido
  dentro de `RulesBackend` (palabra completa), sin tocar `load_responses.py`,
  que sigue usando `./UDITO`.
- **Tablas aplanadas:** la tabla de vías de acceso del art. 4 de ACC sale como
  texto corrido ("VÍA DE ACCESO DOCUMENTACIÓN REQUERIDA…"). Las fichas lo resuelven.
