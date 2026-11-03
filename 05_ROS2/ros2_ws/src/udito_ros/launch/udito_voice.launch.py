"""Arquitectura híbrida - UDITO · Lanzador ROS 2: voz, C.C., consola y ejemplo del cuerpo.

Uso nativo (sin scripts), desde cualquier terminal con ROS 2 cargado:

    ros2 launch udito_ros udito_voice.launch.py [opción:=valor ...]

Opciones (argumentos del lanzador):
    console:=true|false        Consola del operador (cara, botones, log)            [true]
    mic:=true|false            Nodo STT con micrófono                               [true]
    stt_mode:=ptt|vad          ptt = mantén para hablar · vad = escucha continua    [ptt]
    whisper:=tiny|base|small   Velocidad frente a precisión del STT                 [base]
    body_example:=true|false   Nodo de ejemplo del cuerpo                           [true]
    cognitive:=true|false      Capa deliberativa                                    [false]
    rag:=true|false            RAG completo dentro de cognitive                     [false]
    face:=true|false           Cara en ventana aparte (pantalla física)             [false]

El lanzador prepara el entorno por sí solo, en este orden:
    1. Las variables que ya existan en la terminal mandan siempre.
    2. Lee el archivo .env de la raíz del repo (audio, volumen, rutas de modelos).
    3. En la Jetson (aarch64), añade los valores de bajo consumo (hilos, memoria, rutas).
    4. Añade el .venv del repo (Whisper, Piper, RAG) al PYTHONPATH de los nodos.

Una sola instancia: al arrancar se cierran los nodos de UDITO que hubieran quedado vivos de un
lanzamiento anterior, y al cerrar la ventana de la consola se apaga todo el lanzamiento
(no queda ningún nodo corriendo).

Los ajustes de HARDWARE (frecuencias, ReSpeaker, snap) no van aquí: se aplican al
iniciar Ubuntu (03_ADAPTERS/UDITO_ROBOT_SOCIAL/Dispositivos/Jetson_Orin_Nano/arranque).
"""
import glob
import os
import platform
import subprocess
import time
from pathlib import Path

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, EmitEvent, ExecuteProcess, LogInfo, RegisterEventHandler
from launch.event_handlers import OnProcessExit
from launch.events import Shutdown
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue

DEFAULT_ROOT = Path("/opt/cognitive-robotics-core")


def _repo_root() -> Path:
    env = os.environ.get("ROBITA_ROOT")
    if env:
        return Path(env)
    for p in Path(__file__).resolve().parents:
        if (p / "01_SERVICES").is_dir() and (p / "05_ROS2").is_dir():
            return p
    return DEFAULT_ROOT


def _read_dotenv(path: Path) -> dict:
    """Lee KEY=VALOR de un .env (ignora comentarios; la última definición gana)."""
    values = {}
    if not path.is_file():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[len("export "):]
        key, val = line.split("=", 1)
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "'\"":
            val = val[1:-1]
        elif " #" in val:
            val = val.split(" #", 1)[0].strip()
        if key:
            values[key] = val
    return values


def _prepare_environment(root: Path) -> Path:
    """Deja listo os.environ para los nodos. Devuelve el python a usar para la cara."""
    preset = set(os.environ)  # lo que el usuario ya definió en la terminal

    for key, val in _read_dotenv(root / ".env").items():
        if key not in preset:
            os.environ[key] = os.path.expandvars(val)

    if platform.machine() == "aarch64":  # Jetson: bajo consumo (antes scripts/lib/jetson-env.sh)
        jetson = {
            "CUDA_VISIBLE_DEVICES": "",
            "OMP_NUM_THREADS": "1",
            "OPENBLAS_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "TOKENIZERS_PARALLELISM": "false",
            "ROBITA_LOW_MEMORY": "1",
            "ROBITA_RELEASE_MODELS": "1",
            "WHISPER_MODEL": "tiny",
            "ROBITA_RAG_CONFIG": str(root / "01_SERVICES/rag-engine/config/rag_config.jetson.json"),
            "HF_HOME": str(root / "data/huggingface"),
        }
        for key, val in jetson.items():
            os.environ.setdefault(key, val)
        cudnn8 = root / ".local-lib/cudnn8-docker"
        if (cudnn8 / "libcudnn.so.8").is_file():
            os.environ["LD_LIBRARY_PATH"] = f"{cudnn8}:{os.environ.get('LD_LIBRARY_PATH', '')}".rstrip(":")

    os.environ["ROBITA_ROOT"] = str(root)
    os.environ["ROBITA_ROS2_SPEECH"] = "0"  # la voz la publica el nodo TTS, sin nodos paralelos
    os.environ.setdefault("DISPLAY", ":0")

    site = sorted(glob.glob(str(root / ".venv/lib/python3*/site-packages")))
    if site:
        os.environ["PYTHONPATH"] = f"{site[0]}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")
    else:
        print(f"[udito] Aviso: no encuentro {root}/.venv — instala los motores con ./scripts/setup/jetson.sh")

    venv_python = root / ".venv/bin/python"
    return venv_python if venv_python.exists() else Path("python3")


