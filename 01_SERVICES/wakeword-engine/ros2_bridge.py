"""ROS2 desde wakeword: detecta si ROS2 está activo y publica eventos (config en wakeword.json)."""

from __future__ import annotations

import json
import logging
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("wakeword.ros2")

_ENGINE_DIR = Path(__file__).resolve().parent
_CONFIG_PATH = _ENGINE_DIR / "config" / "wakeword.json"

_ros_cfg: dict[str, Any] | None = None
_active: bool | None = None
_node = None
_pub_wakeword = None
_pub_state = None
_logged_status = False


def _load_ros_cfg() -> dict[str, Any]:
    global _ros_cfg
    if _ros_cfg is not None:
        return _ros_cfg
    data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    _ros_cfg = dict(data.get("ros2") or {})
    return _ros_cfg


def _event_path() -> Path:
    return Path(str(_load_ros_cfg().get("event_file", "/tmp/udito_wakeword.json")))


def _daemon_running() -> bool:
    try:
        proc = subprocess.run(
            ["ros2", "daemon", "status"],
            capture_output=True,
            text=True,
            timeout=2.5,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    text = f"{proc.stdout} {proc.stderr}".lower()
    return proc.returncode == 0 and "is running" in text


def probe_ros2(force: bool = False) -> bool:
    """True si ROS2 está disponible y la publicación está habilitada en JSON."""
    global _active
    if not force and _active is not None:
        return _active

    cfg = _load_ros_cfg()
    if not bool(cfg.get("enabled", True)):
        _active = False
        return False

    try:
        import rclpy  # noqa: F401
    except ImportError:
        _active = False
        return False

    if bool(cfg.get("require_daemon", False)) and not _daemon_running():
        _active = False
        return False

    _active = True
    return True


def is_ros2_active() -> bool:
    return probe_ros2()


def log_ros2_status() -> None:
    """Una línea al arrancar el bucle wakeword."""
    global _logged_status
    if _logged_status:
        return
    _logged_status = True
    cfg = _load_ros_cfg()
    if not bool(cfg.get("enabled", True)):
        logger.info("ROS2 wakeword desactivado en config/wakeword.json")
        return
    if probe_ros2():
        logger.info(
            "ROS2 activo — topics %s, %s",
            cfg.get("topic_wakeword", "/udito/wakeword"),
            cfg.get("topic_state", "/udito/state"),
        )
    else:
        logger.info(
            "ROS2 no disponible — eventos solo en %s",
            _event_path(),
        )


def _write_event(payload: dict[str, Any]) -> None:
    path = _event_path()
    try:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        logger.debug("No se pudo escribir %s: %s", path, exc)


def _ensure_publishers() -> bool:
    global _node, _pub_wakeword, _pub_state
    if not probe_ros2():
        return False
    if _node is not None:
        return True

    import rclpy
    from std_msgs.msg import String

    cfg = _load_ros_cfg()
    if not rclpy.ok():
        rclpy.init()
    _node = rclpy.create_node(str(cfg.get("node_name", "udito_wakeword")))
    _pub_wakeword = _node.create_publisher(
        String,
        str(cfg.get("topic_wakeword", "/udito/wakeword")),
        10,
    )
    _pub_state = _node.create_publisher(
        String,
        str(cfg.get("topic_state", "/udito/state")),
        10,
    )
    return True


def _publish_json(publisher, payload: dict[str, Any]) -> None:
    import rclpy
    from std_msgs.msg import String

    if publisher is None or _node is None:
        return
    msg = String()
    msg.data = json.dumps(payload, ensure_ascii=False)
    publisher.publish(msg)
    rclpy.spin_once(_node, timeout_sec=0.02)


def publish_wakeword_detected(
    *,
    wake_word: str,
    probability: float,
    margin: float,
    baseline: float,
) -> None:
    payload = {
        "event": "wakeword_detected",
        "wake_word": wake_word,
        "probability": round(float(probability), 4),
        "margin": round(float(margin), 4),
        "baseline": round(float(baseline), 4),
        "ros2_active": probe_ros2(),
        "timestamp": time.time(),
    }
    _write_event(payload)
    if not _ensure_publishers():
        return
    _publish_json(_pub_wakeword, payload)


def publish_state(state: str, **extra: Any) -> None:
    payload = {
        "state": str(state),
        "ros2_active": probe_ros2(),
        "timestamp": time.time(),
        **extra,
    }
    _write_event(payload)
    if not _ensure_publishers():
        return
    _publish_json(_pub_state, payload)
