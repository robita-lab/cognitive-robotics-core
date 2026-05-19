#!/bin/bash
TARGET_DIR="/opt/robita-lab"

if [ -z "$1" ] || [ -z "$2" ]; then
    read -p "👤 Ingresa tu usuario de GitHub: " GITHUB_USER
    read -s -p "🔑 Ingresa tu Token de GitHub: " GITHUB_TOKEN
    echo ""
else
    GITHUB_USER=$1
    GITHUB_TOKEN=$2
fi

echo "[SUDO] Configurando directorios..."
sudo mkdir -p $TARGET_DIR
sudo chown -R $USER:$USER $TARGET_DIR

echo "📁 Limpiando entorno..."
# Evitamos borrar el script si se está ejecutando desde dentro de la carpeta
find $TARGET_DIR -mindepth 1 -maxdepth 1 ! -name "install.sh" -exec rm -rf {} +

echo "📥 Descargando componentes de la Jetson..."
TAR_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@api.github.com/repos/robita-lab/cognitive-robotics-core/tarball/main"

# Se añade --wildcards para permitir la selección quirúrgica de carpetas en Ubuntu/Jetson
curl -sL $TAR_URL | tar -xz -C $TARGET_DIR --strip-components=1 --wildcards \
    "*/01_SERVICES" \
    "*/02_AGENTS_FACTORY/udit-robot-brain" \
    "*/03_ADAPTERS/robot-udit-physical" \
    "*/04_KNOWLEDGE_CORE" \
    "*/scripts"

cd $TARGET_DIR

echo "⚙️ Configurando variables de entorno..."
if [ -f ".env.example" ]; then
    cp .env.example .env
fi

echo "🚀 Iniciando contenedores en Docker..."
sudo docker compose up --build -d

echo "✅ Proceso finalizado."
