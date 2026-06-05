"""
Cara de UDITO: dibujo de ojos por emoción.
Backend sim (ventana pygame) o futuro hardware (misma API).
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

log = logging.getLogger("udito.face")

# Expresiones de cara (comandos directos + emociones del pipeline)
FACE_EXPRESSIONS = frozenset(
    {
        "neutral",
        "happy",
        "helpful",
        "sorry",
        "sad",
        "thinking",
        "proud",
        "informative",
        "laugh",
        "idle",
        "listening",
        "speaking",
        "surprised",
        "angry",
        "sleepy",
        "love",
        "confused",
        "scared",
        "wink",
        "tongue",
        "closed",
        "wide",
        "curious",
    }
)
KNOWN_EMOTIONS = FACE_EXPRESSIONS  # alias


@dataclass
class FaceState:
    emotion: str = "idle"
    label: str = ""
    source: str = ""

    @classmethod
    def from_speech_json(cls, data: dict[str, Any]) -> FaceState:
        em = (data.get("emotion") or "neutral").strip().lower()
        if em == "sorry":
            em = "sad"
        if em not in FACE_EXPRESSIONS:
            em = "neutral"
        return cls(
            emotion=em,
            label=str(data.get("label") or ""),
            source=str(data.get("source") or ""),
        )


def load_face_state_from_file(path: str | Path) -> FaceState | None:
    p = Path(path)
    if not p.is_file():
        return None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return FaceState.from_speech_json(data)
    except (OSError, json.JSONDecodeError) as e:
        log.debug("No se leyó %s: %s", p, e)
        return None


class FaceDisplay(Protocol):
    def set_state(self, state: FaceState) -> None: ...
    def tick(self, dt: float) -> bool: ...
    def close(self) -> None: ...


class PygameFaceSim:
    """Ventana local que simula la pantalla de ojos del robot."""

    def __init__(
        self,
        width: int | None = None,
        height: int | None = None,
        title: str = "UDITO — pantalla (sim)",
    ) -> None:
        import pygame

        self._pygame = pygame
        w = width or int(os.getenv("ROBITA_FACE_WIDTH", "480"))
        h = height or int(os.getenv("ROBITA_FACE_HEIGHT", "320"))
        os.environ.setdefault("SDL_VIDEO_CENTERED", "1")
        pygame.init()
        self._screen = pygame.display.set_mode((w, h))
        pygame.display.set_caption(title)
        self._clock = pygame.time.Clock()
        self._state = FaceState(emotion="idle")
        self._blink_t = 0.0
        self._blink_phase = 0.0
        self._running = True
        self._bg = (12, 14, 28)
        self._eye_white = (245, 248, 255)
        self._eye_color = (30, 180, 255)
        self._mouth_color = (80, 200, 255)

    def set_state(self, state: FaceState) -> None:
        self._state = state

    def close(self) -> None:
        self._running = False
        self._pygame.quit()

    def _handle_key(self, key: int) -> None:
        pygame = self._pygame
        keys = {
            pygame.K_1: "happy",
            pygame.K_2: "sorry",
            pygame.K_3: "thinking",
            pygame.K_4: "laugh",
            pygame.K_5: "idle",
            pygame.K_6: "listening",
            pygame.K_7: "helpful",
        }
        if key in keys:
            self._state = FaceState(emotion=keys[key], label="teclado")

    def tick(self, dt: float) -> bool:
        pygame = self._pygame
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                return False
            if ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    return False
                self._handle_key(ev.key)

        self._blink_t += dt
        if self._blink_t > 3.2:
            self._blink_t = 0.0
            self._blink_phase = 0.15

        if self._blink_phase > 0:
            self._blink_phase = max(0.0, self._blink_phase - dt * 4)

        self._draw()
        pygame.display.flip()
        self._clock.tick(30)
        return self._running

    def _draw(self) -> None:
        s = self._screen
        w, h = s.get_size()
        s.fill(self._bg)
        em = self._state.emotion
        cx, cy = w // 2, h // 2 - 10
        eye_y = cy - 20
        gap = min(90, w // 5)
        left = (cx - gap, eye_y)
        right = (cx + gap, eye_y)
        blink = self._blink_phase > 0.02

        if em == "wink":
            self._draw_eye(left, 36, 0.5, (0, 0), 0)
            pygame = self._pygame
            x, y = left
            pygame.draw.arc(
                self._screen, self._eye_color, (x - 36, y - 4, 72, 24), 3.14, 0, 4
            )
            self._draw_eye(right, 36, 0.9, (0, 0), 0)
        elif em == "tongue":
            self._draw_eyes(left, right, pupil_scale=0.9, smile=True)
            self._draw_tongue(cx, cy + 58)
        elif em == "closed":
            self._draw_closed_line(left, right)
        elif em == "laugh":
            self._draw_laugh_eyes(left, right)
        elif blink and em not in ("wink", "closed"):
            self._draw_closed_line(left, right)
        elif em in ("sad", "sorry"):
            self._draw_eyes(left, right, pupil_scale=0.55, brow_tilt=-8)
            self._draw_frown(left, right)
        elif em == "thinking":
            self._draw_eyes(left, right, pupil_off=(0, -12), brow_tilt=6)
            self._draw_thinking_dots(cx, cy + 55)
        elif em in ("happy", "fun_fact", "fun_joke"):
            self._draw_eyes(left, right, pupil_scale=0.85, smile=True)
        elif em == "surprised":
            self._draw_eyes(left, right, pupil_scale=0.35, wide=True)
            self._draw_oval_mouth(cx, cy + 52, 28, 36)
        elif em == "angry":
            self._draw_eyes(left, right, pupil_scale=0.7, brow_tilt=-12)
            self._draw_frown(left, right, deep=True)
        elif em == "sleepy":
            self._draw_sleepy_eyes(left, right)
        elif em == "love":
            self._draw_heart_eyes(left, right)
            self._draw_smile(left, right)
        elif em == "confused":
            self._draw_eye(left, 36, 0.85, (-8, 0), 8)
            self._draw_eye(right, 36, 0.85, (8, 0), -6)
            self._draw_smile(left, right, small=True)
        elif em == "scared":
            self._draw_eyes(left, right, pupil_scale=0.25, wide=True)
            self._draw_oval_mouth(cx, cy + 54, 18, 22)
        elif em == "wide":
            self._draw_eyes(left, right, pupil_scale=0.3, wide=True)
        elif em == "curious":
            self._draw_eyes(left, right, pupil_off=(6, -6), brow_tilt=10)
            self._draw_eyes(right, right, pupil_scale=0.85)
        elif em == "proud":
            self._draw_eyes(left, right, pupil_scale=0.8, smile=True, brow_tilt=-4)
        elif em == "listening":
            self._draw_eyes(left, right, pupil_scale=1.1, wide=True)
        elif em in ("speaking", "helpful", "informative"):
            self._draw_eyes(left, right, pupil_scale=0.9)
            self._draw_oval_mouth(cx, cy + 50, 22, 14)
        elif em == "idle":
            self._draw_eyes(left, right, pupil_scale=0.75)
        else:
            self._draw_eyes(left, right)

        self._draw_status_bar(w, h)

    def _draw_status_bar(self, w: int, h: int) -> None:
        pygame = self._pygame
        font = pygame.font.SysFont("dejavusans", 14)
        txt = f"{self._state.emotion}"
        if self._state.label:
            txt += f"  |  {self._state.label}"
        surf = font.render(txt, True, (140, 160, 200))
        s = self._screen
        s.blit(surf, (12, h - 28))
        hint = font.render("Esc: salir | Comandos de voz: ver face_commands.json", True, (90, 100, 130))
        s.blit(hint, (12, h - 48))

    def _draw_eyes(
        self,
        left: tuple[int, int],
        right: tuple[int, int],
        *,
        pupil_scale: float = 1.0,
        pupil_off: tuple[int, int] = (0, 0),
        brow_tilt: int = 0,
        smile: bool = False,
        wide: bool = False,
    ) -> None:
        r = 42 if wide else 36
        for pos in (left, right):
            self._draw_eye(pos, r, pupil_scale, pupil_off, brow_tilt)
        if smile:
            self._draw_smile(left, right)

    def _draw_eye(
        self,
        center: tuple[int, int],
        radius: int,
        pupil_scale: float,
        pupil_off: tuple[int, int],
        brow_tilt: int,
    ) -> None:
        pygame = self._pygame
        x, y = center
        pygame.draw.circle(self._screen, self._eye_white, center, radius)
        pr = int(radius * 0.45 * pupil_scale)
        pygame.draw.circle(
            self._screen,
            self._eye_color,
            (x + pupil_off[0], y + pupil_off[1]),
            max(6, pr),
        )
        if brow_tilt:
            pygame.draw.line(
                self._screen,
                self._eye_color,
                (x - radius, y - radius - 4),
                (x + radius, y - radius - 4 + brow_tilt),
                3,
            )

    def _draw_closed_line(self, left: tuple[int, int], right: tuple[int, int]) -> None:
        pygame = self._pygame
        for x, y in (left, right):
            pygame.draw.arc(
                self._screen,
                self._eye_color,
                (x - 36, y - 8, 72, 24),
                3.14,
                0,
                4,
            )

    def _draw_laugh_eyes(self, left: tuple[int, int], right: tuple[int, int]) -> None:
        self._draw_closed_line(left, right)
        self._draw_smile(left, right, big=True)

    def _draw_frown(
        self,
        left: tuple[int, int],
        right: tuple[int, int],
        *,
        deep: bool = False,
    ) -> None:
        pygame = self._pygame
        cx = (left[0] + right[0]) // 2
        cy = left[1] + (48 if deep else 44)
        w = 100 if deep else 90
        pygame.draw.arc(
            self._screen,
            self._mouth_color,
            (cx - w // 2, cy - 10, w, 36),
            0.2,
            2.9,
            4,
        )

    def _draw_oval_mouth(self, cx: int, cy: int, w: int, h: int) -> None:
        pygame = self._pygame
        pygame.draw.ellipse(
            self._screen,
            self._mouth_color,
            (cx - w // 2, cy - h // 2, w, h),
            2,
        )

    def _draw_tongue(self, cx: int, cy: int) -> None:
        pygame = self._pygame
        pygame.draw.ellipse(self._screen, (220, 90, 110), (cx - 18, cy, 36, 28))
        pygame.draw.ellipse(self._screen, (240, 120, 130), (cx - 14, cy + 4, 28, 22))

    def _draw_sleepy_eyes(self, left: tuple[int, int], right: tuple[int, int]) -> None:
        pygame = self._pygame
        for x, y in (left, right):
            pygame.draw.arc(
                self._screen,
                self._eye_color,
                (x - 38, y - 6, 76, 28),
                3.4,
                6.2,
                4,
            )

    def _draw_heart_eyes(self, left: tuple[int, int], right: tuple[int, int]) -> None:
        pygame = self._pygame
        pink = (255, 100, 140)
        for x, y in (left, right):
            pygame.draw.circle(self._screen, pink, (x - 10, y - 4), 10)
            pygame.draw.circle(self._screen, pink, (x + 10, y - 4), 10)
            pygame.draw.polygon(
                self._screen,
                pink,
                [(x, y + 14), (x - 18, y - 2), (x + 18, y - 2)],
            )

    def _draw_smile(
        self,
        left: tuple[int, int],
        right: tuple[int, int],
        *,
        big: bool = False,
        small: bool = False,
    ) -> None:
        pygame = self._pygame
        cx = (left[0] + right[0]) // 2
        cy = left[1] + (50 if big else 42 if not small else 38)
        w, h = (
            (120 if big else 70 if small else 100),
            (40 if big else 24 if small else 32),
        )
        pygame.draw.arc(
            self._screen,
            self._mouth_color,
            (cx - w // 2, cy - h // 2, w, h),
            3.5,
            6.0,
            4,
        )

    def _draw_thinking_dots(self, cx: int, cy: int) -> None:
        pygame = self._pygame
        t = time.monotonic()
        for i in range(3):
            if int(t * 2) % 3 == i:
                pygame.draw.circle(self._screen, self._mouth_color, (cx - 24 + i * 24, cy), 6)


def create_display(backend: str | None = None) -> FaceDisplay:
    b = (backend or os.getenv("ROBITA_FACE_BACKEND", "sim")).strip().lower()
    if b == "sim":
        return PygameFaceSim()
    raise ValueError(f"Backend de cara no soportado: {b!r} (usa sim)")


def run_face_sim_loop(
    event_file: str | None = None,
    poll_hz: float = 10.0,
) -> int:
    """Bucle: lee emoción del JSON del pipeline y la pinta en ventana."""
    path = event_file or os.getenv(
        "ROBITA_SPEECH_EVENT_FILE",
        "/tmp/udito_speech_out.json",
    )
    display = create_display()
    last_mtime = 0.0
    poll_interval = 1.0 / poll_hz
    last_poll = 0.0

    log.info("Simulación de pantalla — archivo: %s", path)
    print(f"Pantalla sim: mirando {path}")
    print("Teclas 1-7: probar emociones | Esc o cerrar ventana: salir")

    try:
        while True:
            now = time.monotonic()
            if now - last_poll >= poll_interval:
                last_poll = now
                p = Path(path)
                if p.is_file():
                    mt = p.stat().st_mtime
                    if mt != last_mtime:
                        last_mtime = mt
                        st = load_face_state_from_file(path)
                        if st:
                            display.set_state(st)

            if not display.tick(1.0 / 30.0):
                break
    finally:
        display.close()
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    raise SystemExit(run_face_sim_loop())
