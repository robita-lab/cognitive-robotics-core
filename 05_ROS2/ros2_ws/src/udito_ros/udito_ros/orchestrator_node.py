"""Arquitectura 3T - UDITO · Capa ejecutiva · C.C. (orquestador central en ROS 2).

Es el «jefe de proyecto»: recibe lo que oye el robot, decide la intención
y reparte las órdenes. Ningún actuador recibe órdenes de otro sitio.

Intenciones directas (rápidas, sin IA): parar, reír, chiste, dato curioso,
mover los ojos, expresiones de cara. El resto se pregunta a la capa
deliberativa (Cognitive) por /udito/cognitive/query.
"""
from __future__ import annotations

import json
import random
import threading
import time
import unicodedata
import uuid

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from udito_ros import topics
from udito_ros.paths import RESPONSES

STOP_WORDS = ["para", "parate", "detente", "silencio", "callate", "stop", "basta"]
LAUGH_WORDS = ["riete", "rie", "risa", "jaja", "carcajada"]
EYES_WORDS = ["mueve los ojos", "mover los ojos", "mueve tus ojos", "tus ojos",
              "los ojos", "guina", "guinale", "pestanea", "parpadea"]
EYES_CYCLE = [("wink", "guiño"), ("curious", "curioso"), ("wide", "ojos abiertos"),
              ("closed", "ojos cerrados"), ("love", "enamorado"), ("happy", "feliz")]


def norm(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    t = "".join(c if c.isalnum() or c.isspace() else " " for c in t)
    return " ".join(t.split())


def has_any(text: str, words: list[str]) -> bool:
    padded = f" {text} "
    return any(f" {norm(w)} " in padded for w in words)


def load_json(name: str) -> dict:
    try:
        return json.loads((RESPONSES / name).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


class Orchestrator(Node):
    def __init__(self) -> None:
        super().__init__("udito_cc")
        self.declare_parameter("mic_reopen_delay", 0.4)
        self.fun = load_json("fun_notes.json")
        self.face_cmds = load_json("face_commands.json").get("expressions", [])

        self.pub_say = self.create_publisher(String, topics.TTS_SAY, 10)
        self.pub_mic = self.create_publisher(Bool, topics.STT_ENABLE, 10)
        self.pub_face = self.create_publisher(String, topics.SPEECH_OUT, 10)
        self.pub_intent = self.create_publisher(String, topics.INTENT, 10)
        self.pub_query = self.create_publisher(String, topics.COG_QUERY, 10)
        self.create_subscription(String, topics.STT_TEXT, self._on_text, 10)
        self.create_subscription(String, topics.TTS_DONE, self._on_done, 10)
        self.create_subscription(String, topics.COG_ANSWER, self._on_answer, 10)

        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self.get_logger().info(
            f"C.C. listo — oye {topics.STT_TEXT}, ordena a {topics.TTS_SAY} y {topics.SPEECH_OUT}"
        )

    # ---------- utilidades de publicación ----------
    def _json(self, pub, payload: dict) -> None:
        m = String()
        m.data = json.dumps(payload, ensure_ascii=False)
        pub.publish(m)

    def _mic(self, on: bool) -> None:
        m = Bool()
        m.data = on
        self.pub_mic.publish(m)

    def say(self, text: str, emotion: str = "neutral", *, laugh: bool = False, label: str = "") -> str:
        req_id = uuid.uuid4().hex[:8]
        with self._lock:
            self._pending.add(req_id)
        self._mic(False)  # el robot no debe oírse a sí mismo
        self._json(self.pub_say, {"id": req_id, "text": text, "emotion": emotion,
                                  "laugh": laugh, "source": "cc", "label": label})
        return req_id

    def face(self, emotion: str, caption: str = "") -> None:
        self._json(self.pub_face, {"text": caption, "emotion": emotion,
                                   "source": "cc", "label": emotion})

    def intent(self, name: str, text: str, **args) -> None:
        self.get_logger().info(f"[intención] {name} ← «{text}»")
        self._json(self.pub_intent, {"name": name, "text": text, "args": args})

    # ---------- entrada: lo que oye el robot ----------
    def _on_text(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return
        t = norm(text)

        if has_any(t, STOP_WORDS) and len(t.split()) <= 3:
            self.intent("stop", text)
            self.face("neutral")
            self.say("Vale, me detengo.", "neutral", label="stop")
            return

        if has_any(t, LAUGH_WORDS):
            self.intent("laugh", text)
            self.say("", "laugh", laugh=True, label="risa")
            return

        if has_any(t, EYES_WORDS):
            self.intent("move_eyes", text)
            threading.Thread(target=self._eyes_cycle, daemon=True).start()
            return

        kw = self.fun.get("request_keywords", {})
        if has_any(t, kw.get("joke", [])) and self.fun.get("jokes"):
            self.intent("joke", text)
            joke = random.choice(self.fun["jokes"])["text"]
            self.say(joke, "happy", laugh=True, label="chiste")
            return

        if has_any(t, kw.get("curious_fact", [])) and self.fun.get("curious_facts"):
            self.intent("curious_fact", text)
            fact = random.choice(self.fun["curious_facts"])
            tpl = self.fun.get("intro_templates", {}).get(fact.get("intro", ""), "{body}.")
            self.say(tpl.format(body=fact["body"]), "curious", label="dato")
            return

        for expr in self.face_cmds:
            if has_any(t, expr.get("keywords", [])):
                self.intent("face_expression", text, expression=expr["id"])
                self.face(expr["id"])
                self.say(expr.get("reply", ""), expr["id"], label="cara")
                return

        # Nada directo: se lo pregunta a la capa deliberativa (Cognitive)
        self.intent("ask_cognitive", text)
        self.face("thinking", "pensando…")
        self._mic(False)
        self._json(self.pub_query, {"id": uuid.uuid4().hex[:8], "text": text})

    def _eyes_cycle(self) -> None:
        self._mic(False)
        for expr, caption in EYES_CYCLE:
            self.face(expr, caption)
            time.sleep(0.9)
        self.say("¿Te gustan mis ojos?", "happy", label="ojos")

    # ---------- respuestas ----------
    def _on_answer(self, msg: String) -> None:
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            data = {"text": msg.data}
        self.say(str(data.get("text", "")), str(data.get("emotion", "helpful")), label="cognitive")

    def _on_done(self, msg: String) -> None:
        try:
            req_id = str(json.loads(msg.data).get("id", ""))
        except json.JSONDecodeError:
            req_id = ""
        with self._lock:
            self._pending.discard(req_id)
            idle = not self._pending
        if idle:
            delay = float(self.get_parameter("mic_reopen_delay").value)
            threading.Timer(delay, self._reopen_mic).start()

    def _reopen_mic(self) -> None:
        with self._lock:
            if self._pending:
                return
        self._mic(True)


def main(args=None) -> None:
    rclpy.init(args=args)
    node = Orchestrator()
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