def _close_previous_instances() -> None:
    """Cierra nodos de UDITO que hayan quedado vivos de un lanzamiento anterior (evita respuestas dobles)."""
    patterns = ["lib/udito_ros/", "udito_modulos_robot/udito_face.py"]
    found = False
    for pat in patterns:
        if subprocess.run(["pgrep", "-f", pat], capture_output=True).returncode == 0:
            found = True
            subprocess.run(["pkill", "-f", pat], capture_output=True)
    if found:
        print("[udito] Cerré nodos de UDITO que seguían vivos de un lanzamiento anterior.")
        time.sleep(1.5)


def generate_launch_description():
    root = _repo_root()
    _close_previous_instances()
    face_python = _prepare_environment(root)
    arg = LaunchConfiguration

    console = Node(package="udito_ros", executable="console_node", name="udito_console", output="screen",
                   condition=IfCondition(arg("console")))

    return LaunchDescription([
        DeclareLaunchArgument("console", default_value="true", description="Consola del operador (cara, botones, log)"),
        DeclareLaunchArgument("mic", default_value="true", description="Nodo STT con micrófono"),
        DeclareLaunchArgument("stt_mode", default_value="ptt", description="ptt = mantén para hablar · vad = escucha continua"),
        DeclareLaunchArgument("whisper", default_value="base", description="tiny · base · small"),
        DeclareLaunchArgument("body_example", default_value="true", description="Nodo de ejemplo del cuerpo"),
        DeclareLaunchArgument("cognitive", default_value="false", description="Capa deliberativa"),
        DeclareLaunchArgument("rag", default_value="false", description="RAG completo dentro de cognitive"),
        DeclareLaunchArgument("face", default_value="false", description="Cara en ventana aparte (pantalla física)"),

        # Capa ejecutiva: C.C. de UDITO (pasará a Behavior Tree en F2)
        Node(package="udito_ros", executable="udito_cc_node", name="udito_cc", output="screen",
             parameters=[{"use_cognitive": ParameterValue(arg("cognitive"), value_type=bool)}]),
        # Capa de habilidades: voz
        Node(package="udito_ros", executable="tts_node", name="udito_tts", output="screen"),
        Node(package="udito_ros", executable="stt_node", name="udito_stt", output="screen",
             condition=IfCondition(arg("mic")),
             parameters=[{"mode": ParameterValue(arg("stt_mode"), value_type=str),
                          "model": ParameterValue(arg("whisper"), value_type=str)}]),
        # Ejemplo para el orquestador del cuerpo
        Node(package="udito_ros", executable="body_example_node", name="udito_body_example", output="screen",
             condition=IfCondition(arg("body_example"))),
        # Capa deliberativa (opcional)
        Node(package="udito_ros", executable="cognitive_node", name="udito_cognitive", output="screen",
             condition=IfCondition(arg("cognitive")),
             parameters=[{"use_rag": ParameterValue(arg("rag"), value_type=bool)}]),
        # Operador: al cerrar la ventana de la consola se apaga todo el lanzamiento
        console,
        RegisterEventHandler(OnProcessExit(target_action=console, on_exit=[
            LogInfo(msg="[udito] Consola cerrada: apagando todos los nodos de UDITO."),
            EmitEvent(event=Shutdown(reason="consola cerrada")),
        ])),
        # Cara en ventana aparte (pantalla física)
        ExecuteProcess(
            cmd=[str(face_python), str(root / "05_ROS2/udito_modulos_robot/udito_face.py"), "--wakeword"],
            additional_env={
                "ROBITA_SPEECH_EVENT_FILE": os.environ.get("ROBITA_SPEECH_EVENT_FILE", "/tmp/udito_speech_out.json"),
                "ROBITA_WAKEWORD_EVENT_FILE": os.environ.get("ROBITA_WAKEWORD_EVENT_FILE", "/tmp/udito_wakeword.json"),
                "ROBITA_FACE_BACKEND": os.environ.get("ROBITA_FACE_BACKEND", "sim"),
            },
            condition=IfCondition(arg("face")), output="screen"),
    ])
