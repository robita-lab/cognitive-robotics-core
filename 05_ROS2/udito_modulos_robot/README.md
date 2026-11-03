# Arquitectura híbrida - UDITO · Módulos del robot (voz, rostro, audio)

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales.
> Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../docs/Arquitectura_hibrida_UDITO_v2.png)

Librería Python que usan las **habilidades** (capa 1) del paquete `udito_ros`. Antes estaba en la carpeta
`robot-udit-physical` de 03_ADAPTERS; se trasladó aquí porque es **código de funcionamiento** y
`03_ADAPTERS` queda solo para instalación y configuración de dispositivos.

Los nodos la cargan con `udito_ros.paths.add_engine_paths()`, así que no hace falta instalarla.

| Archivo | Para qué |
|---------|----------|
| `udito_speech.py` | Voz con emociones y pausas (lo usa el nodo TTS) |
| `udito_audio.py` | Pantalla de audio (micrófono, altavoz, volumen) y volumen por software |
| `udito_face.py` | Cara en ventana aparte (`face:=true`) |
| `robot_common.py` | Reproducción y grabación de audio, configuración de sesión |
| `processing_cue.py` · `speaker_lock.py` · `voice_features.py` · `jetson_memory.py` · `log_config.py` | Utilidades de audio, memoria y registro |
| `config/session.json` · `assets/` · `*.mp3` | Configuración y sonidos |
| `udito_standalone.py` | **Modo sin ROS (legado congelado).** Se mantiene hasta que la versión ROS 2 tenga paridad (consenso §2.1); después pasa a `_archive` |
