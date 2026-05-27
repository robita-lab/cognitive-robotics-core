"""Wakeword — reexporta el backend configurado (Jetson: udito_mfcc por defecto)."""

from __future__ import annotations

import os

_b = os.getenv("ROBITA_WAKEWORD_BACKEND", "udito_mfcc").strip().lower()

if _b in ("openwakeword", "oww"):
    from oww_detector import *  # noqa: F403
else:
    from udito_mfcc_detector import *  # noqa: F403
