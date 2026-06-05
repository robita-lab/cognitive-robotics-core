# Archivo — no ejecutar

Material **fuera del árbol activo** de la rama `develop` (Jetson offline).

| Carpeta | Contenido |
|---------|-----------|
| **`modo-online/`** | Cerebro remoto, Docker, `udito.py` edge, orquestador — ver [modo-online/README.md](modo-online/README.md) |
| **`scripts/legacy/`** | Scripts sustituidos (Menu_Udito, fetch viejos, etc.) |
| **`historial/`** | Basura movida por `scripts/lib/cleanup-project.sh` |

## Ramas

| Rama | Qué contiene |
|------|----------------|
| **`develop`** | Solo offline — no hay `scripts/server/` ni `docker-compose.yml` en raíz |
| **`develop-base`** | Referencia histórica; debe incluir este `_archive/` tras merge desde `develop` |

```bash
# Tras commit en develop, sincronizar archivo en develop-base:
git checkout develop-base
git merge develop -m "chore: sincronizar _archive desde develop"
```

No borrar manualmente sin revisar.
