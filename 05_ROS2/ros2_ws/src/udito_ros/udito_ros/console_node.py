"""Arquitectura híbrida - UDITO · Consola del operador (nodo ROS 2), estilo robot ROBITA-LAB.

Dibuja el robot completo: cara animada en el visor, órdenes en la pantalla del pecho
y ruedas que giran cuando el C.C. envía una orden de movimiento al cuerpo.
Solo escucha y publica en los mismos topics que el robot real:

  - ENCENDER / APAGAR            → /udito/power
  - MANTÉN PARA HABLAR (espacio) → /udito/stt/ptt
  - Órdenes del pecho y botones de expresión → /udito/stt/text (como si se dijeran)
  - Escucha: /udito/speech_out (cara), /udito/intent (cuerpo), /udito/tts/say,
    /udito/stt/text, /udito/state, /udito/cc/log
"""
from __future__ import annotations

import json
import math
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from udito_ros import intents as I
from udito_ros import topics

# ---------------------------------------------------------------- colores
BG = (10, 14, 26)
TOPBAR = (16, 22, 40)
PANEL = (20, 26, 46)
WHITE = (238, 243, 250)
SHELL = (214, 224, 236)
EDGE = (28, 40, 58)
VISOR = (14, 26, 40)
CYAN = (70, 225, 240)
DIM = (110, 125, 160)
GREEN = (80, 220, 140)
ORANGE = (255, 170, 60)
BLUE = (40, 170, 255)
RED = (240, 80, 80)
CHIP = (24, 40, 58)

NODES = [("udito_stt", "Oído"), ("udito_tts", "Voz"), ("udito_cc", "C.C."),
         ("udito_body_example", "Cuerpo")]

# Botones de expresión → orden equivalente (pasan por el C.C., como la voz)
EXPRESSION_BUTTONS = [("feliz", "sonríe"), ("triste", "ponte triste"), ("sorpresa", "sorpréndete"),
                      ("guiño", "guiña un ojo"), ("ojos", "mueve los ojos"), ("dormido", "duérmete")]

FACE_NAMES = {"happy": "feliz", "sad": "triste", "sorry": "triste", "surprised": "sorpresa",
              "wink": "guiño", "sleepy": "dormido", "laugh": "risa", "thinking": "pensando",
              "curious": "curioso", "confused": "confuso", "proud": "orgulloso", "love": "enamorado",
              "listening": "escuchando", "neutral": "neutral", "idle": "neutral", "helpful": "neutral",
              "wide": "ojos abiertos", "closed": "ojos cerrados", "angry": "enfadado",
              "scared": "asustado", "tongue": "lengua", "speaking": "hablando", "informative": "neutral"}


