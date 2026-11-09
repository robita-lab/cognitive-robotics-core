"""Localiza la raíz del repo (01_SERVICES, 04_KNOWLEDGE_CORE).

Orden: argumento explícito → $ROBITA_REPO_ROOT → subir desde este fichero →
subir desde el cwd. Tras `colcon build` sin --symlink-install el código vive en
install/, fuera del árbol del repo; por eso en la Jetson conviene fijar
ROBITA_REPO_ROOT (o el parámetro `repo_root` del nodo).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def _looks_like_root(p: Path) -> bool:
    return (p / "01_SERVICES").is_dir() and (p / "04_KNOWLEDGE_CORE").is_dir()


def find_repo_root(explicit: str | os.PathLike | None = None) -> Path:
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.getenv("ROBITA_REPO_ROOT", "").strip()
    if env:
        candidates.append(Path(env))
    for start in (Path(__file__).resolve(), Path.cwd().resolve()):
        candidates.extend(start.parents)
        candidates.append(start)
    for c in candidates:
        if _looks_like_root(c):
            return c
    raise FileNotFoundError(
        "No encuentro la raíz del repo (01_SERVICES + 04_KNOWLEDGE_CORE). "
        "Define ROBITA_REPO_ROOT o el parámetro repo_root."
    )


def add_to_syspath(*dirs: Path) -> None:
    for d in dirs:
        s = str(d)
        if s not in sys.path:
            sys.path.insert(0, s)
