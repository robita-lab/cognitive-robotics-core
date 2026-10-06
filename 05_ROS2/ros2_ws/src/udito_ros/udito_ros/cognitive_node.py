"""Arquitectura 3T - UDITO · Capa deliberativa · COGNITIVE (piensa y decide QUÉ decir).

Recibe preguntas del C.C. por /udito/cognitive/query y responde por
/udito/cognitive/answer. Nunca habla ni mueve nada por sí mismo.

- use_rag=false (por defecto): respuestas fijas de 04_KNOWLEDGE_CORE (rápido).
- use_rag=true: RAG completo del repo (FAISS + TinyLlama). Tarda en cargar.
"""
from __future__ import annotations

import json
import os
import queue
import threading

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

from udito_ros import topics
from udito_ros.paths import SERVICES, add_engine_paths

FALLBACK = "Todavía estoy aprendiendo sobre eso. ¿Me lo preguntas de otra forma?"


class CognitiveNode(Node):
    def __init__(self) -> None:
        super().__init__("udito_cognitive")
        self.declare_parameter("use_rag", False)
        self.use_rag = bool(self.get_parameter("use_rag").value)
        add_engine_paths("rag-engine")

        self.rag = None
        self.bqa = None
        self._ready = threading.Event()
        self._q: queue.Queue[dict] = queue.Queue()

        self.pub = self.create_publisher(String, topics.COG_ANSWER, 10)
        self.create_subscription(String, topics.COG_QUERY, self._on_query, 10)
        threading.Thread(target=self._load, daemon=True).start()
        threading.Thread(target=self._worker, daemon=True).start()

    def _load(self) -> None:
        from basic_qa_manager import BasicQAManager

        self.bqa = BasicQAManager()
        if self.use_rag:
            self.get_logger().info("Cargando RAG (puede tardar minutos)…")
            try:
                from rag_system import RAGSystem

                os.chdir(SERVICES / "rag-engine")
                self.rag = RAGSystem(
                    config_path=os.getenv(
                        "ROBITA_RAG_CONFIG",
                        str(SERVICES / "rag-engine" / "config" / "rag_config.json"),
                    ),
                    settings_path=str(SERVICES / "rag-engine" / "config" / "settings.json"),
                )
            except Exception as e:  # noqa: BLE001
                self.get_logger().error(f"RAG no disponible ({e}); sigo con respuestas fijas")
                self.rag = None
        self._ready.set()
        self.get_logger().info("Cognitive listo — modo " + ("RAG" if self.rag else "respuestas fijas"))

    def _on_query(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            data = {"text": msg.data}
        self._q.put(data)

    def _answer(self, text: str) -> dict:
        if self.rag is not None:
            r = self.rag.process_query(text) or {}
            ans = (r.get("answer") or "").strip()
            if ans:
                return {"text": ans, "emotion": r.get("emotion", "helpful"),
                        "source": r.get("source", "rag")}
        r = self.bqa.find_basic_answer(text) if self.bqa else None
        if r and r.get("answer"):
            ans = r["answer"]
            try:
                ans = self.bqa.format_answer(ans)
            except Exception:  # noqa: BLE001
                pass
            return {"text": ans, "emotion": r.get("emotion", "helpful"), "source": "basic_qa"}
        return {"text": FALLBACK, "emotion": "sorry", "source": "fallback"}

    def _worker(self) -> None:
        self._ready.wait()
        while rclpy.ok():
            data = self._q.get()
            text = str(data.get("text", "")).strip()
            try:
                out = self._answer(text)
            except Exception as e:  # noqa: BLE001
                self.get_logger().error(f"Cognitive error: {e}")
                out = {"text": FALLBACK, "emotion": "sorry", "source": "error"}
            out["id"] = data.get("id", "")
            self.get_logger().info(f"[cerebro] «{text}» → {out['text'][:80]}")
            m = String()
            m.data = json.dumps(out, ensure_ascii=False)
            self.pub.publish(m)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = CognitiveNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
