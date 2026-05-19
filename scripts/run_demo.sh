#!/usr/bin/env bash
# Genera el demo offline y abre el reporte HTML.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=.
python examples/synthetic_demo.py
echo
echo "Demo listo. Abre: out/demo/report.html"
