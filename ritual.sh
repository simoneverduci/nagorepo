#!/bin/bash
# ritual.sh — Nago's grimoire ritual cycle
# Run from the nagorepo repo root.
# 1. Rebuild state.json + LOG.md from the live RAG
# 2. Commit and push to GitHub (triggers Pages deploy)

set -e

REPO="C:/_PROJECTS/nagorepo"
cd "$REPO"

echo "=== NAGOREPO RITUAL ==="
echo "Pulling new fragments from the Papers library..."

# Use system Python 3.12
PYTHON="/c/Users/info/AppData/Local/Programs/Python/Python312/python.exe"
$PYTHON grimoire.py 2>&1 || {
    echo "Ritual failed during build. State unchanged."
    exit 1
}

# Read cycle number from state
CYCLE=$(python -c "import json; print(json.load(open('state.json'))['cycle'])")
OBS=$(python -c "import json; d=json.load(open('state.json')); print(d.get('obsession','?')[:40])")

git add state.json LOG.md 2>/dev/null
git commit -m "ritual cycle ${CYCLE} — ${OBS}" 2>/dev/null || echo "Nothing new to commit."
git push origin main 2>&1

echo "=== RITUAL CYCLE ${CYCLE} COMPLETE ==="
echo "Obsession: ${OBS}"
echo "See: https://simoneverduci.github.io/nagorepo/"
