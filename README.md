# 🤖 ROBITA-LAB: Manual de Infraestructura y Desarrollo

Este servidor central (`/opt/robita-lab`) es el entorno de desarrollo activo e integración para el laboratorio de Robótica Social y Agentes de IA. A diferencia de GitHub, que actúa como el control de versiones histórico, este servidor es el **banco de pruebas físico y digital** donde se valida el pipeline antes de su despliegue final.

---

## 🏗️ 1. Filosofía de Trabajo y Ciclo de Vida
El desarrollo en ROBITA-LAB sigue un ciclo de **"Server-First Integration"**:

1.  **Desarrollo**: Se codifica en ramas `feature/` siguiendo la guía `GIT-FLOW.md`.
2.  **Validación**: Se despliega el componente en este servidor para probar la comunicación real entre servicios (ej. que el RAG responda al motor de gesticulación).
3.  **Sincronización**: Una vez validado, se hace `push` a GitHub.
4.  **Despliegue (Pull)**: Los dispositivos finales (como el robot UDITO o servidores web) realizan un `pull` de las imágenes de Docker o el código verificado.

---

## 📁 2. Arquitectura de Directorios (Niveles del Ecosistema)

### [01_SERVICES] — El Cerebro (Lógica de IA)
Contiene los servicios de procesamiento de lenguaje y señales. 
- **Modularidad**: Cada motor (STT, TTS, RAG) es independiente.
- **Escalabilidad**: Permite intercambiar motores pesados (Online/Server) por motores ligeros (Offline/Jetson).
- **Ejemplo**: El `rag-engine` puede usar un modelo GPT-4 vía API o un modelo Llama-3 local dependiendo de la conectividad.

### [02_AGENTS_FACTORY] — Personalidades e Instancias
Es la capa de configuración que define el "Quién" del asistente.
- **Contenido**: Prompts de sistema, parámetros de voz y vinculación a bases de datos.
- **Diferenciación**: Aquí se define que un agente en la Web sea un "Asesor de RRHH" y que el mismo cerebro en el robot UDITO sea un "Compañero Social". **No se cambia el código del motor, solo el perfil en esta carpeta.**

### [03_ADAPTERS] — El Cuerpo (Hardware y Clientes)
Contiene el código que conecta la IA con el mundo real o interfaces digitales.
- **Robot Social (UDIT)**: Contiene el entorno **ROS** (Robot Operating System). Recibe el JSON de la IA (texto + emoción) y lo traduce a movimientos físicos (servos de cara, ruedas, luces).
- **Web Clients**: Interfaces que adaptan el RAG a portales institucionales.

### [04_KNOWLEDGE_CORE] — El Saber (Persistencia)
Memoria a largo plazo organizada para un **RAG Escalable**.
- **Vector Stores**: Índices segmentados por áreas (Admisiones, Finanzas, etc.).
- **ProtoBrain**: Evolución hacia grafos cognitivos para relaciones de datos complejas.
- **Raw Docs**: Repositorio de los documentos originales (PDF/Texto) de la universidad.

---

## 🚀 3. Integración en Hardware (Ejemplo: UDITO / Jetson)

Para llevar la inteligencia del servidor al robot físico:

1.  **Sincronización**: El hardware (Jetson Nvidia) clona la rama `develop` de este servidor.
2.  **Pipeline de Asistente**: La Jetson ejecuta localmente el adaptador (`03_ADAPTERS/robot-udit-physical`) para gestionar sensores y motores en tiempo real vía ROS.
3.  **Modo Offline**: Si el robot pierde conexión, el sistema conmuta automáticamente a los modelos almacenados en las subcarpetas de este servidor optimizadas para ejecución local (Modelos cuantizados).



---

## 🛠️ 4. Reglas de Operación para Investigadores

* **Dockerización**: Es obligatorio que cada componente tenga su `Dockerfile`. Esto garantiza que el código que funciona en este servidor funcione igual en la Jetson de un robot o en la nube.
* **Gestión de Permisos**: La carpeta `/opt/robita-lab` es compartida. Todo archivo debe pertenecer al grupo `robita-group`.
    * *Comando de emergencia:* `sudo chown -R :robita-group /opt/robita-lab && sudo chmod -R 775 /opt/robita-lab`
* **Git-Flow**: Consultar `GIT-FLOW.md`. Nunca trabajes directamente en `develop`. Crea una `feature/` para cada modificación.
* **Agnosticismo**: Evita rutas absolutas. Usa variables de entorno para que el robot pueda encontrar sus servicios sin importar si la IP del servidor cambia.

---

## 📡 5. Despliegue de Servicios
Para iniciar el entorno de pruebas en este servidor:
```bash
cd /opt/robita-lab
docker-compose up -d
