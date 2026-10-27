"""Arquitectura 3T - UDITO · Consola del operador (nodo ROS 2).

Una sola ventana para manejar y ENTENDER el robot:
  - ENCENDER / APAGAR            → /udito/power
  - MANTÉN PARA HABLAR (espacio) → /udito/stt/ptt   (el STT graba solo mientras lo mantienes)
  - Lista de órdenes (clic)      → /udito/stt/text  (como si lo hubieras dicho)
  - Cara del robot, estado de cada nodo y consola con lo que hace el C.C. paso a paso.
"""
from __future__ import annotations

import json
import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

from udito_ros import intents as I
from udito_ros import topics
from udito_ros.paths import add_engine_paths

BG = (12, 14, 28)
PANEL = (22, 26, 48)
TXT = (230, 236, 255)
DIM = (120, 130, 170)
GREEN = (80, 220, 140)
BLUE = (30, 180, 255)
ORANGE = (255, 170, 60)
RED = (255, 80, 80)

NODES = [("udito_stt", "STT oído"), ("udito_tts", "TTS voz"), ("udito_cc", "C.C."),
         ("udito_body_example", "Cuerpo (ejemplo)")]


class Console(Node):
    def __init__(self) -> None:
        super().__init__("udito_console")
        self.intents = I.load()["intents"]
        self.log: list[tuple[str, str, tuple]] = []
        self.lock = threading.Lock()
        self.face_state = None
        self.state = "apagado"
        self.stt_sec = None
        self.last_intent = ""
        self.powered = False

        self.pub_power = self.create_publisher(Bool, topics.POWER, 10)
        self.pub_ptt = self.create_publisher(Bool, topics.STT_PTT, 10)
        self.pub_text = self.create_publisher(String, topics.STT_TEXT, 10)
        self.create_subscription(String, topics.STT_TEXT, self._heard, 10)
        self.create_subscription(String, topics.CC_LOG, self._cc, 10)
        self.create_subscription(String, topics.STATE, self._state, 10)
        self.create_subscription(String, topics.SPEECH_OUT, self._face, 10)
        self.create_subscription(String, topics.INTENT, self._intent, 10)

    def add(self, text: str, color: tuple) -> None:
        with self.lock:
            self.log.append((time.strftime("%H:%M:%S"), text, color))
            self.log = self.log[-300:]

    # ---- suscripciones ----
    def _heard(self, m: String) -> None:
        self.add(f"OÍDO  «{m.data}»", GREEN)

    def _cc(self, m: String) -> None:
        color = BLUE if m.data.startswith("→") else ORANGE
        self.add(("C.C.  " if not m.data.startswith("→") else "      ") + m.data, color)

    def _state(self, m: String) -> None:
        try:
            d = json.loads(m.data)
        except json.JSONDecodeError:
            return
        st = d.get("state", "")
        if "stt_sec" in d:
            self.stt_sec = d["stt_sec"]
        if st and st != self.state:
            self.state = st
            if st == "hearing":
                self.add("escuchando…", DIM)
            elif st == "transcribing":
                self.add("…transcribiendo", DIM)

    def _face(self, m: String) -> None:
        try:
            self.face_state = json.loads(m.data)
        except json.JSONDecodeError:
            pass

    def _intent(self, m: String) -> None:
        self.last_intent = m.data

    # ---- acciones ----
    def power(self, on: bool) -> None:
        self.powered = on
        msg = Bool()
        msg.data = on
        self.pub_power.publish(msg)

    def ptt(self, on: bool) -> None:
        msg = Bool()
        msg.data = on
        self.pub_ptt.publish(msg)

    def say_text(self, text: str) -> None:
        self.add(f"(clic) «{text}»", DIM)
        msg = String()
        msg.data = text
        self.pub_text.publish(msg)


def _make_face(pygame, surface):
    """Reutiliza el dibujo de udito_face.py sobre una zona de la consola."""
    add_engine_paths()
    from udito_face import FaceState, PygameFaceSim

    f = PygameFaceSim.__new__(PygameFaceSim)
    f._pygame, f._screen = pygame, surface
    f._state = FaceState(emotion="sleepy")
    f._bg, f._eye_white = (12, 14, 28), (245, 248, 255)
    f._eye_color, f._mouth_color = (30, 180, 255), (80, 200, 255)
    f._blink_t, f._blink_phase, f._running = 0.0, 0.0, True
    f._draw_status_bar = lambda *a: None  # la consola pone su propio texto
    return f, FaceState


def _wrap(font, text: str, width: int) -> list[str]:
    out, cur = [], ""
    for w in text.split(" "):
        test = (cur + " " + w).strip()
        if font.size(test)[0] > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = test
    return out + [cur]


