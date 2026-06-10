"""
engine.py — Compatibilidad con imports existentes (Detector_wakeword, scripts).

La implementación vive en wake.py.
"""

from wake import (  # noqa: F401
    WakeWordEngine,
    export_module_attrs,
    get_engine,
    load,
    load_config,
    run_debug_monitor,
    run_inference,
    run_inference_scores,
)
