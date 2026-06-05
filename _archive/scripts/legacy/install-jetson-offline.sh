#!/usr/bin/env bash
# Instala cognitive-robotics-core en Jetson (modo offline / edge, sin Docker cerebro).
set -euo pipefail

TARGET_DIR="/opt/robita-lab"

if [[ -z "${1:-}" ]] || [[ -z "${2:-}" ]]; then
  read -r -p "Usuario GitHub: " GITHUB_USER
  read -r -s -p "Token GitHub: " GITHUB_TOKEN
  echo ""
else
  GITHUB_USER="$1"
  GITHUB_TOKEN="$2"
fi

echo "[sudo] Directorio $TARGET_DIR..."
sudo mkdir -p "$TARGET_DIR"
sudo chown -R "$USER:$USER" "$TARGET_DIR"

echo "==> Descargando repo (tarball main)..."
TAR_URL="https://${GITHUB_USER}:${GITHUB_TOKEN}@api.github.com/repos/robita-lab/cognitive-robotics-core/tarball/main"

# Conservar data/ y .env si ya existían
BACKUP="$(mktemp -d)"
[[ -d "$TARGET_DIR/data" ]] && cp -a "$TARGET_DIR/data" "$BACKUP/" || true
[[ -f "$TARGET_DIR/.env" ]] && cp "$TARGET_DIR/.env" "$BACKUP/" || true

find "$TARGET_DIR" -mindepth 1 -maxdepth 1 ! -name "install-jetson-offline.sh" -exec rm -rf {} +

curl -fsSL "$TAR_URL" | tar -xz -C "$TARGET_DIR" --strip-components=1

[[ -d "$BACKUP/data" ]] && cp -a "$BACKUP/data" "$TARGET_DIR/" || true
[[ -f "$BACKUP/.env" ]] && cp "$BACKUP/.env" "$TARGET_DIR/" || true
rm -rf "$BACKUP"

cd "$TARGET_DIR"
chmod +x scripts/*.sh 2>/dev/null || true
./scripts/setup-jetson-offline.sh

echo ""
echo "Instalación base OK. Siguiente: ./scripts/download-offline-models.sh"
