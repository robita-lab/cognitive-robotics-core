# UDITO — Despliegue: servidor → GitHub → Jetson Orin

Producto **UDITO** = robot social (voz + wakeword + RAG TinyLlama).  
**No es web.** El agente web (solo RAG en navegador) es otro subproducto y no entra en estas etapas.

---

## Arquitectura en dos etapas

| Etapa | Dónde | Qué hace |
|-------|--------|----------|
| **1** | Un solo PC (este servidor) | Todo local: wakeword → STT → RAG (TinyLlama) → TTS |
| **2** | Servidor + Jetson (probado aquí con `127.0.0.1`) | **Cerebro** en servidor (Docker). **Cuerpo** en Jetson: wakeword + mic + `POST /voice-query` |

```
Etapa 2 en producción:

  Jetson Orin                         Servidor (cerebro)
  ───────────                         ──────────────────
  robot_edge_client.py                docker compose
  wakeword + mic + altavoz    LAN     :8000 orquestador
  Piper (solo bienvenida)      ───►    :8001 STT
                                      :8004 RAG + TinyLlama
                                      :8002 TTS
```

Conexión **directa por IP y puerto** (HTTP máquina a máquina). Sin navegador.

---

## Etapa 1 — Probar aquí (todo local)

```bash
cd /opt/robita-lab
./scripts/setup-venv.sh          # solo la primera vez
./scripts/etapa1-local.sh
```

- Calibración de ruido → bienvenida hablada → di **«udito»** → pregunta → respuesta por altavoz.
- Script: `03_ADAPTERS/robot-udit-physical/robot_voice_loop.py`

---

## Etapa 2 — Probar aquí (servidor + cliente edge)

**Terminal A — cerebro (servidor):**

```bash
cd /opt/robita-lab
cp .env.example .env    # editar si hace falta
./scripts/etapa2-servidor.sh
# Esperar a que RAG indexe (primera vez: varios minutos)
curl http://127.0.0.1:8000/services/status
```

**Terminal B — cuerpo (simula Jetson en el mismo PC):**

```bash
cd /opt/robita-lab
export ROBITA_SERVER_URL=http://127.0.0.1:8000
./scripts/etapa2-edge.sh
```

En la Jetson real sustituye `127.0.0.1` por la **IP LAN del servidor**.

---

## Subir a GitHub (servidor → GitHub)

### Qué NO subir

- `.venv/`, `logs/`, `.env` (secretos)
- Cachés grandes: `01_SERVICES/rag-engine/data/rag_cache/*.pkl`
- Tokens en `Despliegue_github.sh` — usar PAT solo en el servidor, no commitear

### Pasos recomendados

```bash
cd /opt/robita-lab

# 1. Revisar qué se sube
git status

# 2. Configurar remoto (sin token en el archivo si es posible)
git remote add origin https://github.com/robita-lab/cognitive-robotics-core.git

# 3. Commit
git add .
git commit -m "feat(udito): etapa1 local + etapa2 edge/servidor + guía Jetson"

# 4. Push (PAT por variable de entorno, no en el script)
git push -u origin main
```

Alternativa: editar y ejecutar `Despliegue_github.sh` **solo en el servidor**, con token fuera del repositorio.

### Estructura que debe quedar en el repo

```
01_SERVICES/          # motores + Dockerfiles
03_ADAPTERS/robot-udit-physical/
  robot_voice_loop.py   # etapa 1
  robot_edge_client.py  # etapa 2 Jetson
  robot_common.py
04_KNOWLEDGE_CORE/raw-docs/   # PDFs UDIT
docker-compose.yml
.env.example
scripts/etapa1-local.sh
scripts/etapa2-servidor.sh
scripts/etapa2-edge.sh
DEPLOY_UDITO.md
```

---

## Implementar en Jetson Orin (GitHub → Jetson)

### 1. Servidor (cerebro) — una vez en el laboratorio

```bash
cd /opt/robita-lab
git pull
cp .env.example .env
./scripts/etapa2-servidor.sh
```

Anota la IP del servidor: `hostname -I`

Abre firewall solo en LAN si aplica: puertos **8000** (orquestador) desde la red local.

### 2. Jetson (cuerpo UDITO)

```bash
# Dependencias sistema
sudo apt update
sudo apt install -y python3-venv python3-pip portaudio19-dev alsa-utils git

git clone https://github.com/robita-lab/cognitive-robotics-core.git /opt/robita-lab
cd /opt/robita-lab

python3 -m venv .venv
source .venv/bin/activate
# Solo lo que necesita el edge (ligero):
pip install -r 03_ADAPTERS/robot-udit-physical/requirements-edge.txt

cp .env.example .env
# Editar:
#   ROBITA_SERVER_URL=http://IP_DEL_SERVIDOR:8000

export CUDA_VISIBLE_DEVICES=""
./scripts/etapa2-edge.sh
```

La Jetson **no** necesita cargar TinyLlama ni el índice RAG completo si siempre hay red al servidor.

### 3. Jetson offline (futuro, opcional)

Si no hay red: en la Jetson clonar el repo y usar **etapa 1** (`robot_voice_loop.py`) con modelos descargados y `rag_config.json` con `tinyllama` local. Requiere más RAM/GPU en la Orin.

---

## RAG y TinyLlama

- LLM del RAG: **TinyLlama 1.1B** (`rag_config.json` → `"backend": "tinyllama"`).
- En **etapa 2** TinyLlama corre solo en el **servidor** (`rag-engine`).
- Recuperación: FAISS + embeddings + PDFs en `04_KNOWLEDGE_CORE/raw-docs/`.

---

## Resumen de comandos

| Acción | Comando |
|--------|---------|
| Etapa 1 local | `./scripts/etapa1-local.sh` |
| Cerebro (servidor) | `./scripts/etapa2-servidor.sh` |
| Cuerpo (Jetson) | `ROBITA_SERVER_URL=http://IP:8000 ./scripts/etapa2-edge.sh` |
| Parar Docker | `docker compose down` |

---

## Agente web (fuera de UDITO)

La página web del agente virtual (solo consulta RAG) se desplegará aparte. **No usar** para UDITO ni mezclar con estos scripts.
