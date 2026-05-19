# Ejemplo end-to-end

Este ejemplo asume que tienes Python 3.11+ y un ORCID válido. Para datos reales
necesitas conexión a internet; para una prueba offline se incluye un demo
sintético en `examples/synthetic_demo.py`.

## Instalación

```bash
git clone <repo> scholarly-profile-auditor
cd scholarly-profile-auditor
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# editar .env: SPA_USER_EMAIL para "polite pool" de Crossref/OpenAlex
```

## Auditoría mínima (solo ORCID)

```bash
spa audit --orcid 0000-0002-1825-0097 --out ./out
```

Después de ~30s tendrás en `./out/0000-0002-1825-0097/`:

```
canonical_works.json    # bibliografía consolidada con trazabilidad
canonical_works.bib     # BibTeX listo para reuso
report.html             # reporte humano-legible
report.json             # mismo contenido en JSON
audit_log.md            # bitácora + decisiones por obra
widget/data.json        # alimenta el widget embebible
```

## Auditoría completa

```bash
spa audit \
  --orcid 0000-0002-1825-0097 \
  --scholar "https://scholar.google.com/citations?user=ABCDEFG" \
  --refs ./mis_referencias.bib \
  --alias "R. Pérez-Buendía" \
  --alias "Rogelio Pérez Buendía" \
  --whitelist ./whitelist.txt \
  --area fisico_matematicas \
  --out ./out
```

Donde:
- `whitelist.txt` — un título normalizado por línea (ver
  `app/core/normalize.py`); las obras coincidentes se fuerzan a confirmadas.
- `--alias` puede repetirse.
- `--area` activa los umbrales de referencia del archivo
  `config/snii_reference_params.yaml`.

## Servidor + widget

```bash
spa serve --host 127.0.0.1 --port 8088
# abrir http://127.0.0.1:8088/widget/index.html
```

Desde la página del widget puedes capturar el ORCID, opcionalmente el URL de
Scholar y un archivo de referencias, y obtener el resultado renderizado.

## Embeber el widget en tu web personal

Tras una auditoría exitosa tienes `out/<orcid>/widget/data.json`. Súbelo
junto al `widget/index.html` y `widget/app.js` a tu sitio. Luego:

```html
<!-- Como página independiente -->
<a href="/spa-widget/index.html?data=local">Ver mi auditoría</a>

<!-- Como iframe -->
<iframe
  src="/spa-widget/index.html?data=local"
  width="100%" height="900" style="border:none;"
  title="Mi perfil académico auditado">
</iframe>
```

El `?data=local` indica al widget que cargue `data.json` del mismo
directorio en lugar de llamar al backend. Esto produce una página
estática totalmente embebible sin servidor.

## Demo offline (sin red)

```bash
python examples/synthetic_demo.py
```

Genera `./out/demo/` con un perfil sintético de 6 obras, sin necesidad de
conexión. Útil para probar la cadena de exports y el widget aislado.
