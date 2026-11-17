# Arquitectura híbrida - UDITO · voice-face-engine (voz, rostro y audio)

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales.
> Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../docs/Arquitectura_hibrida_UDITO_v2.png)

Motor en Python **sin ROS**, igual que `stt-engine` y `tts-engine`. Lo usan las habilidades de voz
(`05_ROS2/ros2_ws/src/voice_skills`) y el modo sin ROS. Historia: estaba en `03_ADAPTERS/robot-udit-physical`
y después en una carpeta de `05_ROS2`; vive aquí porque no es ROS y puede reutilizarlo cualquier
adaptador (robot, web…).

Los nodos lo cargan con `central_control.paths.add_engine_paths()`, así que no hace falta instalarla.

| Archivo | Para qué |
|---------|----------|
| `udito_speech.py` | Voz con emociones y pausas (lo usa el nodo TTS) |
| `udito_audio.py` | Pantalla de audio (micrófono, altavoz, volumen) y volumen por software |
| `udito_face.py` | Cara en ventana aparte (`face:=true`) |
| `robot_common.py` | Reproducción y grabación de audio, configuración de sesión |
| `processing_cue.py` · `speaker_lock.py` · `voice_features.py` · `jetson_memory.py` · `log_config.py` | Utilidades de audio, memoria y registro |
| `config/session.json` · `assets/` · `*.mp3` | Configuración y sonidos |
| `udito_standalone.py` | **Modo sin ROS (legado congelado).** Se mantiene hasta que la versión ROS 2 tenga paridad (consenso §2.1); después pasa a `_archive` |
