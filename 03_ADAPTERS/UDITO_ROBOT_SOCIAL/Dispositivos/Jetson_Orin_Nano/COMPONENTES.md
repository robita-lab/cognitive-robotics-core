# Arquitectura híbrida - UDITO · Jetson Orin Nano · Componentes

| Pieza | Modelo | Para qué | Dónde conseguirla | Notas |
|-------|--------|----------|-------------------|-------|
| Ordenador | NVIDIA Jetson Orin Nano Developer Kit (8 GB, «Super») | Voz, rostro, cognitive local | Distribuidores oficiales de NVIDIA | — |
| Almacenamiento actual | microSD | Sistema | — | Se sustituirá por NVMe (D17) |
| Almacenamiento previsto | SSD NVMe M.2 2280 | Sistema, modelos y *swap*; necesario para JetPack 7.2 / Jazzy | Por completar | Compra aprobada (D17) |
| Micrófono y audio | Seeed Studio ReSpeaker 4-Mic Array (USB, `2886:0018`) | Oír (STT), DOA, salida a altavoz | Seeed Studio y distribuidores | La regla udev de `arranque/` lo reserva para el robot |
| Altavoz | Por completar | Voz del robot | Por completar | Conectado al ReSpeaker |
| Pantalla de rostro | Por completar | Cara del robot | Por completar | — |
| Alimentación | Fuente oficial del kit | — | Incluida en el kit | — |
| Red | Cable Ethernet a MiniPC / LAN del laboratorio | ROS 2 y servidor | — | — |

> Completar las filas «Por completar» con modelo exacto y proveedor cuando se confirmen.
