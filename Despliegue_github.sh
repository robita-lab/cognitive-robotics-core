#!/bin/bash

# ==============================================================================
# CONFIGURACIÓN (¡Edita los valores aquí antes de ejecutar!)
# ==============================================================================

# 1. Datos para firmar quién hace el cambio:
GIT_EMAIL="robita-lab@udit.es"
GIT_NAME="Robita Lab"

# 2. Datos de acceso a GitHub:
GITHUB_USER="robita-lab@udit.es"   # <-- Cambia esto por tu usuario de GitHub personal
GITHUB_TOKEN="R0b1t4L4b,"      # <-- Cambia las 'xxxxxx' por tu Personal Access Token (PAT)

# ==============================================================================
# SCRIPT DE DESPLIEGUE (No hace falta tocar nada de aquí para abajo)
# ==============================================================================
REPO_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@github.com/robita-lab/cognitive-robotics-core.git"
COMMIT_MESSAGE="feat: Despliegue inicial de la arquitectura Cognitive Robotics Core"

echo "==================================================="
echo "🚀 INICIANDO DESPLIEGUE HACIA ROBITA-LAB"
echo "==================================================="

cd /opt/robita-lab

# Configurar quién eres en Git (Soluciona el error anterior)
echo "👤 Configurando identidad de Git..."
git config user.email "$GIT_EMAIL"
git config user.name "$GIT_NAME"
echo "✅ Identidad configurada: $GIT_NAME <$GIT_EMAIL>"

# Inicializar Git si no lo está
echo "📁 Comprobando estado de Git..."
if [ ! -d ".git" ]; then
    git init
    echo "✅ Repositorio local inicializado (git init)."
fi

# Rama main
git branch -M main

# Conectar con el remoto ocultando el token en pantalla
echo "🔗 Conectando con GitHub..."
if git remote | grep -q "origin"; then
    git remote remove origin
fi
git remote add origin "$REPO_URL"
echo "✅ Remoto configurado exitosamente."

# Preparar carpetas vacías
echo "📂 Preparando archivos (.gitkeep)..."
find . -type d -empty -not -path "./.git/*" -exec touch {}/.gitkeep \;

# Commit
echo "💾 Guardando estado (Commit)..."
git add .
git commit -m "$COMMIT_MESSAGE"

# Push automático
echo "==================================================="
echo "☁️ SUBIENDO A GITHUB DE FORMA AUTOMÁTICA..."
echo "==================================================="
git push -u origin main

echo "==================================================="
echo "🎉 PROCESO FINALIZADO."
echo "Revisa el código en: https://github.com/robita-lab/cognitive-robotics-core"
echo "==================================================="
