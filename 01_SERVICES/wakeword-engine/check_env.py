#!/usr/bin/env python3
"""
Diagnóstico del entorno wakeword en Jetson (o PC de desarrollo).

  /opt/robita-lab/.venv/bin/python 01_SERVICES/wakeword-engine/check_env.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ENGINE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _ENGINE_DIR / "config" / "wakeword.json"


def _config_path() -> Path:
    import os

    env = os.getenv("ROBITA_WAKEWORD_CONFIG", "").strip()
    if env:
        p = Path(env)
        return p if p.is_absolute() else (_ENGINE_DIR / p).resolve()
    return _CONFIG_PATH


def _jetpack_release() -> str:
    tegra = Path("/etc/nv_tegra_release")
    if not tegra.is_file():
        return "(no Jetson — /etc/nv_tegra_release ausente)"
    return tegra.read_text(encoding="utf-8", errors="replace").strip()


def _resolve_model_path(cfg: dict) -> Path:
    import os

    env = os.getenv("ROBITA_WAKEWORD_MODEL", "").strip()
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = (_ENGINE_DIR / p).resolve()
        return p
    rel = cfg.get("model", {}).get("path", "models/udito.onnx")
    p = Path(rel)
    if not p.is_absolute():
        p = (_ENGINE_DIR / p).resolve()
    return p


def main() -> int:
    print("=== Wakeword — check_env ===\n")

    # onnxruntime
    try:
        import onnxruntime as ort

        print(f"onnxruntime: {ort.__version__}")
        providers = ort.get_available_providers()
        print(f"Providers disponibles: {providers}")
        cuda = "CUDAExecutionProvider" in providers
        print(f"CUDA disponible: {'SÍ' if cuda else 'NO'}")
        try:
            import onnxruntime.capi._pybind_state as _ort_capi

            build = getattr(_ort_capi, "get_build_info", lambda: "")()
            if build:
                print(f"Build info: {build}")
        except Exception:
            pass
    except ImportError as exc:
        print(f"onnxruntime: NO INSTALADO ({exc})")
        providers = []

    # JetPack
    print(f"\nJetPack / L4T:\n{_jetpack_release()}")

    # Config JSON
    cfg_path = _config_path()
    if not cfg_path.is_file():
        print(f"\nERROR: falta {cfg_path}")
        return 1

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    audio = cfg.get("audio", {})
    sr = int(audio.get("sample_rate", 0))
    chunk_ms = int(audio.get("chunk_ms", 0))
    chunk_samples = int(sr * chunk_ms / 1000) if sr and chunk_ms else 0

    print(f"\nConfig: {cfg_path}")
    print(f"  sample_rate: {sr} Hz")
    print(f"  chunk_ms: {chunk_ms} ms")
    print(f"  chunk_samples: {chunk_samples} (esperado 1280 @ 16 kHz / 80 ms)")
    if sr == 16000 and chunk_samples != 1280:
        print("  AVISO: chunk_samples != 1280 — OpenWakeWord requiere 1280 samples/chunk")

    wake = {
        "wake_threshold": cfg.get("wake_threshold", cfg.get("detection", {}).get("wakeword_threshold")),
        "wake_threshold_mode": cfg.get("wake_threshold_mode", "average"),
        "wake_buffer_size": cfg.get("wake_buffer_size", 3),
        "wake_debug_mode": cfg.get("wake_debug_mode", False),
        "wake_provider": cfg.get("wake_provider", "cuda"),
    }
    print("  wake_*:", wake)

    # Modelo
    model_path = _resolve_model_path(cfg)
    print(f"\nModelo: {model_path}")
    if model_path.is_file():
        size_kb = model_path.stat().st_size / 1024
        print(f"  Existe: SÍ ({size_kb:.1f} KiB)")
        try:
            model_path.read_bytes()[:4]
            print("  Legible: SÍ")
        except OSError as exc:
            print(f"  Legible: NO ({exc})")
            return 1
    else:
        print("  Existe: NO")
        return 1

    # Sesión ORT de prueba (runtime real, no solo get_available_providers)
    if providers:
        try:
            import os

            import onnxruntime as ort

            wake_provider = str(cfg.get("wake_provider", "cpu")).lower()
            if wake_provider in ("cuda", "gpu") and os.environ.get("CUDA_VISIBLE_DEVICES") == "":
                os.environ.pop("CUDA_VISIBLE_DEVICES", None)

            sess = ort.InferenceSession(
                str(model_path),
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            active = sess.get_providers()
            first = active[0] if active else "?"
            print(f"\nSesión de prueba (udito.onnx): {first}")
            if cuda and first != "CUDAExecutionProvider":
                print(
                    "  AVISO: CUDA listado pero sesión usa CPU — suele faltar libcudnn "
                    "(Jetson: sudo apt install nvidia-cudnn o revisa JetPack)."
                )
            elif first == "CUDAExecutionProvider":
                print("  CUDA runtime: OK")
        except Exception as exc:
            print(f"\nSesión de prueba: falló ({exc})")

    print("\n=== Fin check_env ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
