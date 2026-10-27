"""Arquitectura 3T - UDITO · Pantalla de audio (capa reactiva: sensores y actuadores de sonido).

Elige micrófono y altavoz, mira el nivel en vivo, graba 3 s y escúchalo,
lanza un tono de prueba y guarda la selección en .env (la usan STT y TTS).

    ./scripts/udito/audio.sh
"""
from __future__ import annotations

import math
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
RATE = 16000
CHUNK = 960  # 30 ms de s16 mono = 480 muestras * 2 bytes

BG = (12, 14, 28)
PANEL = (22, 26, 48)
SEL = (30, 180, 255)
TXT = (230, 236, 255)
DIM = (120, 130, 170)
OK = (80, 220, 140)
WARN = (255, 170, 60)


# ----------------------------------------------------------------- dispositivos
def _run(cmd: list[str]) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=5).stdout
    except Exception:  # noqa: BLE001
        return ""


def pulse_ok() -> bool:
    if not shutil.which("pactl"):
        return False
    return subprocess.run(["pactl", "info"], capture_output=True).returncode == 0


def list_pulse(kind: str) -> list[dict]:
    """kind = 'sources' | 'sinks'."""
    out, devs, name = _run(["pactl", "list", kind]), [], None
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            name = line.split(":", 1)[1].strip()
        elif line.startswith("Description:") and name:
            if not name.endswith(".monitor"):
                desc = line.split(":", 1)[1].strip()
                devs.append({"backend": "pulse", "id": name, "label": desc})
            name = None
    return devs


def list_alsa(kind: str) -> list[dict]:
    """kind = 'in' | 'out'."""
    out = _run(["arecord" if kind == "in" else "aplay", "-l"])
    devs = []
    for m in re.finditer(r"card (\d+): \S+ \[([^\]]+)\], device (\d+): [^\[]*\[([^\]]+)\]", out):
        card, cname, dev, dname = m.groups()
        devs.append({"backend": "alsa", "id": f"plughw:{card},{dev}",
                     "label": f"{cname} · {dname}"})
    return devs


# ----------------------------------------------------------------- captura / reproducción
class Mic:
    """Lee el micrófono elegido en segundo plano: nivel en vivo + grabación."""

    def __init__(self) -> None:
        self.proc: subprocess.Popen | None = None
        self.level = 0.0
        self.recording: list[bytes] | None = None
        self.error = ""

    def open(self, dev: dict) -> None:
        self.close()
        if dev["backend"] == "pulse":
            cmd = ["parec", f"--device={dev['id']}", f"--rate={RATE}", "--channels=1",
                   "--format=s16le"]
        else:
            cmd = ["arecord", "-q", "-D", dev["id"], "-f", "S16_LE", "-r", str(RATE),
                   "-c", "1", "-t", "raw"]
        try:
            self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.error = ""
        except OSError as e:
            self.error = str(e)
            return
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()

    def _read(self, proc: subprocess.Popen) -> None:
        while proc.poll() is None and proc is self.proc:
            data = proc.stdout.read(CHUNK)
            if not data:
                break
            a = np.frombuffer(data, dtype=np.int16).astype(np.float32) / 32768.0
            self.level = float(np.sqrt(np.mean(a * a))) if a.size else 0.0
            if self.recording is not None:
                self.recording.append(data)
        if proc is self.proc and proc.poll() not in (None, 0):
            self.error = (proc.stderr.read() or b"").decode(errors="ignore").strip()[:90] or "no abre"
            self.level = 0.0

    def record(self, seconds: float) -> bytes:
        self.recording = []
        time.sleep(seconds)
        data, self.recording = b"".join(self.recording), None
        return data

    def close(self) -> None:
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None


