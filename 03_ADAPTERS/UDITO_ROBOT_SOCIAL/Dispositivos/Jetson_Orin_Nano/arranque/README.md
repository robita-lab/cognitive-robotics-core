# Arquitectura híbrida - UDITO · Arranque de la Jetson

> **Arquitectura híbrida** = evolución del 3T acordada en el consenso de ROBITA-lab (D14): 4 capas
> (0 plataforma · 1 habilidades · 2 ejecutiva con Behavior Tree · 3 deliberativa) + 4 planos transversales
> (seguridad, modelo del mundo, modos y salud, observabilidad). Este documento trata la base de todo:
> que el **hardware de la Jetson** (capa 0) esté preparado antes de que arranque ninguna otra capa.

---

## Idea principal

Los ajustes de **hardware** de la Jetson se aplican **una sola vez, al iniciar Ubuntu**, sin que nadie tenga que acordarse de ellos. Cuando se arranca el robot (`ros2 launch …`), la máquina ya está lista y el lanzador no tiene que hacer nada de esto.

| Ajuste | Cuándo se aplica | Cómo |
|--------|------------------|------|
| Modo de energía MAXN_SUPER | **En cada arranque** | Servicio `udito-jetson-arranque.service` (`nvpmodel -m 2`) |
| CPU, GPU y memoria a frecuencia máxima | **En cada arranque** | Mismo servicio (`jetson_clocks`) |
| ReSpeaker reservado para el robot | **En cada arranque** (al detectar el dispositivo) | Regla udev `99-udito-respeaker.rules` |
| Actualizaciones automáticas de snap en pausa | **Una vez** (queda guardado) | `snap refresh --hold` |

---

## Por qué cada ajuste

### 1. Modo de energía MAXN_SUPER (`nvpmodel -m 2`)

- **Problema:** la Jetson venía en el modo **15W**, que limita la CPU a 1,5 GHz y la GPU a 612 MHz.
- **Solución:** el kit Orin Nano «Super» tiene el modo **MAXN_SUPER** (sin límite de consumo): CPU a **1,73 GHz** y GPU a **1,02 GHz**.
- **Modos disponibles** (`/etc/nvpmodel.conf`): `0` = 15W · `1` = 25W · `2` = MAXN_SUPER · `3` = 7W.
- **Coste:** más consumo y calor. Necesita la fuente oficial del kit y el ventilador.
- **Si el robot va con batería** y hace falta ahorrar: cambiar `-m 2` por `-m 1` (25W) en el servicio.
- **Analogía:** pasar de un contrato de luz limitado a uno sin tope de potencia.

### 2. Frecuencias al máximo (`jetson_clocks`)

- **Problema:** de fábrica, la Jetson ajusta la velocidad de la CPU y la GPU según la carga, empezando baja para ahorrar energía. Whisper (el oído del robot) necesita mucha CPU de golpe al terminar cada frase.
- **Medido en UDITO:** sin este ajuste, transcribir una frase tardaba **13–27 s**; con él, **~1,5 s**.
- **Coste:** más consumo y algo más de calor. El ventilador del kit lo gestiona sin problema.
- **Analogía:** es como tener el coche ya en marcha y caliente antes de salir, en vez de arrancar en frío en cada semáforo.

### 3. ReSpeaker reservado para el robot (`PULSE_IGNORE`)

- **Problema:** el robot usa el ReSpeaker (micrófono y altavoz) directamente (ALSA). Si el sonido del escritorio (PulseAudio) lo abre antes, el robot recibe **«Device or resource busy»**: no oye y no habla.
- **Solución:** una regla udev le dice a PulseAudio que ignore el ReSpeaker. El escritorio sigue teniendo sonido por HDMI, pero el ReSpeaker queda **solo para el robot**.
- **Consecuencia:** el ReSpeaker no aparece en *Configuración → Sonido* del escritorio. Es lo esperado.

### 4. Actualizaciones de snap en pausa (`snap refresh --hold`)

- **Problema:** el servicio `snapd` se ponía a actualizar programas en segundo plano y llegó a consumir el **44 % de la CPU**, justo cuando el robot necesitaba transcribir.
- **Solución:** pausar las actualizaciones **automáticas** de snap. Los programas instalados con snap (por ejemplo, el navegador) **siguen funcionando**.
- **Mantenimiento:** para actualizar a mano cuando convenga (con el robot parado): `sudo snap refresh`.
- **Por qué no se desactiva snapd del todo:** si se para `snapd`, dejan de abrirse los programas instalados con snap.

---

## Instalación (una sola vez, en la Jetson)

Desde esta carpeta, en una terminal de la Jetson:

```bash
sudo cp udito-jetson-arranque.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now udito-jetson-arranque.service
sudo cp 99-udito-respeaker.rules /etc/udev/rules.d/
sudo udevadm control --reload-rules && sudo udevadm trigger
sudo snap refresh --hold
```

Reinicia la Jetson para comprobar que todo se aplica solo.

## Comprobación (tras reiniciar)

```bash
systemctl is-active udito-jetson-arranque.service      # → active
nvpmodel -q                                            # → NV Power Mode: MAXN_SUPER
sudo jetson_clocks --show | grep -E "cpu0|GPU "        # cpu0 1728000 · GPU 1020000000
snap refresh --time | grep -i hold                     # → hold: forever
```

Y el robot debe arrancar, oír y hablar sin ningún comando previo.

## Desinstalar (volver al estado de fábrica)

```bash
sudo systemctl disable --now udito-jetson-arranque.service
sudo rm /etc/systemd/system/udito-jetson-arranque.service /etc/udev/rules.d/99-udito-respeaker.rules
sudo udevadm control --reload-rules
sudo snap refresh --unhold
sudo nvpmodel -m 0                                      # vuelve al modo 15W de fábrica
```

---

## Qué NO va aquí

Los parámetros **funcionales** (modelo de Whisper, modo «mantén para hablar» o escucha continua, volumen, activar el Cognitive) no son de hardware: van como **argumentos del lanzador de ROS 2**, documentados en el README del paquete.
