#!/bin/bash
echo "🤖 Iniciando instalación automatizada de UDITO (Jetson Edge)..."

# 1. Pedir credenciales de forma segura
read -p "👤 Ingresa tu usuario de GitHub: " GITHUB_USER
read -s -p "🔑 Ingresa tu Token de GitHub (no se verá mientras escribes): " GITHUB_TOKEN
echo ""

TARGET_DIR="/opt/robita-lab/cognitive-robotics-core"

# 2. Limpiar e inicializar la carpeta
echo "📁 Preparando el entorno en $TARGET_DIR..."
sudo rm -rf $TARGET_DIR
sudo mkdir -p $TARGET_DIR
sudo chown -R $USER:$USER /opt/robita-lab
cd $TARGET_DIR

# 3. Descarga (Sparse-Checkout)
echo "📥 Descargando SOLO los módulos esenciales de IA y ROS2..."
git init
git remote add origin https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/robita-lab/cognitive-robotics-core.git
git sparse-checkout init --cone
git sparse-checkout set 01_SERVICES 02_AGENTS_FACTORY/udit-robot-brain 03_ADAPTERS/robot-udit-physical 04_KNOWLEDGE_CORE scripts

# 4. Traer el código
git pull origin main

# 5. Configurar variables de entorno
echo "⚙️ Configurando archivo .env..."
cp .env.example .env

# 6. Levantar la arquitectura completa
echo "🚀 Compilando y levantando contenedores en Docker..."
sudo docker compose up --build -d

echo "✅ ¡Instalación completada! El cerebro de UDITO está funcionando."
