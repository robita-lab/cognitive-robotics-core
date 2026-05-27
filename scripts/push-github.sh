#!/usr/bin/env bash
# Sube cambios a GitHub (PAT por variable, no en el repo).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

REPO_URL="https://github.com/robita-lab/cognitive-robotics-core.git"

if [[ ! -d .git ]]; then
  git init -b main
  git remote add origin "$REPO_URL" 2>/dev/null || git remote set-url origin "$REPO_URL"
fi

# No subir secretos ni modelos pesados
git add -A
git reset HEAD .env .env.local 2>/dev/null || true
git status

if [[ -z "$(git status --porcelain)" ]]; then
  echo "Nada que commitear."
  exit 0
fi

MSG="${1:-feat(jetson): UDITO offline Jetson — voz, RAG y conocimiento}"
git commit -m "$MSG"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  git pull --rebase origin main 2>/dev/null || git pull origin main --allow-unrelated-histories 2>/dev/null || true
  git push "https://${GITHUB_TOKEN}@github.com/robita-lab/cognitive-robotics-core.git" HEAD:main
else
  echo ""
  echo "Commit creado. Para subir a GitHub:"
  echo "  GITHUB_TOKEN=ghp_xxx $0 \"$MSG\""
  echo "  o: git push -u origin main"
fi