def main(args=None) -> None:
    import pygame

    rclpy.init(args=args)
    node = Console()
    threading.Thread(target=rclpy.spin, args=(node,), daemon=True).start()

    pygame.init()
    W, H = 1180, 720
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("UDITO — Consola (ROS 2)")
    font = lambda s: pygame.font.SysFont("dejavusans", s)  # noqa: E731
    f_big, f, f_small, f_tiny = font(22), font(16), font(14), font(12)
    clock = pygame.time.Clock()

    LW = 560
    face_rect = pygame.Rect(20, 70, LW, 280)
    face, FaceState = _make_face(pygame, screen.subsurface(face_rect))
    power_btn = pygame.Rect(20, 14, 170, 40)
    ptt_btn = pygame.Rect(20, 362, LW, 70)
    log_rect = pygame.Rect(20, 444, LW, H - 456)
    list_rect = pygame.Rect(LW + 40, 70, W - LW - 60, 430)
    intent_rect = pygame.Rect(LW + 40, 512, W - LW - 60, H - 524)

    order_rects: list[tuple[pygame.Rect, dict]] = []
    col_w = (list_rect.w - 30) // 2
    for i, it in enumerate(node.intents[:20]):
        col, row = divmod(i, 10)
        r = pygame.Rect(list_rect.x + 10 + col * (col_w + 10), list_rect.y + 36 + row * 38, col_w, 32)
        order_rects.append((r, it))

    alive: set[str] = set()
    last_check = 0.0
    talking = False
    node.add("Consola lista. Pulsa ENCENDER.", DIM)

    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                if power_btn.collidepoint(ev.pos):
                    node.power(not node.powered)
                elif ptt_btn.collidepoint(ev.pos) and node.powered:
                    talking = True
                    node.ptt(True)
                else:
                    for r, it in order_rects:
                        if r.collidepoint(ev.pos):
                            node.say_text(it.get("label", "").split("/")[0].strip())
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and talking:
                talking = False
                node.ptt(False)
            elif ev.type == pygame.KEYDOWN and ev.key == pygame.K_SPACE and node.powered and not talking:
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

        screen.fill(BG)
        # ---- barra superior ----
        pygame.draw.rect(screen, RED if node.powered else GREEN, power_btn, border_radius=8)
        t = f_big.render("APAGAR" if node.powered else "ENCENDER", True, BG)
        screen.blit(t, t.get_rect(center=power_btn.center))
        x = power_btn.right + 25
        for name, label in NODES:
            ok = name in alive
            pygame.draw.circle(screen, GREEN if ok else RED, (x + 7, 34), 7)
            screen.blit(f_small.render(label, True, TXT if ok else DIM), (x + 20, 26))
            x += 40 + f_small.size(label)[0]
        info = f"estado: {node.state}" + (f"   ·   STT {node.stt_sec}s" if node.stt_sec is not None else "")
        screen.blit(f_small.render(info, True, DIM), (W - 20 - f_small.size(info)[0], 26))

        # ---- cara ----
        if node.face_state is not None:
            face._state = FaceState.from_speech_json(node.face_state)
            node.face_state = None
        if not node.powered:
            face._state = FaceState(emotion="sleepy", label="apagado")
        elif talking:
            face._state = FaceState(emotion="listening", label="te escucho")
        face._blink_t += 1 / 30
        if face._blink_t > 3.2:
            face._blink_t, face._blink_phase = 0.0, 0.15
        face._blink_phase = max(0.0, face._blink_phase - 4 / 30)
        face._draw()
        pygame.draw.rect(screen, PANEL, face_rect, 2, border_radius=8)
        screen.blit(f_tiny.render(f"cara: {face._state.emotion}", True, DIM), (face_rect.x + 10, face_rect.bottom - 20))

        # ---- botón hablar ----
        col = RED if talking else (BLUE if node.powered else PANEL)
        pygame.draw.rect(screen, col, ptt_btn, border_radius=12)
        label = ("GRABANDO… suelta para enviar" if talking else
                 "MANTÉN PARA HABLAR  (o barra espaciadora)" if node.powered else "Primero pulsa ENCENDER")
        t = f_big.render(label, True, TXT)
        screen.blit(t, t.get_rect(center=ptt_btn.center))

        # ---- consola ----
        pygame.draw.rect(screen, PANEL, log_rect, border_radius=8)
        screen.blit(f_tiny.render("CONSOLA — qué hace el robot (ROS 2)", True, DIM), (log_rect.x + 10, log_rect.y + 6))
        y = log_rect.bottom - 8
        with node.lock:
            items = list(node.log)
        for hora, text, c in reversed(items):
            rows = _wrap(f_small, text, log_rect.w - 90)
            if y - 18 * len(rows) < log_rect.y + 26:
                break
            for row in reversed(rows):
                y -= 18
                screen.blit(f_small.render(row, True, c), (log_rect.x + 76, y))
            screen.blit(f_tiny.render(hora, True, DIM), (log_rect.x + 10, y + 2))
            y -= 4

        # ---- órdenes ----
        pygame.draw.rect(screen, PANEL, list_rect, border_radius=8)
        screen.blit(f.render("ÓRDENES  (dilas, o clic para enviarlas)", True, DIM), (list_rect.x + 10, list_rect.y + 8))
        mouse = pygame.mouse.get_pos()
        for i, (r, it) in enumerate(order_rects, start=1):
            hover = r.collidepoint(mouse)
            pygame.draw.rect(screen, BLUE if hover else BG, r, border_radius=6)
            tag = " ⚙" if it.get("body") else ""
            screen.blit(f_small.render(f"{i:2d}  {it.get('label', it['id'])}{tag}", True, BG if hover else TXT),
                        (r.x + 8, r.y + 7))

        # ---- último /udito/intent ----
        pygame.draw.rect(screen, PANEL, intent_rect, border_radius=8)
        screen.blit(f_tiny.render("ÚLTIMA ORDEN AL CUERPO  →  /udito/intent   (⚙ = mueve el cuerpo)", True, DIM),
                    (intent_rect.x + 10, intent_rect.y + 6))
        yy = intent_rect.y + 28
        txt = node.last_intent or "(aún ninguna — prueba «sígueme» o «mira a la izquierda»)"
        try:
            txt = json.dumps(json.loads(txt), ensure_ascii=False, indent=1) if node.last_intent else txt
        except json.JSONDecodeError:
            pass
        for line in txt.splitlines():
            for row in _wrap(f_tiny, line, intent_rect.w - 20):
                if yy > intent_rect.bottom - 16:
                    break
                screen.blit(f_tiny.render(row, True, ORANGE if node.last_intent else DIM), (intent_rect.x + 10, yy))
                yy += 15

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
