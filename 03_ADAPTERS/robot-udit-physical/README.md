#descargar repositorio especifico de UDITO en un dispositivo
# 🤖 Despliegue de UDITO en Jetson Orin

Sigue estos 3 pasos exactos en la terminal del dispositivo para realizar la instalación local:

### Paso 1: Descargar el archivo del script
Ejecuta el siguiente bloque para bajar el instalador y otorgarle permisos:

curl -sL [https://raw.githubusercontent.com/robita-lab/cognitive-robotics-core/main/scripts/install_in_jetson.sh](https://raw.githubusercontent.com/robita-lab/cognitive-robotics-core/main/scripts/install_in_jetson.sh) -o install_in_jetson.sh$ chmod +x install_in_jetson.sh

### Paso 2: Configurar las credenciales
Puedes optar por una de las siguientes dos opciones:

* Opción A (Sin editar): No modifiques el archivo. Pasarás los datos directamente en el comando final.
* Opción B (Manual): Abre el script con 'nano install.sh' y escribe tu usuario y token directamente en las variables superiores.

### Paso 3: Ejecutar el script
Si utilizas la Opción A, lanza el script pasando tu usuario y token como argumentos:

$ ./install.sh TU_USUARIO_GITHUB TU_TOKEN_GITHUB

Si utilizas la Opción B, simplemente ejecútalo de forma directa:

$ ./install.sh



---

# Adaptador físico UDITO

Código del **cuerpo** del robot: micrófono, wakeword, grabación VAD, saludo local (Piper) y consulta al **cerebro** por HTTP.

Guía completa: [`DEPLOY_UDITO.md`](../../DEPLOY_UDITO.md)

---

## Archivos

| Archivo | Rol |
|---------|-----|
| `udito.py` | Robot físico → `POST /voice-query` al cerebro en red |
| `udito_standalone.py` | Todo local (STT + RAG + TTS en el mismo PC) |
| `robot_common.py` | Bucle wakeword, calibración, VAD, reproducción audio |
| `requirements-edge.txt` | Dependencias mínimas para el edge (Jetson) |

---

## Scripts (raíz del repo)

| Script | Equivalente anterior | Uso |
|--------|----------------------|-----|
| `./scripts/udito.sh` | etapa2-edge | Robot físico + cerebro remoto |
| `./scripts/udito_standalone.sh` | etapa1-local | Un solo PC, sin Docker cerebro |
| `./scripts/udito_virtual.sh` | etapa2-servidor | Cerebro con Docker Compose |
| `./scripts/launch.sh` | — | Cerebro sin Docker (venv + uvicorn) |

---

## Flujo de voz (robot físico)

```
«udito» (wakeword TFLite)
  → saludo desde 04_KNOWLEDGE_CORE/responses/agent.json (Piper local)
  → grabación pregunta (VAD)
  → POST /voice-query al cerebro
       → STT → ¿despedida? → conversation.json
       → si no → RAG (qa.json + raw-docs) → TTS
  → reproduce audio WAV del cerebro
  → vuelve a escuchar wakeword
```

---

## Configuración

Copiar y editar en la raíz del repo:

```bash
cp .env.example .env
```

| Variable | Descripción |
|----------|-------------|
| `ROBITA_SERVER_URL` | Cerebro, p. ej. `http://192.168.1.100:8000` |
| `ROBITA_AUDIO_INPUT` | Índice del micrófono USB |
| `ROBITA_AUDIO_OUTPUT` | Altavoz ALSA (`default` o `plughw:3,0`) |
| `ROBITA_KNOWLEDGE_CORE` | Textos de saludo/aviso locales |

Probar audio: `../../scripts/test-audio.sh`

---

## Arranque

**Con cerebro en otro equipo (Jetson + servidor):**

```bash
# Servidor
./scripts/launch.sh

# Robot
export ROBITA_SERVER_URL=http://IP_SERVIDOR:8000
./scripts/udito.sh
```

**Todo en un PC:**

```bash
./scripts/udito_standalone.sh
```

El modo standalone permite **una segunda pregunta** tras la primera sin repetir el wakeword.

---

## Textos hablados

No están hardcodeados en Python. Editar:

- Saludo: `04_KNOWLEDGE_CORE/responses/agent.json`
- Despedida: `04_KNOWLEDGE_CORE/responses/conversation.json` (cerebro)
- Q&A fijo: `04_KNOWLEDGE_CORE/responses/qa.json` (RAG)

Tras cambiar despedida o Q&A, reiniciar el cerebro: `./scripts/stop.sh && ./scripts/launch.sh`

---

## Wakeword

- Modelo: `01_SERVICES/wakeword-engine/micro_model.tflite`
- Lógica: `01_SERVICES/wakeword-engine/Detector_wakeword.py`
- Umbral y calibración: `robot_common.py` + `wake_word_config.json`
