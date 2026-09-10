# Guía de Git-Flow para UDITO

Esta guía explica cómo trabajamos con ramas y commits en este repositorio. **No hay revisor ni política de Pull Request**: cada miembro del equipo es responsable de que sus commits entren limpios. Por eso importa que todos sigamos las mismas reglas.

Si tienes dudas, léelo entero una vez y ten esta página a mano las primeras semanas.

---

## 1. Las tres ramas que siempre existen

```
main     ──────●──────────────●────────────●──────   (releases etiquetados)
                \              \            \
develop  ────●───●──●──●────────●──●──●──────●────   (integración)
              \     \              \
               feat  feat           hotfix
```

| Rama      | Para qué sirve                                    | ¿Se commitea directamente? |
|-----------|---------------------------------------------------|----------------------------|
| `main`    | Código en producción / demos. Solo versiones etiquetadas (`v0.1.0-demo`, etc.). | **NO. Nunca.** |
| `develop` | Rama de integración. Todo lo que está terminado acaba aquí. | **NO.** Solo mediante merge desde `feature/*`, `release/*` o `hotfix/*`. |
| `feature/*`, `release/*`, `hotfix/*` | Ramas de trabajo. Aquí es donde sí commiteas. | **Sí.** |

> Regla de oro: **si tu rama actual es `main` o `develop`, no hagas `git commit`.** Crea una rama de trabajo primero.

---

## 2. Tipos de rama de trabajo

### 2.1 `feature/<nombre>` — funcionalidad nueva

- **De dónde sale:** de `develop`.
- **A dónde vuelve:** a `develop`.
- **Nombre:** `feature/` + descripción corta en kebab-case.
  - Bien: `feature/llm-server-side`, `feature/router-greeting-fix`, `feature/tts-streaming`
  - Mal: `feature/luis`, `feature/cambios`, `feature/arreglos-varios`

### 2.2 `hotfix/<nombre>` — arreglo urgente en producción

- **De dónde sale:** de `main`.
- **A dónde vuelve:** a `main` **y** a `develop` (las dos).
- Solo para bugs críticos que aparecen en un release ya publicado.
- Ejemplo: `hotfix/audio-crash-arranque`.

### 2.3 `release/<version>` — preparación de un release

- **De dónde sale:** de `develop`.
- **A dónde vuelve:** a `main` (etiquetada) **y** a `develop`.
- Aquí se hacen solo ajustes de versión, cambios de documentación y correcciones menores. **No** se añaden funcionalidades nuevas.
- Ejemplo: `release/v0.1.0-demo`.

### 2.4 `bugfix/<nombre>` — bug no urgente (opcional)

- Como `feature/*` pero para corregir algo que no funciona en `develop`.
- Sale de `develop`, vuelve a `develop`.
- Si prefieres simplificar, puedes meter los bugfixes dentro de `feature/*`. Lo importante es ser consistente.

---

## 3. Flujo de trabajo típico (copia-pega)

### Empezar una funcionalidad nueva

```bash
# 1. Ponte en develop y actualízala
git checkout develop
git pull

# 2. Crea tu rama de trabajo
git checkout -b feature/mi-nueva-funcion

# 3. Trabaja: edita, commitea (ver sección 4), repite.
git add <archivos>
git commit -m "feat(scope): descripcion corta"

# 4. Empuja tu rama a origin (la primera vez con -u)
git push -u origin feature/mi-nueva-funcion
```

### Integrar tu funcionalidad en `develop`

```bash
# 1. Antes de fusionar, trae los últimos cambios de develop a tu rama
git checkout develop
git pull
git checkout feature/mi-nueva-funcion
git merge develop        # resuelve conflictos aquí, en tu rama, no en develop
# (o: git rebase develop si prefieres historial lineal y sabes lo que haces)

# 2. Verifica que el código sigue funcionando tras el merge
#    (tests, build, arranque rápido del stack…)

# 3. Fusiona a develop
git checkout develop
git merge --no-ff feature/mi-nueva-funcion
git push

# 4. Borra la rama local y la remota cuando esté fusionada
git branch -d feature/mi-nueva-funcion
git push origin --delete feature/mi-nueva-funcion
```

`--no-ff` fuerza un merge commit aunque sería posible hacer fast-forward. Lo queremos: deja visible en el grafo qué commits pertenecían a cada feature.

### Sacar un release

```bash
git checkout develop
git pull
git checkout -b release/v0.1.0
# ajustes finales (version bump, changelog…)
git commit -m "chore(release): v0.1.0"

# Cuando está listo:
git checkout main
git merge --no-ff release/v0.1.0
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin main --tags

git checkout develop
git merge --no-ff release/v0.1.0
git push

git branch -d release/v0.1.0
git push origin --delete release/v0.1.0
```

### Hotfix urgente

```bash
git checkout main
git pull
git checkout -b hotfix/descripcion-corta
# arregla, commitea
git checkout main
git merge --no-ff hotfix/descripcion-corta
git tag -a v0.1.1 -m "Hotfix v0.1.1"
git push origin main --tags

git checkout develop
git merge --no-ff hotfix/descripcion-corta
git push

git branch -d hotfix/descripcion-corta
git push origin --delete hotfix/descripcion-corta
```

---

## 4. Cómo escribir commits

Usamos **Conventional Commits**. El formato es:

```
tipo(scope): resumen corto en minúsculas, sin punto final

Cuerpo opcional explicando el "por qué" (no el "qué", eso ya está en el diff).
Una línea en blanco entre resumen y cuerpo.
```

