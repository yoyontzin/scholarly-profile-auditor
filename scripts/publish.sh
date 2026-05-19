#!/usr/bin/env bash
# ============================================================================
# Prepara el repositorio para GitHub y un tarball para Zenodo, en un solo paso.
# Ejecutar EN TU MAC desde la raíz del proyecto:
#     cd ~/Documents/scholarly-profile-auditor
#     bash scripts/publish.sh
#
# No sube nada por sí solo: deja todo listo y te imprime los comandos finales.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."
ROOT="$PWD"

VERSION=$(grep -m1 '^version = ' pyproject.toml | sed -E 's/version = "([^"]+)"/\1/')
RELEASE="scholarly-profile-auditor-v${VERSION}"
DIST="dist"
GH_USER="${GH_USER:-yoyontzin}"   # cámbialo si tu usuario de GitHub es otro

echo "============================================================"
echo " Empaquetando ${RELEASE}"
echo "============================================================"

# ---------- 1. Tests (si hay Python disponible) ----------
PY=$(command -v python3.12 || command -v python3.11 || command -v python3 || true)
if [ -n "$PY" ]; then
  echo "→ Corriendo tests con $PY ..."
  "$PY" -m venv .venv 2>/dev/null || true
  # shellcheck disable=SC1091
  source .venv/bin/activate 2>/dev/null || true
  pip install --quiet -e ".[dev]" 2>/dev/null || pip install --quiet pytest pytest-asyncio respx unidecode bibtexparser rispy rapidfuzz httpx pydantic pydantic-settings pyyaml || true
  PYTHONPATH=. pytest -q --no-header 2>&1 | tail -6 || echo "  (revisa los tests manualmente)"
  deactivate 2>/dev/null || true
else
  echo "→ Sin Python; se omiten tests (correrán en GitHub Actions)."
fi

# ---------- 2. Limpiar caches ----------
echo "→ Limpiando caches..."
find . -type d -name __pycache__ -prune -exec rm -rf {} + 2>/dev/null || true
find . -type d -name '.pytest_cache' -prune -exec rm -rf {} + 2>/dev/null || true
find . -type d -name '*.egg-info' -prune -exec rm -rf {} + 2>/dev/null || true
rm -rf .ruff_cache .mypy_cache build 2>/dev/null || true

# ---------- 3. Tarball para Zenodo ----------
echo "→ Generando tarball..."
mkdir -p "$DIST"
TARBALL="$DIST/${RELEASE}.tar.gz"
tar czf "$TARBALL" \
  --exclude='.git' --exclude='.venv' --exclude='dist' --exclude='out' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='.mypy_cache' --exclude='.ruff_cache' --exclude='.DS_Store' \
  -s ",^\.,${RELEASE}," . 2>/dev/null || \
tar czf "$TARBALL" \
  --exclude='.git' --exclude='.venv' --exclude='dist' --exclude='out' \
  --exclude='__pycache__' --exclude='*.pyc' --exclude='.pytest_cache' \
  --exclude='.mypy_cache' --exclude='.ruff_cache' --exclude='.DS_Store' \
  --transform "s,^\./,${RELEASE}/," .

# ---------- 4. MANIFEST con checksums ----------
echo "→ Generando MANIFEST..."
{
  echo "# ${RELEASE} — manifest"
  echo "# Generado: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  find . -type f \
    -not -path './.git/*' -not -path './.venv/*' -not -path './dist/*' \
    -not -path './out/*' -not -name '*.pyc' -not -name '.DS_Store' \
    -not -path '*/__pycache__/*' | sort | while read -r f; do
      if command -v sha256sum >/dev/null; then sha=$(sha256sum "$f" | awk '{print $1}');
      else sha=$(shasum -a 256 "$f" | awk '{print $1}'); fi
      printf '%s  %s\n' "$sha" "${f#./}"
    done
} > "$DIST/MANIFEST-${VERSION}.txt"

if command -v sha256sum >/dev/null; then sha256sum "$TARBALL" > "$DIST/${RELEASE}.sha256";
else shasum -a 256 "$TARBALL" > "$DIST/${RELEASE}.sha256"; fi

# ---------- 5. Inicializar git si hace falta ----------
if [ ! -d ".git" ]; then
  echo "→ Inicializando repositorio git..."
  git init -b main >/dev/null
fi
git add -A
git -c user.name="${GIT_NAME:-Rogelio Pérez-Buendía}" \
    -c user.email="${GIT_EMAIL:-rogelio.perez@cimat.mx}" \
    commit -m "scholarly-profile-auditor v${VERSION}" >/dev/null 2>&1 || \
    echo "  (nada nuevo que commitear, o ya commiteado)"

echo ""
echo "============================================================"
echo " LISTO. Artefactos en ./${DIST}/"
echo "   • ${RELEASE}.tar.gz   (subir a Zenodo)"
echo "   • ${RELEASE}.sha256"
echo "   • MANIFEST-${VERSION}.txt"
echo "============================================================"
echo ""
echo "PASOS FINALES (cópialos):"
echo ""
echo "  # 1. Crear el repo en GitHub (vía web o gh CLI):"
echo "  gh repo create ${GH_USER}/scholarly-profile-auditor --public --source=. --remote=origin --push"
echo ""
echo "  # …o manualmente si ya lo creaste en github.com:"
echo "  git remote add origin https://github.com/${GH_USER}/scholarly-profile-auditor.git"
echo "  git push -u origin main"
echo ""
echo "  # 2. Conectar Zenodo:  https://zenodo.org/account/settings/github/"
echo "     Activa el toggle del repo 'scholarly-profile-auditor'."
echo ""
echo "  # 3. Crear el release (dispara el archivado en Zenodo + DOI):"
echo "  git tag v${VERSION} && git push origin v${VERSION}"
echo "  gh release create v${VERSION} ${DIST}/${RELEASE}.tar.gz --title 'v${VERSION}' --notes-file CHANGELOG.md"
echo ""
echo "  # 4. Cuando Zenodo te dé el DOI, reemplaza PLACEHOLDER en:"
echo "     CITATION.cff  y  .zenodo.json   →  vuelve a commitear y re-taggear."
