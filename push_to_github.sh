#!/usr/bin/env bash
# Sube este proyecto a GitHub. Requiere: git y gh (GitHub CLI) ya instalados.
# Si no has iniciado sesion en gh:  gh auth login
set -e
cd "$(dirname "$0")"
REPO="${1:-TUTOR_2_LEARN_LOCALLY}"
VIS="${2:---public}"   # usa  ./push_to_github.sh TUTOR_2_LEARN_LOCALLY --private  para privado

if [ ! -d .git ]; then
  git init
  git branch -M main
fi
git add .
git commit -m "TUTOR_2_LEARN_LOCALLY: tutor de IA local con ingesta de PDF y RAG" || echo "(nada nuevo que commitear)"

# Crea el repo en tu cuenta y sube (si ya existe, solo hace push)
if gh repo view "$REPO" >/dev/null 2>&1; then
  git remote add origin "https://github.com/$(gh api user -q .login)/$REPO.git" 2>/dev/null || true
  git push -u origin main
else
  gh repo create "$REPO" "$VIS" --source=. --remote=origin --push
fi
echo "Listo. Abrelo con:  gh repo view --web $REPO"
