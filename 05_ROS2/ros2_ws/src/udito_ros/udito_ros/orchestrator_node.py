"""Arquitectura 3T - UDITO · Capa ejecutiva · C.C. (orquestador central en ROS 2).

Es el «jefe de proyecto»: recibe lo que oye el robot, reconoce la orden
(config/intents.yaml) y reparte el trabajo:
  - voz       → /udito/tts/say      (actuador TTS)
  - cara      → /udito/speech_out   (actuador pantalla)
  - cuerpo    → /udito/intent       (orquestador del cuerpo: cuello y base)
Cada paso se publica también en /udito/cc/log para verlo en la consola.
Ningún actuador recibe órdenes de otro sitio.
"""
from __future__ import annotations

import datetime
import json
import random
import threading
import time
import uuid

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from udito_ros import intents as I
from udito_ros import topics
from udito_ros.paths import RESPONSES

EYES_CYCLE = ["wink", "curious", "wide", "closed", "love", "happy"]


class Orchestrator(Node):
    def __init__(self) -> None:
        super().__init__("udito_cc")
        self.declare_parameter("mic_reopen_delay", 0.4)
        self.declare_parameter("use_cognitive", False)  # RAG desactivado en esta etapa
        self.declare_parameter("match_threshold", 0.72)
        cat = I.load()
        self.intents, self.unknown = cat["intents"], cat["unknown"]
        try:
            self.fun = json.loads((RESPONSES / "fun_notes.json").read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            self.fun = {}
        self.powered = False

        self.pub_say = self.create_publisher(String, topics.TTS_SAY, 10)
        self.pub_mic = self.create_publisher(Bool, topics.STT_ENABLE, 10)
        self.pub_face = self.create_publisher(String, topics.SPEECH_OUT, 10)
        self.pub_intent = self.create_publisher(String, topics.INTENT, 10)
        self.pub_query = self.create_publisher(String, topics.COG_QUERY, 10)
        self.pub_log = self.create_publisher(String, topics.CC_LOG, 10)
        self.create_subscription(String, topics.STT_TEXT, self._on_text, 10)
        self.create_subscription(String, topics.TTS_DONE, self._on_done, 10)
        self.create_subscription(String, topics.COG_ANSWER, self._on_answer, 10)
        self.create_subscription(Bool, topics.POWER, self._on_power, 10)

        self._pending: set[str] = set()
        self._lock = threading.Lock()
        self.get_logger().info(f"C.C. listo — {len(self.intents)} órdenes cargadas de {I.intents_file()}")

    # ---------- publicación ----------
    def _json(self, pub, payload: dict) -> None:
        m = String()
        m.data = json.dumps(payload, ensure_ascii=False)
        pub.publish(m)

    def log(self, text: str) -> None:
        self.get_logger().info(text)
        m = String()
        m.data = text
        self.pub_log.publish(m)

    def _mic(self, on: bool) -> None:
        m = Bool()
        m.data = on
        self.pub_mic.publish(m)

    def say(self, text: str, emotion: str = "neutral", *, laugh: bool = False, label: str = "") -> None:
        if not text and not laugh:
            return
        req_id = uuid.uuid4().hex[:8]
        with self._lock:
            self._pending.add(req_id)
        self._mic(False)  # el robot no debe oírse a sí mismo
        self._json(self.pub_say, {"id": req_id, "text": text, "emotion": emotion,
                                  "laugh": laugh, "source": "cc", "label": label})
        self.log(f"→ {topics.TTS_SAY}  «{text or '(risa)'}»")

    def face(self, emotion: str, caption: str = "") -> None:
        self._json(self.pub_face, {"text": caption, "emotion": emotion, "source": "cc", "label": emotion})

    def body(self, intent_id: str, text: str, body: dict) -> None:
        payload = {"name": body.get("name", intent_id), "args": body.get("args", {}),
                   "intent": intent_id, "text": text, "source": "udito_cc",
                   "stamp": time.time()}
        self._json(self.pub_intent, payload)
        self.log(f"→ {topics.INTENT}  {json.dumps(payload['name'])} {json.dumps(payload['args'], ensure_ascii=False)}")

    # ---------- encendido ----------
    def _on_power(self, msg: Bool) -> None:
        self.powered = bool(msg.data)
        if self.powered:
            self.log("ENCENDIDO")
            self.face("happy")
            self.say("Hola, soy UDITO. Estoy listo.", "happy", label="encendido")
        else:
            self.log("APAGADO")
            self.face("sleepy")
            self.say("Me apago. Hasta luego.", "sleepy", label="apagado")

    # ---------- entrada: lo que oye el robot ----------
    def _on_text(self, msg: String) -> None:
        text = msg.data.strip()
        if not text:
            return
        if not self.powered:
            self.log(f"(apagado) ignoro «{text}» — pulsa ENCENDER")
            return
        it, score = I.match(text, self.intents, float(self.get_parameter("match_threshold").value))
        if it is None:
            if bool(self.get_parameter("use_cognitive").value):
                self.log(f"«{text}» no es una orden ({score:.2f}) → pregunto al Cognitive")
                self.face("thinking")
                self._json(self.pub_query, {"id": uuid.uuid4().hex[:8], "text": text})
            else:
                self.log(f"«{text}» no es una orden conocida (parecido {score:.2f})")
                self.face(self.unknown.get("face", "confused"))
                self.say(self.unknown.get("say", ""), self.unknown.get("face", "confused"), label="desconocida")
            return

        self.log(f"«{text}» → intención {it['id']} (confianza {score:.2f})")
        self.execute(it, text)

    def execute(self, it: dict, text: str) -> None:
        face = it.get("face", "neutral")
        say = it.get("say", "")
        special = it.get("special")
        if special == "joke" and self.fun.get("jokes"):
            say = random.choice(self.fun["jokes"])["text"]
        elif special == "fact" and self.fun.get("curious_facts"):
            fact = random.choice(self.fun["curious_facts"])
            tpl = self.fun.get("intro_templates", {}).get(fact.get("intro", ""), "{body}.")
            say = tpl.format(body=fact["body"])
        elif special == "time":
            now = datetime.datetime.now()
            say = f"Son las {now.hour} y {now.minute:02d}."
        elif special == "eyes":
            threading.Thread(target=self._eyes_cycle, args=(say,), daemon=True).start()
            return

        if it.get("body"):
            self.body(it["id"], text, it["body"])
        self.face(face)
        self.say(say, face, laugh=bool(it.get("laugh")), label=it["id"])

    def _eyes_cycle(self, closing: str) -> None:
        self._mic(False)
        self.log(f"→ {topics.SPEECH_OUT}  ciclo de ojos {EYES_CYCLE}")
        for expr in EYES_CYCLE:
            self.face(expr)
            time.sleep(0.8)
        self.say(closing, "happy", label="ojos")

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
            threading.Timer(float(self.get_parameter("mic_reopen_delay").value), self._reopen_mic).start()

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
