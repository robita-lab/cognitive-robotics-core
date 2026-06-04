# UDITO en Jetson Orin — pipeline offline (standalone)

Guía para ejecutar **wakeword + STT + RAG + TTS** en la Jetson **sin cerebro remoto ni servidor en la red**.

El servidor del laboratorio es **opcional** (solo para copiar modelos una vez con `sync-models-from-server.sh`). **UDITO debe funcionar con el servidor apagado o sin LAN.**

Repositorio: [cognitive-robotics-core](https://github.com/robita-lab/cognitive-robotics-core).

Ruta estándar: `/opt/robita-lab`

**Rama Git:** **`develop`** (UDITO offline en Jetson). Ver [README.md](README.md#ramas-del-repositorio).

```bash
git clone -b develop https://github.com/robita-lab/cognitive-robotics-core.git /opt/robita-lab
```

---

## Qué modo usar

| Escenario | Script |
|-----------|--------|
| **Jetson offline (este documento)** | `./scripts/setup-jetson-offline.sh` luego **`./scripts/Principal-UDITO.sh`** o **`./UDITO`** |
| Jetson + cerebro en servidor LAN | `./scripts/udito.sh` con `ROBITA_SERVER_URL` |
| Servidor (cerebro Docker/venv) | `./scripts/launch.sh` |

El modo standalone corre un solo proceso Python (`udito_standalone.py`) que carga wakeword, Whisper, RAG y Piper localmente.

---

## Requisitos hardware / SO

- NVIDIA Jetson Orin (aarch64), Ubuntu 22.04
- Micrófono USB y altavoz (grupo `audio`)
- **~8 GB RAM** recomendado (TinyLlama + Whisper en CPU)
- **~15 GB libres** en disco (venv, modelos HF, caché RAG)
- Red **solo la primera vez** (pip + descarga de modelos), salvo que copies cachés desde el servidor

---

## Instalación en una Jetson nueva (desde GitHub)

### 1. Paquetes del sistema

```bash
sudo apt update
sudo apt install -y python3.10-venv python3-pip portaudio19-dev alsa-utils \
  libopenblas-dev libsndfile1 curl git
```

Si `python3 -m venv` falla por `ensurepip`, el script `setup-venv.sh` crea el `.venv` con `get-pip.py` automáticamente (no requiere pasos extra).

### 2. Clonar o instalar el repo

**Opción A — clone público:**

```bash
sudo mkdir -p /opt/robita-lab
sudo chown -R "$USER:$USER" /opt/robita-lab
git clone https://github.com/robita-lab/cognitive-robotics-core.git /opt/robita-lab
cd /opt/robita-lab
```

**Opción B — tarball mínimo (repo privado):**

```bash
./scripts/install-jetson-offline.sh TU_USUARIO_GITHUB TU_TOKEN
```

### 3. Configuración automática (venv + Piper aarch64 + .env)

```bash
cd /opt/robita-lab
./scripts/setup-jetson-offline.sh
```

Esto:

- Crea `.venv` e instala dependencias (`setup-venv.sh`)
- Sustituye el binario **Piper x86_64** por **piper_linux_aarch64** si hace falta
- Copia `.env.example` → `.env` con `ROBITA_RAG_CONFIG` para Jetson

Los binarios y voces en `01_SERVICES/tts-engine/piper/` del repo son **para Jetson (aarch64)**. Ver [piper/README.md](01_SERVICES/tts-engine/piper/README.md).

### 4. Modelos de IA (primera vez con internet)

```bash
cd /opt/robita-lab
source .venv/bin/activate
./scripts/download-offline-models.sh
```

Descarga a `data/huggingface/` (Whisper, embeddings, TinyLlama). La primera ejecución de UDITO puede tardar varios minutos mientras indexa `Horarios_UDIT.txt`.

### 5. Copiar modelos desde el servidor del laboratorio (sin re-descargar)

Si el servidor ya tiene todo en caché, desde la Jetson (sustituye `IP_SERVIDOR` y usuario):

```bash
export ROBITA_SERVER_HOST=192.168.x.x
export ROBITA_SERVER_USER=udito
./scripts/sync-models-from-server.sh
```

Vuelve a ejecutar `./scripts/download-offline-models.sh` solo si faltan archivos.

### 6. Wakeword (openWakeWord — por defecto en Jetson)

En **esta Jetson** el motor por defecto es **[openWakeWord](https://github.com/dscripka/openWakeWord)**, no TFLite.

| | Jetson / Linux (este repo) | Windows |
|---|---------------------------|---------|
| Motor | **openWakeWord** + ONNX | **TFLite** (`micro_model.tflite`) |
| Modelo «udito» | `01_SERVICES/wakeword-engine/models/udito.onnx` | Export `.tflite` (legado) |
| Setup | `./scripts/setup-wakeword-oww.sh` | No usar `setup-wakeword-oww.sh` sin adaptar código |

**Windows:** openWakeWord **no** es el camino soportado en el pipeline Windows del laboratorio; allí se usa **TensorFlow Lite**. Detalle: [01_SERVICES/wakeword-engine/README.md](01_SERVICES/wakeword-engine/README.md).

```bash
# Copia tu modelo entrenado con openWakeWord:
cp /ruta/udito.onnx /opt/robita-lab/01_SERVICES/wakeword-engine/models/udito.onnx
./scripts/setup-wakeword-oww.sh
```

`.env`: `ROBITA_WAKEWORD_BACKEND=openwakeword` (opcional; es el comportamiento por defecto en `udito_standalone.py`).

### 7. Audio

Edita `.env`:

```bash
nano /opt/robita-lab/.env
```

- `ROBITA_AUDIO_INPUT` — índice del mic (entero)
- `ROBITA_AUDIO_OUTPUT` — `default` o `plughw:X,Y`

Prueba TTS sin wakeword:

```bash
./scripts/test-audio-standalone.sh
```

### 8. Arrancar UDITO offline

**Comando principal (recomendado en Jetson):**

```bash
cd /opt/robita-lab
./scripts/Principal-UDITO.sh
# atajo en la raíz del repo:
./UDITO
```

Internamente ejecuta `udito_standalone.py` vía `udito_standalone.sh` (no hace falta invocarlo directamente).

Antes de arrancar, `prepare-pipeline.sh` (automático) detiene Docker/contenedores, puertos 8000–8004, ollama si estaba activo, y libera RAM.

Desactivar preparación: `ROBITA_SKIP_PREPARE=1 ./scripts/Principal-UDITO.sh`

`start-udito-visible.sh` redirige al mismo script (compatibilidad).

**Solo si necesitas cerebro remoto** (servidor encendido): `./scripts/udito-run.sh` → modo online.

**Menú de pruebas por componente:**

```bash
./scripts/Menu_Udito.sh
```

Opción 1 = `Principal-UDITO.sh`. Opciones 2–6 = pruebas parciales.

Flujo: di **«udito»** → saludo → pregunta → respuesta hablada.

---

## Variables de entorno (Jetson offline)

| Variable | Uso |
|----------|-----|
| `ROBITA_KNOWLEDGE_CORE` | Textos en `04_KNOWLEDGE_CORE/responses/` |
| `ROBITA_RAG_CONFIG` | `rag_config.jetson.json` (solo docs presentes en edge) |
| `HF_HOME` | Caché Hugging Face en `data/huggingface` |
| `ROBITA_AUDIO_INPUT` / `ROBITA_AUDIO_OUTPUT` | Dispositivos de audio |
| `WHISPER_MODEL` | `small` (por defecto) |
| `CUDA_VISIBLE_DEVICES` | Vacío = CPU (recomendado para estabilidad en 8 GB) |

---

## Ampliar conocimiento documental

El perfil Jetson incluye solo `Horarios_UDIT.txt`. Para los PDFs del servidor:

```bash
rsync -avz usuario@IP_SERVIDOR:/opt/robita-lab/04_KNOWLEDGE_CORE/raw-docs/ \
  /opt/robita-lab/04_KNOWLEDGE_CORE/raw-docs/
```

Luego cambia en `.env`:

```bash
ROBITA_RAG_CONFIG=/opt/robita-lab/01_SERVICES/rag-engine/config/rag_config.json
```

y reinicia standalone (reindexará RAG).

---

## Solución de problemas

### Jetson se bloquea o reinicia (muy importante)

**Causa habitual:** falta de RAM (~7,4 GB). Si se cargan a la vez **TensorFlow** (wakeword) + **Whisper** + **TinyLlama** (~4 GB solo el LLM) + embeddings, el kernel mata procesos o la placa se reinicia.

**Optimizaciones activas en Jetson:**

| Medida | Efecto |
|--------|--------|
| `rag_config.jetson.json` → `backend: none` | Sin TinyLlama (~4 GB) |
| Arranque solo wakeword + TTS | STT/RAG tras el primer «udito» |
| `WHISPER_MODEL=tiny` | STT más ligero que `small` |
| Wakeword **openWakeWord** + ONNX | Sin `tflite_runtime` roto en numpy 2 (Jetson) |
| STT se libera tras transcribir | No convive Whisper + RAG en RAM |
| Embeddings RAG bajo demanda | No cargan hasta indexar/buscar |
| `OMP_NUM_THREADS=1` etc. | Menos picos por hilos |

Variables en `.env`: `ROBITA_LOW_MEMORY=1`, `ROBITA_RELEASE_MODELS=1`.

**No ejecutes** en la Jetson a la vez: `download-offline-models.sh` (descarga TinyLlama) + pipeline + Docker. Arranca con **`Principal-UDITO.sh`** o **`Menu_Udito.sh` → opción 1**.

**No uses** `udito.sh` ni `ROBITA_SERVER_URL` si el servidor no está disponible. El modo correcto en esta Jetson es siempre **offline** → **`Principal-UDITO.sh`** (o `./UDITO`).

| Síntoma | Acción |
|---------|--------|
| Reinicios al abrir UDITO | Confirma `ROBITA_RAG_CONFIG=.../rag_config.jetson.json` y `backend: none` |
| `cannot execute binary file` al hablar | Piper era x86: `./scripts/install-piper-aarch64.sh` |
| `No module named faster_whisper` | `./scripts/setup-venv.sh` |
| Sin respuesta RAG / muy lento | Comprueba `data/huggingface`; copia desde servidor |
| No oye el altavoz | `./scripts/test-audio-standalone.sh`, `alsamixer` |
| Wakeword no dispara | `models/udito.onnx` presente; `./scripts/setup-wakeword-oww.sh`; ver [wakeword-engine/README.md](01_SERVICES/wakeword-engine/README.md) |

Logs: salida en consola con `ROBITA_VERBOSE=1`.

---

## Relación con el resto del monorepo

- **No modifica** el flujo servidor (`launch.sh`, `docker-compose.yml`).
- `install_in_jetson.sh` antiguo levantaba Docker (cerebro); usar **`install-jetson-offline.sh`** o esta guía.
- Subir cambios: ver sección «Git» en `README.md`.
