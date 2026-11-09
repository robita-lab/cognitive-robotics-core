"""Descarga los ficheros ONNX del modelo de embeddings (revisión fijada).

  python -m robita_cognitive.tools.fetch_model [--dest DIR] [--model intfloat/multilingual-e5-small]

Destino por defecto: $ROBITA_MODELS_DIR o ~/.cache/robita/models. Hay que
hacerlo una vez con red; después el robot funciona sin ella.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import urllib.request
from pathlib import Path

from ..core.embeddings import MODELS, E5_SMALL, models_dir


def fetch(model: str = E5_SMALL.name, dest: Path | None = None, force: bool = False) -> Path:
    spec = MODELS[model]
    target = (dest or models_dir()) / spec.dirname
    target.mkdir(parents=True, exist_ok=True)
    for local, remote in spec.files.items():
        out = target / local
        if out.is_file() and not force:
            print(f"ya existe {out}")
            continue
        url = f"https://huggingface.co/{spec.name}/resolve/{spec.revision}/{remote}"
        print(f"descargando {url}")
        tmp = out.with_suffix(out.suffix + ".part")
        req = urllib.request.Request(url, headers={"User-Agent": "robita-cognitive"})
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f, length=1 << 20)
        tmp.replace(out)
    (target / "REVISION").write_text(f"{spec.name}@{spec.revision}\n")
    return target


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default=E5_SMALL.name, choices=sorted(MODELS))
    ap.add_argument("--dest", type=Path, default=None)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)
    print(fetch(a.model, a.dest, a.force))
    return 0


if __name__ == "__main__":
    sys.exit(main())
