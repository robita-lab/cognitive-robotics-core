# Arquitectura híbrida - UDITO · Entorno ROS 2 de la Jetson

> **Arquitectura híbrida** = evolución del 3T (consenso ROBITA-lab, D14): 4 capas + 4 planos transversales. Diagrama: [`docs/Arquitectura_hibrida_UDITO_v2.png`](../../../../../docs/Arquitectura_hibrida_UDITO_v2.png)

**Para qué:** que cualquier usuario (`udito`, `root`…) abra una terminal y pueda escribir
`ros2 launch central_control udito_voice.launch.py` sin cargar nada a mano.

**Por qué en el sistema y no en cada usuario:** el robot se ha lanzado como `udito` y como `root`;
un único archivo en `/etc/profile.d/` sirve para todos y se mantiene en un solo sitio.

## Instalar (una vez)

```bash
sudo cp udito-ros2-entorno.sh /etc/profile.d/
grep -q udito-ros2-entorno /etc/bash.bashrc || echo '[ -f /etc/profile.d/udito-ros2-entorno.sh ] && . /etc/profile.d/udito-ros2-entorno.sh' | sudo tee -a /etc/bash.bashrc
```

Abre una terminal nueva y comprueba: `ros2 pkg list | grep -E 'central_control|voice_skills'`.

## Desinstalar

```bash
sudo rm /etc/profile.d/udito-ros2-entorno.sh
sudo sed -i '/udito-ros2-entorno/d' /etc/bash.bashrc
```