class Console(Node):
    def __init__(self) -> None:
        super().__init__("udito_console")
        self.intents = I.load()["intents"]
        self.lock = threading.Lock()
        self.chat: list[tuple[str, str]] = []     # (quién, texto)
        self.log: list[tuple[str, tuple]] = []    # (texto, color)
        self.emotion = "neutral"
        self.state = "idle"
        self.stt_sec = None
        self.powered = False
        self.power_t = 0.0                        # instante del último cambio de encendido
        self.last_intent: dict | None = None
        self.active_order = ""                    # id de la orden en curso (se ilumina en el pecho)
        self.active_t = 0.0
        self.motion = ""                          # follow | go_to | rotate | ""
        self.motion_until = 0.0
        self.head_action = ""                     # look | nod | shake
        self.head_args: dict = {}
        self.head_t = 0.0
        self.env: list[float] = []                # volumen de la voz cada 1/fps s (sincroniza la boca)
        self.env_fps = 20
        self.env_t = 0.0

        self.pub_power = self.create_publisher(Bool, topics.POWER, 10)
        self.pub_ptt = self.create_publisher(Bool, topics.STT_PTT, 10)
        self.pub_text = self.create_publisher(String, topics.STT_TEXT, 10)
        self.pub_say = self.create_publisher(String, topics.SAY_REQUEST, 10)
        # caja «Haz que diga»
        self.typed = ""
        self.typing = False
        self.say_emotion = "neutral"
        self.create_subscription(String, topics.STT_TEXT, self._heard, 10)
        self.create_subscription(String, topics.TTS_SAY, self._said, 10)
        self.create_subscription(String, topics.CC_LOG, self._cc, 10)
        self.create_subscription(String, topics.STATE, self._state, 10)
        self.create_subscription(String, topics.SPEECH_OUT, self._face, 10)
        self.create_subscription(String, topics.INTENT, self._intent, 10)

    # ---------------------------------------------------------- utilidades
    @staticmethod
    def _j(raw: str) -> dict:
        try:
            d = json.loads(raw)
            return d if isinstance(d, dict) else {}
        except json.JSONDecodeError:
            return {}

    def add_chat(self, who: str, text: str) -> None:
        with self.lock:
            self.chat = (self.chat + [(who, text)])[-12:]

    def add_log(self, text: str, color: tuple) -> None:
        with self.lock:
            self.log = (self.log + [(text, color)])[-40:]

    # ---------------------------------------------------------- suscripciones
    def _heard(self, m: String) -> None:
        self.add_chat("tú", m.data)

    def _said(self, m: String) -> None:
        d = self._j(m.data)
        txt = d.get("text") or ("(risa)" if d.get("laugh") else "")
        if txt:
            self.add_chat("UDITO", txt)
        label = d.get("label", "")
        if label and label not in ("cc", "encendido", "apagado", "desconocida", "cognitive"):
            self.active_order, self.active_t = label, time.time()

    def _cc(self, m: String) -> None:
        self.add_log(m.data, BLUE if m.data.startswith("→") else ORANGE)

    def _state(self, m: String) -> None:
        d = self._j(m.data)
        if "stt_sec" in d:
            self.stt_sec = d["stt_sec"]
        if d.get("state"):
            self.state = d["state"]
        if d.get("state") == "speaking":
            self.env, self.env_fps, self.env_t = d.get("env") or [], int(d.get("fps") or 20), time.time()

    def _face(self, m: String) -> None:
        em = str(self._j(m.data).get("emotion") or "neutral")
        self.emotion = "sad" if em == "sorry" else em

    def _intent(self, m: String) -> None:
        d = self._j(m.data)
        self.last_intent = d
        name, args = d.get("name", ""), d.get("args", {}) or {}
        now = time.time()
        if name == "follow":
            self.motion, self.motion_until = "follow", now + 3600
        elif name == "go_to":
            self.motion, self.motion_until = "go_to", now + 4
        elif name == "rotate":
            self.motion, self.motion_until = "rotate", now + 3.5
        elif name == "stop":
            self.motion, self.motion_until = "", 0.0
            self.head_action = ""
        elif name in ("look", "head_gesture"):
            self.head_action = "look" if name == "look" else str(args.get("gesture", "nod"))
            self.head_args, self.head_t = args, now

    # ---------------------------------------------------------- acciones
    def power(self, on: bool) -> None:
        self.powered, self.power_t = on, time.time()
        if not on:
            self.motion, self.head_action = "", ""
        msg = Bool()
        msg.data = on
        self.pub_power.publish(msg)

    def ptt(self, on: bool) -> None:
        msg = Bool()
        msg.data = on
        self.pub_ptt.publish(msg)

    def say_free(self) -> None:
        """Envía la frase escrita al C.C. (que la reparte a voz y cara)."""
        text = self.typed.strip()
        if not text:
            return
        msg = String()
        msg.data = json.dumps({"text": text, "emotion": I.EMOTIONS.get(self.say_emotion, "neutral")},
                              ensure_ascii=False)
        self.pub_say.publish(msg)
        self.typed = ""

    def say_text(self, text: str) -> None:
        msg = String()
        msg.data = text
        self.pub_text.publish(msg)


