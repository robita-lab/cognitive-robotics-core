"""Arquitectura 3T - UDITO · Contrato de topics (el «bus» ROS 2).

Capa reactiva (sensores/actuadores) <-> Capa ejecutiva C.C. <-> Capa deliberativa.
Todos los mensajes son std_msgs/String con JSON (salvo STT_ENABLE: std_msgs/Bool).
"""

# Capa reactiva -> C.C.
STT_TEXT = "/udito/stt/text"          # texto reconocido por el micrófono
# C.C. -> capa reactiva
STT_ENABLE = "/udito/stt/enable"      # Bool: abre/cierra el micrófono (evita oírse a sí mismo)
TTS_SAY = "/udito/tts/say"            # {"id","text","emotion","laugh"}
TTS_DONE = "/udito/tts/done"          # {"id"} cuando termina de hablar
SPEECH_OUT = "/udito/speech_out"      # emoción para la pantalla-rostro (ya lo escucha udito_face)
STATE = "/udito/state"                # {"state": "session_listening" | "idle" | "speaking"...}
INTENT = "/udito/intent"              # {"name","text","args"} para cuerpo (cuello, base) — futuro
# C.C. <-> capa deliberativa (Cognitive)
COG_QUERY = "/udito/cognitive/query"  # {"id","text"}
COG_ANSWER = "/udito/cognitive/answer"  # {"id","text","emotion","source"}
