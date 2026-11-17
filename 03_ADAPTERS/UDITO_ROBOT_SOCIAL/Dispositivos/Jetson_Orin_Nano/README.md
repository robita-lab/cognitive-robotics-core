# Arquitectura híbrida - UDITO · Jetson Orin Nano

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales. Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

**Papel:** capas 1 (habilidades de voz y rostro) y 3 (`cognitive` con RAG local). Mientras no llegue el
Behavior Tree al MiniPC (fase F2), también ejecuta el C.C. (`udito_cc`).

| Dato | Valor |
|------|-------|
| Sistema | Ubuntu 22.04 · JetPack 6 · ROS 2 Humble |
| Ruta del repo | `/opt/cognitive-robotics-core` |
| Usuario de escritorio | `udito` |
| Red | LAN `10.8.0.132/24` (GW `10.8.0.254`) · WiFi `10.8.34.5/23` (MAC registrada por TI) |

## Contenido

| Carpeta | Qué es | Cuándo se usa |
|---------|--------|---------------|
| [`arranque/`](arranque/) | Ajustes de hardware al iniciar Ubuntu: modo de energía MAXN_SUPER, `jetson_clocks`, ReSpeaker reservado para el robot, actualizaciones de snap en pausa | Una vez; luego se aplican solos en cada arranque |
| [`entorno_ros2/`](entorno_ros2/) | Carga ROS 2 y los proyectos `central_control` y `voice_skills` en todas las terminales y para todos los usuarios | Una vez |

## Instalación desde cero

```bash
# 1. Repositorio
sudo git clone -b feature/ros2-voice-orchestrator https://github.com/robita-lab/cognitive-robotics-core.git /opt/cognitive-robotics-core
sudo chown -R udito:udito /opt/cognitive-robotics-core
cd /opt/cognitive-robotics-core

# 2. ROS 2 y motores de IA
./scripts/setup/ros2-humble.sh       # ROS 2 Humble (si no está)
./scripts/setup/jetson.sh            # .venv con Whisper, Piper y RAG
./scripts/setup/piper-jetson.sh      # binario de voz para ARM
./scripts/setup/models-download.sh   # modelos (primera vez, con internet)

# 3. Hardware al arrancar (ver arranque/README.md)
cd 03_ADAPTERS/UDITO_ROBOT_SOCIAL/Dispositivos/Jetson_Orin_Nano/arranque
sudo cp udito-jetson-arranque.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now udito-jetson-arranque.service
sudo cp 99-udito-respeaker.rules /etc/udev/rules.d/ && sudo udevadm control --reload-rules && sudo udevadm trigger
sudo snap refresh --hold

# 4. Entorno ROS 2 para todos (ver entorno_ros2/README.md)
cd ../entorno_ros2
sudo cp udito-ros2-entorno.sh /etc/profile.d/
grep -q udito-ros2-entorno /etc/bash.bashrc || echo '[ -f /etc/profile.d/udito-ros2-entorno.sh ] && . /etc/profile.d/udito-ros2-entorno.sh' | sudo tee -a /etc/bash.bashrc

# 5. Compilar el paquete (primera vez)
cd /opt/cognitive-robotics-core/05_ROS2/ros2_ws && colcon build --packages-select central_control voice_skills --symlink-install
```

## Arrancar el robot

| Forma | Comando |
|-------|---------|
| Nativa ROS 2 | `ros2 launch central_control udito_voice.launch.py` |
| Atajo (cierra instancias anteriores y compila si hace falta) | `robot` (= `./scripts/ros2/udito-ros.sh`) |

Las opciones (`whisper:=`, `stt_mode:=`, `mic:=`…) están en el README de `central_control`.

## Comprobar que todo está bien

```bash
systemctl is-active udito-jetson-arranque.service   # active
nvpmodel -q                                         # NV Power Mode: MAXN_SUPER
snap refresh --time | grep -i hold                  # hold: forever
ros2 pkg list | grep -E 'central_control|voice_skills'   # central_control y voice_skills
```
