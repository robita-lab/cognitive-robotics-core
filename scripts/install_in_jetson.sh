#!/bin/bash

# Comprobar si se ejecuta desde el directorio correcto al descargarse
TARGET_DIR="/opt/robita-lab"

echo "[SUDO] Solicitando permisos para configurar el directorio..."
sudo mkdir -p $TARGET_DIR
sudo chown -R $USER:$USER $TARGET_DIR
cd $TARGET_DIR

# Solicitar credenciales de forma interactiva y segura
read -p "👤 Ingresa tu usuario de GitHub: " GITHUB_USER
read -s -p "🔑 Ingresa tu Token de GitHub: " GITHUB_TOKEN
echo ""

echo "📁 Limpiando entorno previo..."
rm -rf $TARGET_DIR/*

echo "📥 Descargando componentes de la Jetson..."
TAR_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@api.github.com/repos/robita-lab/cognitive-robotics-core/tarball/main"

# Descarga y extrae omitiendo la carpeta raíz del Monorepositorio
curl -sL $TAR_URL | tar -xz --strip-components=1 \
    "*/01_SERVICES" \
    "*/02_AGENTS_FACTORY/udit-robot-brain" \
    "*/03_ADAPTERS/robot-udit-physical" \
    "*/04_KNOWLEDGE_CORE" \
    "*/scripts"

echo "⚙️ Configurando variables de entorno..."
if [ -f ".env.example" ]; then
    cp .env.example .env
    echo "✅ Archivo .env generado."
else
    echo "⚠️ .env.example no encontrado en el repositorio."
fi

echo "🚀 Iniciando contenedores en Docker..."
sudo docker compose up --build -d

echo "✅ Proceso finalizado con éxito."
