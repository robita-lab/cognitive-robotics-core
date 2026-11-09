"""Nodo ROS 2 `robita_cognitive`: capa fina sobre robita_cognitive.core.

Ofrece dos entradas al mismo motor:

1. Acción `Think` (robita_interfaces/action/Think) — la interfaz definitiva
   (D3). Feedback = una frase por mensaje, para que el TTS empiece antes.
   Cancelable. Un goal nuevo interrumpe al que esté en curso (el robot solo
   mantiene un turno a la vez).
2. Adaptador de topics compatible con el `cognitive_node` de udito_ros:
   /udito/cognitive/query  {"id","text"[,"session_id"]}
   /udito/cognitive/answer {"id","text","emotion","source",...}
   Así el C.C. actual funciona sin cambios mientras llega el Behavior Tree.

Los backends se cargan en segundo plano (normativa: ~1 s; legacy: minutos);
mientras tanto contestan las reglas / respuestas fijas.
"""

from __future__ import annotations

import json
import logging
import queue
import threading
import time
import uuid

import rclpy
from rclpy.action import ActionServer, CancelResponse, GoalResponse
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.node import Node
from std_msgs.msg import String

from robita_interfaces.action import Think

from .core import CancelToken, ThinkRequest
from .factory import EngineConfig, build_engine


class CognitiveNode(Node):
    def __init__(self) -> None:
        super().__init__("robita_cognitive")
        p = self.declare_parameter
        p("repo_root", "")
        p("use_rag", True)
        p("rag_backend", "normativa")   # normativa | legacy | none
        p("index_dir", "")
        p("rag_config", "")
        p("rag_rebuild", False)
        p("memory_turns", 8)
        p("memory_ttl_s", 300.0)
        p("think_action", "/udito/cognitive/think")
        p("topic_adapter", True)
        p("query_topic", "/udito/cognitive/query")
        p("answer_topic", "/udito/cognitive/answer")
        p("topic_session_idle_s", 120.0)
        g = self.get_parameter

        self.engine = build_engine(
            EngineConfig(
                repo_root=g("repo_root").value,
                use_rag=g("use_rag").value,
                rag_backend=g("rag_backend").value,
                index_dir=g("index_dir").value,
                rag_config=g("rag_config").value,
                rag_rebuild=g("rag_rebuild").value,
                memory_turns=g("memory_turns").value,
                memory_ttl_s=g("memory_ttl_s").value,
            )
        )
        self._warmup = self.engine.warmup_async()
        threading.Thread(target=self._report_ready, daemon=True).start()

        self._cb = ReentrantCallbackGroup()
        self._lock = threading.Lock()
        self._tokens: dict[bytes, CancelToken] = {}
        self._active: bytes | None = None

        self._action = ActionServer(
            self,
            Think,
            g("think_action").value,
            execute_callback=self._execute,
            goal_callback=lambda _goal: GoalResponse.ACCEPT,
            handle_accepted_callback=self._on_accepted,
            cancel_callback=self._on_cancel,
            callback_group=self._cb,
        )

        if g("topic_adapter").value:
            self._idle_s = float(g("topic_session_idle_s").value)
            self._topic_session = ""
            self._topic_last = 0.0
            self._q: queue.Queue[dict] = queue.Queue()
            self._pub = self.create_publisher(String, g("answer_topic").value, 10)
            self.create_subscription(
                String, g("query_topic").value, self._on_query, 10, callback_group=self._cb
            )
            threading.Thread(target=self._topic_worker, daemon=True).start()

        self.get_logger().info(
            f"robita_cognitive en marcha · acción {g('think_action').value} · "
            f"topics {'sí' if g('topic_adapter').value else 'no'} · backends {self.engine.status()}"
        )

    def _report_ready(self) -> None:
        self._warmup.join()
        self.get_logger().info(f"backends cargados: {self.engine.status()}")

    # ---------------------------------------------------------------- acción
    @staticmethod
    def _gid(goal_handle) -> bytes:
        return bytes(goal_handle.goal_id.uuid)

    def _on_accepted(self, goal_handle) -> None:
        gid = self._gid(goal_handle)
        with self._lock:
            if self._active is not None and self._active in self._tokens:
                self.get_logger().info("Think nuevo: interrumpo el turno en curso")
                self._tokens[self._active].cancel()
            self._tokens[gid] = CancelToken()
            self._active = gid
        goal_handle.execute()

    def _on_cancel(self, goal_handle) -> CancelResponse:
        with self._lock:
            tok = self._tokens.get(self._gid(goal_handle))
        if tok:
            tok.cancel()
        return CancelResponse.ACCEPT

    def _execute(self, goal_handle):
        gid = self._gid(goal_handle)
        with self._lock:
            tok = self._tokens.setdefault(gid, CancelToken())
        g = goal_handle.request

        def on_partial(sentence: str, index: int) -> None:
            fb = Think.Feedback()
            fb.partial_text = sentence
            fb.index = index
            goal_handle.publish_feedback(fb)

        try:
            r = self.engine.think(
                ThinkRequest(session_id=g.session_id or "default", turn_id=g.turn_id, text=g.text, lang=g.lang),
                cancel=tok,
                on_partial=on_partial,
            )
        finally:
            with self._lock:
                self._tokens.pop(gid, None)
                if self._active == gid:
                    self._active = None

        res = Think.Result()
        res.text, res.emotion, res.source = r.text, r.emotion, r.source
        res.model_id, res.latency_ms = r.model_id, float(r.latency_ms)
        if r.cancelled or tok.cancelled:
            if goal_handle.is_cancel_requested:
                goal_handle.canceled()
            else:  # interrumpido por un goal nuevo
                goal_handle.abort()
            return res
        goal_handle.succeed()
        return res

    # ---------------------------------------------------------------- topics
    def _on_query(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
            if not isinstance(data, dict):
                data = {"text": str(data)}
        except json.JSONDecodeError:
            data = {"text": msg.data}
        self._q.put(data)

    def _topic_session_id(self) -> str:
        now = time.monotonic()
        if not self._topic_session or now - self._topic_last > self._idle_s:
            self._topic_session = f"topics-{uuid.uuid4().hex[:8]}"
        self._topic_last = now
        return self._topic_session

    def _topic_worker(self) -> None:
        while rclpy.ok():
            try:
                data = self._q.get(timeout=0.5)
            except queue.Empty:
                continue
            req_id = str(data.get("id", ""))
            sid = str(data.get("session_id") or self._topic_session_id())
            r = self.engine.think(ThinkRequest(session_id=sid, turn_id=req_id, text=str(data.get("text", ""))))
            out = {
                "id": req_id,
                "text": r.text,
                "emotion": r.emotion,
                "source": r.source,
                "detail": r.detail,
                "latency_ms": round(r.latency_ms, 1),
                "session_id": sid,
            }
            m = String()
            m.data = json.dumps(out, ensure_ascii=False)
            self._pub.publish(m)


def main(args=None) -> None:
    # El núcleo usa `logging`; lo mandamos a stderr para verlo junto al log de ROS.
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")
    rclpy.init(args=args)
    node = CognitiveNode()
    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == "__main__":
    main()