def write_wav(pcm: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(RATE)
        wf.writeframes(pcm)
    return path


def tone() -> bytes:
    t = np.arange(int(RATE * 0.35)) / RATE
    parts = [np.sin(2 * math.pi * f * t) * 0.15 for f in (523, 659, 784)]
    return (np.concatenate(parts) * 32767).astype(np.int16).tobytes()


def _alsa_card(dev: dict) -> str:
    return dev["id"].split(":", 1)[1].split(",")[0]


def get_volume(dev: dict) -> int:
    """Volumen actual (0-100) del altavoz elegido."""
    if dev["backend"] == "pulse":
        out = _run(["pactl", "get-sink-volume", dev["id"]])
    else:
        out = "".join(_run(["amixer", "-c", _alsa_card(dev), "sget", c])
                      for c in ("PCM", "Speaker", "Master", "Headphone"))
    m = re.search(r"(\d+)%", out)
    return int(m.group(1)) if m else 50


def set_volume(dev: dict, pct: int) -> None:
    """Fija el volumen de hardware (afecta también a la voz del robot)."""
    pct = max(0, min(100, int(pct)))
    if dev["backend"] == "pulse":
        _run(["pactl", "set-sink-volume", dev["id"], f"{pct}%"])
    else:
        for ctl in ("PCM", "Speaker", "Master", "Headphone"):
            _run(["amixer", "-q", "-c", _alsa_card(dev), "sset", ctl, f"{pct}%"])


def apply_env_volume() -> None:
    """Aplica ROBITA_AUDIO_VOLUME del .env al altavoz configurado (lo usa el TTS al arrancar)."""
    env = current_env()
    out, vol = env.get("ROBITA_AUDIO_OUTPUT", ""), env.get("ROBITA_AUDIO_VOLUME", "")
    if not out or not vol.isdigit():
        return
    backend = "alsa" if out.startswith(("plughw:", "hw:")) else "pulse"
    set_volume({"backend": backend, "id": out.replace("hw:", "plughw:", 1) if out.startswith("hw:") else out},
               int(vol))


def gain(pct: int) -> float:
    """Curva perceptiva: 50 % suena «a la mitad» (no lineal)."""
    return (max(0, min(100, int(pct))) / 100.0) ** 2


def scale_pcm(pcm: bytes, pct: int) -> bytes:
    a = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) * gain(pct)
    return np.clip(a, -32768, 32767).astype(np.int16).tobytes()


def scale_wav(wav: bytes, pct: int) -> bytes:
    """Aplica el volumen por software a un WAV completo (lo usa el TTS)."""
    import io

    with wave.open(io.BytesIO(wav), "rb") as r:
        params, frames = r.getparams(), r.readframes(r.getnframes())
    if params.sampwidth != 2:
        return wav
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(scale_pcm(frames, pct))
    return buf.getvalue()


def env_volume() -> int:
    v = os.getenv("ROBITA_AUDIO_VOLUME") or current_env().get("ROBITA_AUDIO_VOLUME", "")
    return int(v) if str(v).isdigit() else 100


def play(dev: dict, pcm: bytes, volume: int = 100) -> str:
    path = write_wav(scale_pcm(pcm, volume))
    try:
        if dev["backend"] == "pulse":
            cmd = ["paplay", f"--device={dev['id']}", path]
        else:
            cmd = ["aplay", "-q", "-D", dev["id"], path]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return "" if r.returncode == 0 else (r.stderr.strip()[:90] or "error al reproducir")
    finally:
        Path(path).unlink(missing_ok=True)


# ----------------------------------------------------------------- .env
def save_env(mic: dict, spk: dict, volume: int) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines() if ENV.exists() else []
    if ENV.exists():
        shutil.copy(ENV, ROOT / ".env.bak")
    values: dict[str, str | None] = {}
    if mic["backend"] == "pulse":
        values.update(ROBITA_AUDIO_INPUT="pulse", ROBITA_PULSE_SOURCE=mic["id"])
    else:
        values.update(ROBITA_AUDIO_INPUT=mic["id"].replace("plughw:", "hw:"), ROBITA_PULSE_SOURCE=None)
    if spk["backend"] == "pulse":
        values.update(ROBITA_AUDIO_OUTPUT=spk["id"], ROBITA_PULSE_SINK=spk["id"])
    else:
        values.update(ROBITA_AUDIO_OUTPUT=spk["id"], ROBITA_PULSE_SINK=None)
    values["ROBITA_AUDIO_VOLUME"] = str(int(volume))
    out, seen = [], set()
    for line in lines:
        key = line.split("=", 1)[0].strip()
        if key in values:
            seen.add(key)
            if values[key] is not None:
                out.append(f"{key}={values[key]}")
            continue
        out.append(line)
    out += [f"{k}={v}" for k, v in values.items() if k not in seen and v is not None]
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


