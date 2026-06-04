# Piper TTS — binarios para Jetson (aarch64)

Los archivos de esta carpeta (`piper`, `*.so`, `espeak-ng-data/`, `voices/`) están en el repositorio **compilados y empaquetados para NVIDIA Jetson / Linux `aarch64`**.

No uses esta carpeta en un PC **x86_64** (servidor o portátil Intel/AMD): el ejecutable no arrancará (`cannot execute binary file`). En x86_64 el TTS del proyecto usa otro despliegue (Docker / cerebro remoto).

## Contenido

| Elemento | Uso |
|----------|-----|
| `piper` | Motor TTS offline en UDITO standalone |
| `lib*.so` | Dependencias del binario aarch64 |
| `voices/*.onnx` | Voces en español (es_ES, es_MX) para Piper |

Tras `git pull` en la Jetson, normalmente **no hace falta** volver a instalar si los binarios del repo coinciden con tu placa.

## Si falla el binario en la Jetson

```bash
cd /opt/robita-lab
./scripts/install-piper-aarch64.sh
```

Ese script descarga Piper oficial aarch64 y deja la carpeta coherente con la arquitectura de la placa.

## ¿Son muy grandes?

Sí. En disco, esta carpeta suele ocupar **~400 MB** (casi todo son las voces `.onnx`, ~60 MB cada una). El `git pull` en otra Jetson puede tardar por eso.

| Parte | Tamaño aprox. |
|-------|----------------|
| `piper` + `.so` + espeak | ~50 MB |
| `voices/*.onnx` | ~340 MB |

## ¿Se pueden omitir en el clone?

**Sí.** No es obligatorio traer las voces con Git si ya tienes el código del repo.

1. Clona o actualiza el repo con normalidad (ya incluye voces si hiciste pull completo).
2. **O** en una Jetson nueva, tras el código, instala solo el motor y descarga **una** voz:

```bash
cd /opt/robita-lab
./scripts/install-piper-aarch64.sh          # binario aarch64 (~15 MB descarga)
./scripts/download-piper-voices-low.sh      # voz ligera en español
# o: ./scripts/download-piper-voices-male.sh
```

La voz activa la define `01_SERVICES/tts-engine/config/tts_config.json` (campo del modelo Piper). Con **una** voz basta para UDITO.

Si borraste `voices/` localmente para ahorrar espacio, vuelve a ejecutar el script de descarga correspondiente; no hace falta commitear las voces otra vez.

## Más contexto

- Arranque UDITO en Jetson: [DEPLOY_JETSON_OFFLINE.md](../../../DEPLOY_JETSON_OFFLINE.md)
- Configuración de voz: [../config/tts_config.json](../config/tts_config.json)