# ==================================================================== dibujo
class Painter:
    def __init__(self, pygame, screen) -> None:
        self.pg = pygame
        self.s = screen
        font = lambda n, b=False: pygame.font.SysFont("dejavusans", n, bold=b)  # noqa: E731
        self.f = {k: font(*v) for k, v in {
            "xs": (11,), "s": (12,), "sb": (12, True), "m": (14,), "mb": (14, True),
            "l": (18, True), "xl": (26, True)}.items()}
        self.blink_next = time.time() + 3.0

    # ------------------------------------------------------------ texto
    def text(self, txt, key, color, pos, center=False):
        surf = self.f[key].render(txt, True, color)
        rect = surf.get_rect(center=pos) if center else surf.get_rect(topleft=pos)
        self.s.blit(surf, rect)
        return rect

    def wrap(self, txt, key, width):
        out, cur = [], ""
        for w in txt.split(" "):
            test = (cur + " " + w).strip()
            if self.f[key].size(test)[0] > width and cur:
                out.append(cur)
                cur = w
            else:
                cur = test
        return out + [cur]

    # ------------------------------------------------------------ cara
    def face(self, cx, cy, emotion, on, boot, t, speaking, head_dx):
        pg, s = self.pg, self.s
        if not on:
            return
        a = min(1.0, boot)                         # 0→1 durante el arranque
        col = tuple(int(c * a) for c in CYAN)
        glow = tuple(int(c * a * 0.35) for c in CYAN)
        ex_l, ex_r, ey = cx - 55 + head_dx, cx + 55 + head_dx, cy - 18
        blink = time.time() >= self.blink_next
        if blink and time.time() > self.blink_next + 0.14:
            self.blink_next = time.time() + 2.5 + (t * 7) % 2.5
        open_k = a if boot < 1 else 1.0           # ojos se abren al arrancar

        def eye_oval(x, y, w=44, h=52, k=1.0):
            hh = max(4, int(h * k * open_k))
            pg.draw.ellipse(s, glow, (x - w // 2 - 5, y - hh // 2 - 5, w + 10, hh + 10))
            pg.draw.ellipse(s, col, (x - w // 2, y - hh // 2, w, hh))

        def eye_arc(x, y, up=True):
            r = pg.Rect(x - 30, y - 18, 60, 46)
            for g in (6, 3):
                pg.draw.arc(s, glow, r.inflate(g * 2, g * 2), 0.3 if up else math.pi + 0.3,
                            math.pi - 0.3 if up else 2 * math.pi - 0.3, 3)
            pg.draw.arc(s, col, r, 0.3 if up else math.pi + 0.3, math.pi - 0.3 if up else 2 * math.pi - 0.3, 7)

        def eye_line(x, y):
            pg.draw.line(s, col, (x - 26, y), (x + 26, y), 7)

        def heart(x, y):
            pg.draw.circle(s, col, (x - 11, y - 6), 13)
            pg.draw.circle(s, col, (x + 11, y - 6), 13)
            pg.draw.polygon(s, col, [(x - 24, y - 2), (x + 24, y - 2), (x, y + 24)])

        em = emotion
        if blink and em not in ("sleepy", "closed", "wink", "happy", "laugh", "love"):
            eye_line(ex_l, ey)
            eye_line(ex_r, ey)
        elif em in ("happy", "laugh", "proud", "helpful"):
            eye_arc(ex_l, ey)
            eye_arc(ex_r, ey)
        elif em in ("sad", "sorry"):
            eye_oval(ex_l, ey + 6, 40, 34)
            eye_oval(ex_r, ey + 6, 40, 34)
            pg.draw.line(s, col, (ex_l - 26, ey - 30), (ex_l + 18, ey - 20), 5)
            pg.draw.line(s, col, (ex_r + 26, ey - 30), (ex_r - 18, ey - 20), 5)
        elif em in ("surprised", "wide", "scared"):
            eye_oval(ex_l, ey, 50, 62)
            eye_oval(ex_r, ey, 50, 62)
        elif em == "wink":
            eye_arc(ex_l, ey)
            eye_oval(ex_r, ey)
        elif em in ("sleepy", "closed"):
            eye_line(ex_l, ey + 6)
            eye_line(ex_r, ey + 6)
        elif em == "love":
            heart(ex_l, ey)
            heart(ex_r, ey)
        elif em in ("thinking", "curious", "confused"):
            eye_oval(ex_l, ey - 4, 40, 46)
            eye_oval(ex_r, ey + 4, 40, 34)
        elif em == "angry":
            eye_oval(ex_l, ey + 4, 42, 36)
            eye_oval(ex_r, ey + 4, 42, 36)
            pg.draw.line(s, col, (ex_l - 24, ey - 26), (ex_l + 20, ey - 14), 6)
            pg.draw.line(s, col, (ex_r + 24, ey - 26), (ex_r - 20, ey - 14), 6)
        elif em == "listening":
            eye_oval(ex_l, ey, 48, 58)
            eye_oval(ex_r, ey, 48, 58)
        else:
            eye_oval(ex_l, ey)
            eye_oval(ex_r, ey)

        # boca
        my = cy + 38
        mx = cx + head_dx
        if speaking is not None and speaking is not False:
            lvl = speaking if isinstance(speaking, float) else abs(math.sin(t * 14))
            h = 4 + int(30 * lvl)
            if lvl < 0.08:   # pausa entre palabras: boca cerrada
                pg.draw.line(s, col, (mx - 20, my), (mx + 20, my), 5)
            else:
                pg.draw.ellipse(s, col, (mx - 24, my - h // 2, 48, h))
        elif em in ("sad", "sorry", "angry"):
            pg.draw.arc(s, col, (mx - 34, my - 2, 68, 40), 0.4, math.pi - 0.4, 6)
        elif em in ("surprised", "scared", "wide"):
            pg.draw.ellipse(s, col, (mx - 14, my - 14, 28, 30), 5)
        elif em in ("sleepy", "closed"):
            self.text("z z", "l", col, (mx + 70, cy - 60), center=True)
            pg.draw.line(s, col, (mx - 16, my + 6), (mx + 16, my + 6), 5)
        elif em in ("thinking", "confused"):
            for i in range(3):
                pg.draw.circle(s, col, (mx - 18 + i * 18, my + 8), 5 if int(t * 3) % 3 == i else 3)
        elif em == "laugh":
            pg.draw.ellipse(s, col, (mx - 30, my - 8, 60, 34))
            pg.draw.rect(s, VISOR, (mx - 32, my - 10, 64, 16))
        else:
            pg.draw.arc(s, col, (mx - 38, my - 26, 76, 48), math.pi + 0.35, 2 * math.pi - 0.35, 6)

    # ------------------------------------------------------------ robot
    def robot(self, node: Console, cx, top, t, ptt_on):
        pg, s = self.pg, self.s
        on = node.powered
        boot = (time.time() - node.power_t) / 1.2 if on else 0.0
        moving = node.motion and time.time() < node.motion_until
        if node.motion and not moving:
            node.motion = ""
        bob = int(3 * math.sin(t * 10)) if moving else 0
        sway = int(10 * math.sin(t * 2.2)) if node.motion == "follow" and moving else 0
        cx += sway

        # cabeza: giro / asentir / negar
        head_dx = head_dy = 0
        ha_t = time.time() - node.head_t
        if node.head_action == "look" and ha_t < 4:
            d = -1 if node.head_args.get("direction") == "left" else 1
            head_dx = int(d * 26 * min(1.0, ha_t * 3) * (1 if ha_t < 3 else max(0.0, 4 - ha_t)))
        elif node.head_action == "nod" and ha_t < 2:
            head_dy = int(10 * math.sin(ha_t * 12))
        elif node.head_action == "shake" and ha_t < 2:
            head_dx = int(18 * math.sin(ha_t * 12))

        white = WHITE if on else (120, 128, 140)
        shell = SHELL if on else (95, 102, 114)
        top += bob

        # sombra
        pg.draw.ellipse(s, (6, 9, 18), (cx - 230, top + 676, 460, 22))

        # ruedas (detrás del cuerpo)
        spin = t * (9 if node.motion != "rotate" else 14) if moving else 0
        for side in (-1, 1):
            wc = (cx + side * 150, top + 650)
            pg.draw.ellipse(s, EDGE, (wc[0] - 62, wc[1] - 36, 124, 72))
            pg.draw.ellipse(s, (88, 96, 108) if on else (60, 64, 72), (wc[0] - 56, wc[1] - 30, 112, 60))
            for k in range(6):
                ang = spin * side + k * math.pi / 3
                pg.draw.line(s, (130, 138, 150) if on else (75, 80, 88), wc,
                             (wc[0] + int(48 * math.cos(ang)), wc[1] + int(24 * math.sin(ang))), 4)
            pg.draw.ellipse(s, (160, 168, 180) if on else (90, 95, 104), (wc[0] - 18, wc[1] - 10, 36, 20))
        if moving:  # líneas de velocidad
            for i in range(3):
                y = top + 640 + i * 14
                x0 = cx - 260 - int((t * 300 + i * 40) % 80)
                pg.draw.line(s, (40, 70, 100), (x0, y), (x0 + 40, y), 3)

        # brazos
        bt = top + 300
        for side in (-1, 1):
            arm = pg.Rect(0, 0, 58, 180)
            arm.center = (cx + side * 252, bt + 120 + (int(6 * math.sin(t * 10 + side)) if moving else 0))
            pg.draw.ellipse(s, EDGE, arm.inflate(10, 10))
            pg.draw.ellipse(s, shell, arm)

        # cuerpo
        body = [(cx - 210, bt), (cx + 210, bt), (cx + 232, bt + 290),
                (cx + 188, bt + 330), (cx - 188, bt + 330), (cx - 232, bt + 290)]
        pg.draw.polygon(s, EDGE, [(x + (5 if x > cx else -5), y + 5) for x, y in body])
        pg.draw.polygon(s, white, body)
        pg.draw.lines(s, shell, False, [(cx - 180, bt + 268), (cx, bt + 318), (cx + 180, bt + 268)], 5)

        # cuello
        pg.draw.rect(s, EDGE, (cx - 62, top + 270, 124, 34), border_radius=10)
        pg.draw.rect(s, (70, 80, 95), (cx - 56, top + 274, 112, 26), border_radius=8)

        # cabeza
        hx, hy = cx + head_dx // 2, top + head_dy
        head = pg.Rect(hx - 175, hy, 350, 270)
        for dx in (-188, 188):
            pg.draw.ellipse(s, EDGE, (hx + dx - 26, hy + 100, 52, 80))
            pg.draw.ellipse(s, shell, (hx + dx - 22, hy + 104, 44, 72))
        pg.draw.ellipse(s, EDGE, head.inflate(14, 14))
        pg.draw.ellipse(s, white, head)
        pg.draw.ellipse(s, shell, head.inflate(-20, -20), 6)
        visor = pg.Rect(hx - 138, hy + 42, 276, 186)
        pg.draw.rect(s, EDGE, visor.inflate(10, 10), border_radius=82)
        lit = (VISOR if on else (6, 8, 12))
        pg.draw.rect(s, lit, visor, border_radius=78)
        if on:
            pg.draw.ellipse(s, (30, 50, 70), (hx - 112, hy + 56, 120, 38))
        face_em = "listening" if ptt_on else node.emotion
        mouth = False
        if node.state == "speaking":
            if node.env:
                k = int((time.time() - node.env_t) * node.env_fps)
                mouth = float(node.env[k]) if 0 <= k < len(node.env) else 0.0
            else:
                mouth = True
        self.face(hx, hy + 135, face_em, on, boot, t, mouth, head_dx // 2)
        if not on:
            self.text("apagado", "s", (60, 70, 90), (hx, hy + 135), center=True)

        # pantalla del pecho: órdenes
        ch = pg.Rect(cx - 188, bt + 18, 376, 250)
        pg.draw.rect(s, EDGE, ch.inflate(10, 10), border_radius=22)
        pg.draw.rect(s, VISOR if on else (6, 8, 12), ch, border_radius=18)
        rects = []
        if on:
            self.text("ÓRDENES  ·  dilas o tócalas", "sb", CYAN, (ch.x + 16, ch.y + 8))
            mouse = pg.mouse.get_pos()
            active = node.active_order if time.time() - node.active_t < 4 else ""
            if node.motion and moving:
                active = {"follow": "follow_me", "go_to": "come_here", "rotate": "turn_around"}.get(node.motion, active)
            for i, it in enumerate(node.intents[:20]):
                col, row = divmod(i, 10)
                r = pg.Rect(ch.x + 12 + col * 180, ch.y + 30 + row * 21, 172, 19)
                hi = it["id"] == active
                hov = r.collidepoint(mouse)
                pg.draw.rect(s, BLUE if hi else ((40, 64, 90) if hov else CHIP), r, border_radius=10)
                lbl = it.get("label", it["id"]) + (" ⚙" if it.get("body") else "")
                self.text(f"{i + 1:>2}  {lbl}", "xs", WHITE, (r.x + 8, r.y + 3))
                rects.append((r, it))
        return rects

    # ------------------------------------------------------------ paneles
    def left(self, node: Console, rect, ptt_on):
        pg, s = self.pg, self.s
        pg.draw.rect(s, PANEL, rect, border_radius=14)
        ptt = pg.Rect(rect.x + 15, rect.y + 15, rect.w - 30, 80)
        color = RED if ptt_on else (BLUE if node.powered else CHIP)
        pg.draw.rect(s, color, ptt, border_radius=40)
        if not node.powered:
            self.text("Primero pulsa ENCENDER", "mb", DIM, ptt.center, center=True)
        elif ptt_on:
            self.text("GRABANDO…", "l", WHITE, (ptt.centerx, ptt.y + 30), center=True)
            self.text("suelta para enviar", "s", WHITE, (ptt.centerx, ptt.y + 56), center=True)
        else:
            self.text("MANTÉN PARA HABLAR", "l", WHITE, (ptt.centerx, ptt.y + 30), center=True)
            self.text("o barra espaciadora", "s", (220, 240, 255), (ptt.centerx, ptt.y + 56), center=True)

        # conversación (de abajo hacia arriba en su zona)
        split = rect.y + int(rect.h * 0.60)
        self.text("CONVERSACIÓN", "sb", DIM, (rect.x + 15, rect.y + 110))
        with node.lock:
            chat = list(node.chat)
            log = list(node.log)
        y = split - 10
        for who, txt in reversed(chat):
            rows = self.wrap(txt, "m", rect.w - 30)
            need = 18 + 19 * len(rows) + 8
            if y - need < rect.y + 132:
                break
            y -= need
            self.text(who, "sb", GREEN if who == "tú" else CYAN, (rect.x + 15, y))
            for i, row in enumerate(rows):
                self.text(row, "m", WHITE, (rect.x + 15, y + 18 + i * 19))
        # log ROS 2
        self.text("QUÉ HACE EL ROBOT (ROS 2)", "sb", DIM, (rect.x + 15, split + 4))
        y = rect.bottom - 10
        for txt, c in reversed(log):
            rows = self.wrap(txt, "xs", rect.w - 30)
            if y - 15 * len(rows) < split + 26:
                break
            y -= 15 * len(rows) + 3
            for i, row in enumerate(rows):
                self.text(row, "xs", c, (rect.x + 15, y + i * 15))
        return ptt

    def right(self, node: Console, rect):
        pg, s = self.pg, self.s
        pg.draw.rect(s, PANEL, rect, border_radius=14)
        self.text("ÚLTIMA ORDEN AL CUERPO", "sb", DIM, (rect.x + 15, rect.y + 15))
        li = node.last_intent
        if li:
            self.text(str(li.get("name", "")), "xl", ORANGE, (rect.x + 15, rect.y + 38))
            y = rect.y + 80
            for k, v in (li.get("args") or {}).items():
                self.text(f"{k}: {v}", "m", WHITE, (rect.x + 15, y))
                y += 21
            self.text(f"intent: {li.get('intent', '')}", "m", DIM, (rect.x + 15, y))
            self.text("topic: /udito/intent", "m", DIM, (rect.x + 15, y + 21))
        else:
            for i, row in enumerate(self.wrap("Aún ninguna. Prueba «sígueme» o «mira a la izquierda».", "m", rect.w - 30)):
                self.text(row, "m", DIM, (rect.x + 15, rect.y + 45 + i * 20))

        y0 = rect.y + 200
        self.text("ESTADO", "sb", DIM, (rect.x + 15, y0))
        mic = {"hearing": ("grabando", RED), "transcribing": ("transcribiendo", ORANGE)}.get(
            node.state, ("listo", GREEN) if node.powered else ("apagado", DIM))
        moving = node.motion and time.time() < node.motion_until
        rows = [("Cara", FACE_NAMES.get(node.emotion, node.emotion) if node.powered else "apagada", CYAN),
                ("Micrófono", mic[0], mic[1]),
                ("Ruedas", {"follow": "siguiendo", "go_to": "avanzando", "rotate": "girando"}.get(node.motion, "") if moving else "quietas",
                 ORANGE if moving else WHITE),
                ("Último STT", f"{node.stt_sec} s" if node.stt_sec is not None else "—", WHITE)]
        for i, (k, v, c) in enumerate(rows):
            self.text(k, "m", DIM, (rect.x + 15, y0 + 25 + i * 26))
            self.text(v, "mb", c, (rect.x + 140, y0 + 25 + i * 26))

        y1 = y0 + 140
        self.text("EXPRESIONES", "sb", DIM, (rect.x + 15, y1))
        btns = []
        mouse = pg.mouse.get_pos()
        bw = (rect.w - 30 - 16) // 3
        for i, (lbl, order) in enumerate(EXPRESSION_BUTTONS):
            r = pg.Rect(rect.x + 15 + (i % 3) * (bw + 8), y1 + 24 + (i // 3) * 40, bw, 32)
            hov = r.collidepoint(mouse) and node.powered
            pg.draw.rect(s, (40, 64, 90) if hov else CHIP, r, border_radius=16)
            self.text(lbl, "m", WHITE if node.powered else DIM, r.center, center=True)
            btns.append((r, order))

        # ---- Haz que diga ----
        y2 = y1 + 24 + 2 * 40 + 18
        self.text("HAZ QUE DIGA", "sb", DIM, (rect.x + 15, y2))
        box = pg.Rect(rect.x + 15, y2 + 22, rect.w - 30, 64)
        pg.draw.rect(s, (12, 18, 32), box, border_radius=10)
        pg.draw.rect(s, BLUE if node.typing else CHIP, box, 2, border_radius=10)
        if node.typed or node.typing:
            caret = "|" if node.typing and int(time.time() * 2) % 2 else ""
            rows = self.wrap(node.typed + caret, "m", box.w - 20)[-3:]
            for i, row in enumerate(rows):
                self.text(row, "m", WHITE, (box.x + 10, box.y + 6 + i * 19))
        else:
            self.text("Escribe una frase y pulsa Enter", "m", DIM, (box.x + 10, box.y + 10))
            self.text("etiquetas: [feliz] Hola [sorpresa] ¿sí?", "xs", DIM, (box.x + 10, box.y + 36))
        emo_btns = []
        names = ["neutral", "feliz", "triste", "sorpresa", "pensando", "enfadado", "risa", "guiño"]
        cw = (rect.w - 30 - 3 * 6) // 4
        for i, name in enumerate(names):
            r = pg.Rect(rect.x + 15 + (i % 4) * (cw + 6), box.bottom + 8 + (i // 4) * 30, cw, 25)
            sel = node.say_emotion == name
            pg.draw.rect(s, CYAN if sel else CHIP, r, border_radius=12)
            self.text(name, "xs", BG if sel else WHITE, r.center, center=True)
            emo_btns.append((r, name))
        send = pg.Rect(rect.x + 15, box.bottom + 72, rect.w - 30, 34)
        can = node.powered and node.typed.strip()
        pg.draw.rect(s, BLUE if can else CHIP, send, border_radius=17)
        self.text("DECIR  (Enter)", "mb", WHITE if can else DIM, send.center, center=True)
        return btns, box, emo_btns, send

    def topbar(self, node: Console, w, alive):
        pg, s = self.pg, self.s
        pg.draw.rect(s, TOPBAR, (0, 0, w, 56))
        b = pg.Rect(20, 10, 150, 36)
        pg.draw.rect(s, RED if node.powered else GREEN, b, border_radius=18)
        self.text("APAGAR" if node.powered else "ENCENDER", "l", WHITE if node.powered else BG, b.center, center=True)
        x = 200
        for name, label in NODES:
            ok = name in alive
            pg.draw.circle(s, GREEN if ok else RED, (x, 28), 6)
            r = self.text(label, "m", WHITE if ok else DIM, (x + 12, 19))
            x = r.right + 28
        info = f"estado: {node.state}" + (f"   ·   STT {node.stt_sec} s" if node.stt_sec is not None else "")
        surf = self.f["m"].render(info, True, DIM)
        s.blit(surf, (w - 20 - surf.get_width(), 19))
        return b


# ==================================================================== main
def main(args=None) -> None:
    import pygame

    rclpy.init(args=args)
    node = Console()
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()

    pygame.init()
    W, H = 1280, 820
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("UDITO — Consola (ROS 2)")
    painter = Painter(pygame, screen)
    clock = pygame.time.Clock()

    alive: set[str] = set()
    last_check = 0.0
    talking = False
    order_rects, expr_btns, emo_btns = [], [], []
    say_box = say_btn = pygame.Rect(0, 0, 0, 0)
    pygame.key.start_text_input()
    ptt_rect = power_rect = pygame.Rect(0, 0, 0, 0)
    t0 = time.time()

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE:
                if node.typing:
                    node.typing = False       # Esc deja de escribir
                else:
                    running = False
            elif node.typing and ev.type == pygame.TEXTINPUT:
                node.typed = (node.typed + ev.text)[:400]
            elif node.typing and ev.type == pygame.KEYDOWN:
                if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    if node.powered:
                        node.say_free()
                elif ev.key == pygame.K_BACKSPACE:
                    node.typed = node.typed[:-1]
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                node.typing = say_box.collidepoint(ev.pos)
                if say_btn.collidepoint(ev.pos) and node.powered:
                    node.say_free()
                for r, name in emo_btns:
                    if r.collidepoint(ev.pos):
                        node.say_emotion = name
                if power_rect.collidepoint(ev.pos):
                    node.power(not node.powered)
                elif ptt_rect.collidepoint(ev.pos) and node.powered:
                    talking = True
                    node.ptt(True)
                elif node.powered:
                    for r, it in order_rects:
                        if r.collidepoint(ev.pos):
                            node.say_text(it.get("label", "").split("/")[0].strip())
                    for r, order in expr_btns:
                        if r.collidepoint(ev.pos):
                            node.say_text(order)
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and talking:
                talking = False
                node.ptt(False)
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE and node.powered and not talking and not node.typing:
                talking = True
                node.ptt(True)
            elif ev.type == pygame.KEYUP and ev.key == pygame.K_SPACE and talking:
                talking = False
                node.ptt(False)

        if time.time() - last_check > 1.0:
            last_check = time.time()
            try:
                alive = set(node.get_node_names())
            except Exception:  # noqa: BLE001
                pass

        t = time.time() - t0
        screen.fill(BG)
        if node.powered:  # halo detrás del robot
            for r in range(360, 0, -12):
                c = max(0, int(22 - r / 18))
                pygame.draw.circle(screen, (10 + c // 2, 14 + c, 26 + c), (W // 2, H // 2 + 20), r)
        power_rect = painter.topbar(node, W, alive)
        ptt_rect = painter.left(node, pygame.Rect(20, 72, 330, H - 92), talking)
        expr_btns, say_box, emo_btns, say_btn = painter.right(node, pygame.Rect(W - 350, 72, 330, H - 92))
        order_rects = painter.robot(node, W // 2, 92, t, talking)

        pygame.display.flip()
        clock.tick(30)

    if talking:
        node.ptt(False)
    pygame.quit()
    node.destroy_node()
    if rclpy.ok():
        rclpy.shutdown()


if __name__ == "__main__":
    main()