### Tipos que usamos

| Tipo     | Cuándo usarlo                                             |
|----------|-----------------------------------------------------------|
| `feat`   | Funcionalidad nueva visible para el usuario o para otro módulo. |
| `fix`    | Corrección de un bug.                                     |
| `docs`   | Solo documentación (`.md`, comentarios, ARCHITECTURE…).   |
| `refactor` | Cambio de código que no altera comportamiento externo. |
| `test`   | Añadir o corregir tests.                                  |
| `chore`  | Tareas de mantenimiento: dependencias, configuración, versionado. |
| `build`  | Cambios en Dockerfiles, `requirements.txt`, scripts de build. |
| `perf`   | Mejora de rendimiento sin cambio funcional.               |

### Scopes que usamos

El scope identifica la parte del sistema afectada. Ejemplos reales del repo:

- `server-side` — stack FastAPI + Ollama + Redis
- `dialog` — `llm_dialog_manager` (ROS2)
- `audio` — STT/TTS, ReSpeaker
- `ros2` — launchfiles, paquetes ROS2 genéricos
- `arduino` — firmware de microcontrolador
- `secrets` — gestión de credenciales y `.env`
- `docs` — documentación de nivel de workspace

Si tu cambio cruza scopes, elige el principal o usa un scope más genérico (`repo`, `build`).

### Ejemplos buenos

```
feat(dialog): añadir fallback cuando el router devuelve intent=unknown
fix(server-side): copiar README.md en la stage builder del Dockerfile
docs(server-side): describir el diseño de dos niveles en ARCHITECTURE.md
refactor(audio): extraer la ruta de config a un helper reutilizable
chore(release): v0.1.0-demo
```

### Ejemplos malos (y por qué)

| Commit                              | Problema                                     |
|-------------------------------------|----------------------------------------------|
| `arreglos`                          | No dice qué, ni dónde, ni por qué.           |
| `Cambios varios en el código`       | Commits múltiples mezclados — sepáralos.     |
| `fix: bug`                          | Falta scope y resumen útil.                  |
| `feat(server-side): Added new endpoint.` | Mayúscula inicial, punto final, verbo en pasado — usa presente, minúsculas, sin punto. |
| `WIP`                               | Nunca en `develop` o `main`. Solo está bien en tu rama local, y aun así mejor evítalo. |

### Reglas adicionales

- **Resumen ≤ 72 caracteres.** Si no cabe, el cambio probablemente es demasiado grande.
- **Un commit = un cambio lógico.** Si en el mismo commit arreglas un bug *y* añades una feature, divídelo (`git add -p` es tu amigo).
- **No hagas `git add .` a ciegas.** Puede colar archivos de entorno, binarios o secretos. Añade por nombre.
- **No incluyas credenciales jamás.** Ni en el código, ni en el mensaje del commit. Las claves van en `.env` (que está en `.gitignore`).
- **No añadas trailers automáticos** (`Co-Authored-By: Claude…`, `Generated-by: …`, etc.) a los commits de este repo.

---

## 5. Responsabilidades sin revisor

Como no hay Pull Request con revisor, **cada uno se autorrevisa antes de push**. Checklist mínima antes de hacer `git push` a `develop`:

- [ ] He corrido los tests relevantes localmente y pasan.
- [ ] He arrancado el módulo que tocó (stack server-side, nodo ROS, etc.) y funciona.
- [ ] `git diff` muestra solo cambios que yo entiendo. Nada que no reconozca.
- [ ] No estoy commiteando archivos generados (`build/`, `__pycache__/`, `.venv/`, modelos descargados, logs, `*.wav` de prueba…).
- [ ] No estoy commiteando secretos ni rutas absolutas con mi usuario personal.
- [ ] El commit (o los commits) tienen mensajes de la sección 4.
- [ ] Traje `develop` a mi rama antes de fusionar, y resolví los conflictos.

Si encuentras un bug propio después de haber empujado a `develop`: **no lo silencies con un `git push --force`**. Haz un nuevo commit que lo arregle (o un `git revert` si hace falta volver atrás). El historial de `develop` y `main` es compartido y no se reescribe.

---

## 6. Cosas que nunca hacemos

- **`git push --force` a `develop` o `main`.** Jamás. Reescribir historia compartida rompe el repo de los demás.
- **Commitear directamente a `develop` o `main`.** Siempre desde una rama de trabajo.
- **Mezclar cambios no relacionados en un mismo commit.**
- **Fusionar sin traer antes `develop`** (te arriesgas a meter conflictos sin verlos venir).
- **Borrar ramas remotas de otra gente.**
- **Subir `.env`, claves, tokens, o archivos con rutas tipo `/home/udito/...`.**

---

## 7. Chuleta rápida

```bash
# ¿En qué rama estoy?
git branch --show-current

# ¿Qué voy a commitear?
git status
git diff --staged

# Crear rama de feature
git checkout develop && git pull
git checkout -b feature/mi-cosa

# Commit correcto
git add ruta/concreta/archivo.py
git commit -m "feat(scope): resumen corto"

# Traer develop a mi rama antes de fusionar
git fetch && git merge origin/develop

# Fusionar mi feature a develop
git checkout develop && git pull
git merge --no-ff feature/mi-cosa
git push

# Limpieza
git branch -d feature/mi-cosa
git push origin --delete feature/mi-cosa
```

---

## 8. Dudas

Si algo de esta guía choca con un caso real que te encuentres, **pregunta antes de empujar**. Es más barato hablar 5 minutos que deshacer un merge roto en `develop`.
