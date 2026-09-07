"""
Detector_wakeword.py — Punto de entrada del robot.

Reexporta el motor OpenWakeWord definido en engine.py (config en JSON).
"""

from engine import (  # noqa: F401
    WakeWordEngine,
    get_engine,
    load,
    load_config,
    run_inference,
    run_inference_scores,
)
from ros2_bridge import (  # noqa: F401
    is_ros2_active,
    log_ros2_status,
    probe_ros2,
    publish_state,
    publish_wakeword_detected,
)

_eng = get_engine()
BACKEND = _eng.BACKEND
SAMPLE_RATE = _eng.SAMPLE_RATE
CHUNK_SAMPLES = _eng.CHUNK_SAMPLES
CHUNK_SEC = _eng.CHUNK_SEC
BLOCK_DURATION = _eng.BLOCK_DURATION
THRESHOLD_VOICE = _eng.THRESHOLD_VOICE
WAKEWORD_THRESHOLD = _eng.WAKEWORD_THRESHOLD
