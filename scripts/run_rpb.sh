#!/usr/bin/env bash
# ============================================================================
# Auditoría completa para Rogelio Pérez-Buendía con ORCID + Scholar.
# Pensado para correr en macOS desde IP residencial (Scholar no bloquea ahí).
#
# Uso:
#   cd ~/Documents/scholarly-profile-auditor
#   bash scripts/run_rpb.sh
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_DIR="$PWD"

ORCID="0000-0002-7739-4779"
SCHOLAR_URL="https://scholar.google.com/citations?user=Y0mbwdoAAAAJ&hl=es"
EMAIL="rogelio.perez@cimat.mx"
OUT_DIR="$PROJECT_DIR/out/$ORCID"

echo "============================================================"
echo " Scholarly Profile Auditor"
echo " ORCID:   $ORCID"
echo " Scholar: $SCHOLAR_URL"
echo " Out:     $OUT_DIR"
echo "============================================================"

# ---------- Paso 1: Python 3.11+ ----------
PY=""
for cand in python3.12 python3.11 python3; do
  if command -v "$cand" >/dev/null 2>&1; then
    ver=$("$cand" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "")
    if [[ "$ver" > "3.10" || "$ver" == "3.11" || "$ver" == "3.12" || "$ver" == "3.13" ]]; then
      PY="$cand"; break
    fi
  fi
done
if [ -z "$PY" ]; then
  echo "ERROR: necesitas Python 3.11 o superior. Instala con:  brew install python@3.12"
  exit 1
fi
echo "Python: $PY ($($PY --version))"

# ---------- Paso 2: venv (limpiar si quedó corrupto) ----------
if [ -d ".venv" ] && [ ! -x ".venv/bin/python" ]; then
  echo "→ Limpiando .venv corrupto..."
  rm -rf .venv
fi
if [ ! -d ".venv" ]; then
  echo "→ Creando venv en .venv..."
  "$PY" -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

# ---------- Paso 3: dependencias ----------
echo "→ Instalando dependencias (puede tardar ~1 min la primera vez)..."
pip install --quiet -e ".[dev]"

# ---------- Paso 4: configuración ----------
if [ ! -f ".env" ]; then
  cp .env.example .env
fi
# Asegurar email
if ! grep -q "^SPA_USER_EMAIL=" .env; then
  echo "SPA_USER_EMAIL=$EMAIL" >> .env
fi
export SPA_USER_EMAIL="$EMAIL"
export SPA_ENABLE_SCHOLAR=true

# ---------- Paso 5: ejecutar pipeline ----------
echo ""
echo "→ Corriendo pipeline (ORCID + OpenAlex + Crossref + DataCite + arXiv + Scholar)..."
echo "  Si Scholar bloquea, el pipeline continúa con las demás fuentes."
echo ""

spa audit \
  --orcid "$ORCID" \
  --scholar "$SCHOLAR_URL" \
  --area fisico_matematicas \
  --alias "Rogelio Yoyontzin" \
  --alias "J. Rogelio Pérez-Buendía" \
  --alias "Jesús Rogelio Pérez Buendía" \
  --out "./out"

# ---------- Paso 6: abrir reporte ----------
REPORT="$OUT_DIR/report.html"
if [ -f "$REPORT" ]; then
  echo ""
  echo "============================================================"
  echo " Reporte generado:"
  echo "   $REPORT"
  echo "============================================================"
  open "$REPORT" 2>/dev/null || true
else
  echo "ADVERTENCIA: no se encontró $REPORT"
fi

# ---------- Paso 7: levantar widget opcional ----------
echo ""
echo "Para servir el widget interactivo:"
echo "   source .venv/bin/activate && spa serve --port 8088"
echo "   open http://127.0.0.1:8088/widget/index.html"
