# Arquitectura híbrida - UDITO · Servidor del laboratorio

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales. Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

**Papel:** capa 3 opcional (deliberativa pesada) y plano D (datos). Es una **mejora, no una dependencia**:
si cae la red, el robot sigue en modo LOCAL (requisito 2 del consenso).

| Qué corre | Detalle |
|-----------|---------|
| `llm-engine` | LLM 7–8B cuantizado a 4 bits, **sin estado** (la memoria vive en el robot), con clave de API |
| RAG completo | Todo el conocimiento de `04_KNOWLEDGE_CORE` (fuente de verdad del índice local de la Jetson) |
| Ingesta | MCAP → Parquet → DuckDB / Polars; Foxglove |

## Red

Las conexiones las **abre siempre el robot** por un túnel **WireGuard** (D15). El servidor nunca inicia contacto.

> Por completar: instalación de `llm-engine`, modelos, WireGuard (servidor) e IP fija (pendiente de TI).
