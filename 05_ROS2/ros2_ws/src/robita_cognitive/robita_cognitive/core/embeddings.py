"""Embeddings de texto con ONNX Runtime (sin torch).

Modelo por defecto: intfloat/multilingual-e5-small (MIT, 384 dimensiones).
Elegido con la evaluación de docs/RAG_NORMATIVA.md: el mejor de los modelos
pequeños en español y el que mejor separa preguntas respondibles de no
respondibles.

Dependencias: numpy, onnxruntime y tokenizers (hay wheels para aarch64; en la
Jetson se puede usar onnxruntime-gpu). Los ficheros del modelo se descargan
con `python -m robita_cognitive.tools.fetch_model` y viven en
$ROBITA_MODELS_DIR (por defecto ~/.cache/robita/models).
"""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np


@dataclass(frozen=True)
class ModelSpec:
    name: str          # id en Hugging Face
    revision: str      # commit fijado: el índice se construyó con estos pesos
    files: dict[str, str]  # nombre local -> ruta en el repo
    query_prefix: str = ""
    passage_prefix: str = ""
    max_tokens: int = 512

    @property
    def dirname(self) -> str:
        return self.name.split("/")[-1]


E5_SMALL = ModelSpec(
    name="intfloat/multilingual-e5-small",
    revision="614241f622f53c4eeff9890bdc4f31cfecc418b3",
    files={"model.onnx": "onnx/model.onnx", "tokenizer.json": "onnx/tokenizer.json"},
    query_prefix="query: ",
    passage_prefix="passage: ",
)

MODELS = {E5_SMALL.name: E5_SMALL}


def models_dir() -> Path:
    return Path(os.getenv("ROBITA_MODELS_DIR", Path.home() / ".cache" / "robita" / "models"))


class OnnxEmbedder:
    """Mean pooling + normalización L2, igual que sentence-transformers para e5."""

    def __init__(self, spec: ModelSpec = E5_SMALL, model_dir: str | os.PathLike | None = None,
                 threads: int = 0) -> None:
        self.spec = spec
        self.model_dir = Path(model_dir) if model_dir else models_dir() / spec.dirname
        self.threads = threads
        self._session = None
        self._tok = None
        self._lock = threading.Lock()

    @property
    def name(self) -> str:
        return self.spec.name

    def available(self) -> bool:
        return all((self.model_dir / f).is_file() for f in self.spec.files)

    def load(self) -> None:
        with self._lock:
            if self._session is not None:
                return
            if not self.available():
                raise FileNotFoundError(
                    f"Faltan los ficheros de {self.spec.name} en {self.model_dir}. "
                    "Descárgalos con: python -m robita_cognitive.tools.fetch_model"
                )
            import onnxruntime as ort
            from tokenizers import Tokenizer

            opts = ort.SessionOptions()
            if self.threads:
                opts.intra_op_num_threads = self.threads
            providers = [p for p in ("CUDAExecutionProvider", "CPUExecutionProvider")
                         if p in ort.get_available_providers()]
            self._session = ort.InferenceSession(str(self.model_dir / "model.onnx"), opts, providers=providers)
            tok = Tokenizer.from_file(str(self.model_dir / "tokenizer.json"))
            tok.enable_truncation(self.spec.max_tokens)
            tok.enable_padding()
            self._tok = tok
            self._inputs = {i.name for i in self._session.get_inputs()}

    def _encode(self, texts: list[str], batch_size: int = 16) -> np.ndarray:
        self.load()
        out = []
        for i in range(0, len(texts), batch_size):
            enc = self._tok.encode_batch(texts[i:i + batch_size])
            ids = np.array([e.ids for e in enc], dtype=np.int64)
            mask = np.array([e.attention_mask for e in enc], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self._inputs:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self._session.run(None, feed)[0]           # (B, T, H)
            m = mask[..., None].astype(np.float32)
            emb = (hidden * m).sum(1) / np.clip(m.sum(1), 1e-9, None)
            out.append(emb / np.linalg.norm(emb, axis=1, keepdims=True))
        return np.vstack(out).astype(np.float32) if out else np.zeros((0, 0), np.float32)

    def encode_queries(self, texts: list[str]) -> np.ndarray:
        return self._encode([self.spec.query_prefix + t for t in texts])

    def encode_passages(self, texts: list[str]) -> np.ndarray:
        return self._encode([self.spec.passage_prefix + t for t in texts])