def current_env() -> dict[str, str]:
    d = {}
    if ENV.exists():
        for line in ENV.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                d[k.strip()] = v.strip()
    return d


# ----------------------------------------------------------------- pantalla
def main() -> None:
    import pygame

    has_pulse = pulse_ok()
    mics = (list_pulse("sources") if has_pulse else []) + list_alsa("in")
    spks = (list_pulse("sinks") if has_pulse else []) + list_alsa("out")
    env = current_env()
    cur_in = env.get("ROBITA_PULSE_SOURCE") or env.get("ROBITA_AUDIO_INPUT", "")
    cur_out = env.get("ROBITA_AUDIO_OUTPUT", "")
    mi = next((i for i, d in enumerate(mics) if d["id"] in (cur_in, cur_in.replace("hw:", "plughw:"))), 0)
    si = next((i for i, d in enumerate(spks) if d["id"] == cur_out), 0)

    status = ("PulseAudio OK" if has_pulse else
              "PulseAudio NO accesible (¿ejecutas como root?) — solo dispositivos ALSA")
    status_col = OK if has_pulse else WARN
    busy = {"v": False}

    mic = Mic()
    if mics:
        mic.open(mics[mi])

    pygame.init()
    W, H = 860, 620
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("UDITO — audio")
    f_big, f, f_small = (pygame.font.SysFont(None, s) for s in (34, 24, 20))
    clock = pygame.time.Clock()
    col_w, row_h, top = (W - 60) // 2, 30, 80
    buttons = {"rec": pygame.Rect(30, H - 110, 250, 44),
               "tone": pygame.Rect(305, H - 110, 250, 44),
               "save": pygame.Rect(580, H - 110, 250, 44)}

    def set_status(msg: str, col=TXT) -> None:
        nonlocal status, status_col
        status, status_col = msg, col

    def action(kind: str) -> None:
        if busy["v"]:
            return
        busy["v"] = True
        try:
            if kind == "rec" and mics and spks:
                set_status("Grabando 3 s… habla ahora", SEL)
                pcm = mic.record(3.0)
                set_status("Reproduciendo lo grabado…", SEL)
                err = play(spks[si], pcm, vol["v"])
                set_status(err or "¿Te oíste? Si sí, pulsa Guardar.", WARN if err else OK)
            elif kind == "tone" and spks:
                set_status("Tono de prueba…", SEL)
                err = play(spks[si], tone(), vol["v"])
                set_status(err or "¿Oíste el tono?", WARN if err else OK)
            elif kind == "save" and mics and spks:
                save_env(mics[mi], spks[si], vol["v"])
                set_status("Guardado en .env (copia: .env.bak)", OK)
        finally:
            busy["v"] = False

    def draw_list(x: int, title: str, devs: list[dict], sel: int) -> list[pygame.Rect]:
        screen.blit(f.render(title, True, DIM), (x, top - 28))
        rects = []
        for i, d in enumerate(devs[:11]):
            r = pygame.Rect(x, top + i * row_h, col_w, row_h - 4)
            pygame.draw.rect(screen, SEL if i == sel else PANEL, r, border_radius=6)
            tag = "P" if d["backend"] == "pulse" else "A"
            label = f"[{tag}] {d['label']}"[:58]
            screen.blit(f_small.render(label, True, BG if i == sel else TXT), (r.x + 8, r.y + 6))
            rects.append(r)
        if not devs:
            screen.blit(f_small.render("(ninguno)", True, WARN), (x, top))
        return rects

    vol = {"v": get_volume(spks[si]) if spks else 50, "drag": False}
    vbar = pygame.Rect(30, H - 230, W - 60, 18)

    def vol_from_x(x: int) -> int:
        return max(0, min(100, int((x - vbar.x) * 100 / vbar.w)))

    mic_rects: list = []
    spk_rects: list = []
    running = True
    while running:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running = False
            elif ev.type == pygame.KEYDOWN and ev.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_MINUS, pygame.K_KP_MINUS) and spks:
                vol["v"] = max(0, min(100, vol["v"] + (5 if ev.key in (pygame.K_PLUS, pygame.K_KP_PLUS) else -5)))
                set_volume(spks[si], vol["v"])
            elif ev.type == pygame.MOUSEMOTION and vol["drag"]:
                vol["v"] = vol_from_x(ev.pos[0])
            elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1 and vol["drag"]:
                vol["drag"] = False
                if spks:
                    set_volume(spks[si], vol["v"])
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1 and vbar.inflate(0, 16).collidepoint(ev.pos):
                vol["v"], vol["drag"] = vol_from_x(ev.pos[0]), True
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                for i, r in enumerate(mic_rects):
                    if r.collidepoint(ev.pos) and i != mi:
                        mi = i
                        mic.open(mics[mi])
                for i, r in enumerate(spk_rects):
                    if r.collidepoint(ev.pos):
                        si = i
                        vol["v"] = get_volume(spks[si])
                for k, r in buttons.items():
                    if r.collidepoint(ev.pos):
                        threading.Thread(target=action, args=(k,), daemon=True).start()

        screen.fill(BG)
        screen.blit(f_big.render("UDITO — audio", True, TXT), (30, 14))
        mic_rects = draw_list(30, "Micrófono", mics, mi)
        spk_rects = draw_list(30 + col_w + 0 + 30, "Altavoz", spks, si)

        # medidor de nivel
        screen.blit(f.render(f"Volumen altavoz: {vol['v']}%   (arrastra o usa + / -)", True, DIM),
                    (30, vbar.y - 26))
        pygame.draw.rect(screen, PANEL, vbar, border_radius=6)
        pygame.draw.rect(screen, SEL, (vbar.x, vbar.y, int(vbar.w * vol["v"] / 100), vbar.h), border_radius=6)
        pygame.draw.circle(screen, TXT, (vbar.x + int(vbar.w * vol["v"] / 100), vbar.centery), 11)

        y = H - 165
        screen.blit(f.render("Nivel micrófono", True, DIM), (30, y - 26))
        bar = pygame.Rect(30, y, W - 60, 22)
        pygame.draw.rect(screen, PANEL, bar, border_radius=6)
        lvl = min(1.0, mic.level * 8)
        if lvl > 0:
            pygame.draw.rect(screen, OK if lvl < 0.8 else WARN,
                             (bar.x, bar.y, int(bar.w * lvl), bar.h), border_radius=6)
        if mic.error:
            screen.blit(f_small.render(f"micro: {mic.error}", True, WARN), (30, y + 26))

        for k, label in (("rec", "Probar micro (3 s)"), ("tone", "Tono en altavoz"),
                         ("save", "Guardar selección")):
            r = buttons[k]
            pygame.draw.rect(screen, PANEL, r, border_radius=8)
            pygame.draw.rect(screen, SEL, r, 2, border_radius=8)
            t = f.render(label, True, TXT)
            screen.blit(t, t.get_rect(center=r.center))

        screen.blit(f_small.render(status, True, status_col), (30, H - 50))
        screen.blit(f_small.render("[P] PulseAudio · [A] ALSA directo · Esc: salir", True, DIM),
                    (30, H - 26))
        pygame.display.flip()
        clock.tick(30)

    mic.close()
    pygame.quit()


if __name__ == "__main__":
    main()
