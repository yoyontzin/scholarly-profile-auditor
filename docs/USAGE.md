# Guía de uso — Scholarly Profile Auditor

Tres formas de usar el software, ordenadas de menos a más sofisticadas.

## Opción 1 — Widget en el navegador (sin instalación)

El uso más simple para investigadores no-programadores y para incrustar en
una página académica personal.

### Cómo usarlo localmente

```bash
# Abre el archivo directamente con tu navegador
open widget/standalone.html
# o equivalente en Linux: xdg-open widget/standalone.html
```

No necesitas servidor ni instalar nada. Todo el procesamiento ocurre en tu
navegador llamando a las APIs públicas (ORCID, OpenAlex, Semantic Scholar,
arXiv, Crossref) mediante CORS.

### Cómo embeberlo en tu página académica

Sube `widget/standalone.html` a tu sitio (puede ser un repo de GitHub Pages
o tu hosting institucional). Embebe en cualquier página con:

```html
<iframe
  src="/scholarly-profile-auditor/standalone.html?orcid=0000-0002-7739-4779"
  width="100%" height="1200" style="border:none; border-radius:6px;"
  title="Mi auditoría bibliográfica">
</iframe>
```

Parámetros de URL soportados:

| Parámetro | Significado | Ejemplo |
|---|---|---|
| `orcid` | pre-llena el campo ORCID | `?orcid=0000-0002-1825-0097` |
| `autorun=1` | dispara la búsqueda automáticamente | `?orcid=...&autorun=1` |

### Flujo de uso

**Paso 1 — Identificación.** Elige uno de tres modos:

- **ORCID**: si lo tienes, es el camino más rápido y exacto.
- **URL de Google Scholar**: extrae el `user_id` y consolida con OpenAlex
  y SS (Scholar bloquea CORS desde navegador, pero los otros funcionan).
- **Sólo nombre**: el sistema busca candidatos en paralelo en OpenAlex
  Authors, ORCID Search y Semantic Scholar Authors. Los presenta como
  *checklist* con sus afiliaciones, número de obras y citas. Marcas el
  correcto y continúas.

**Paso 2 — Confirmación de obras.** Una vez identificado el autor, el
sistema busca publicaciones en **cinco fuentes en paralelo** (ORCID works,
OpenAlex por author ID, Semantic Scholar por author ID, arXiv por nombre,
Crossref por nombre), deduplica por DOI → arXiv → título+año, y muestra
cada obra con un **score de confianza** (número de fuentes que la
mencionan). Tú marcas con *checkbox* cuáles son tuyas. El sistema
pre-marca las que aparecen en 2+ fuentes.

**Paso 3 — Análisis Cita A / Cita B.** Para cada obra marcada el sistema
consulta sus citantes vía OpenAlex `filter=cites:Wxxx` y Semantic Scholar
`/paper/DOI:.../citations`. Clasifica cada citante según las definiciones
oficiales SNII:

- **Cita A** ⇔ `A(C) ∩ A(W) = ∅` (citante no tiene a *ningún* autor del
  trabajo).
- **Cita B** ⇔ `E ∉ A(C)` (citante no tiene al evaluado).
- **Autocita estricta** ⇔ `E ∈ A(C)`.

Identidad verificada: `Cita A + (B − A) + autocitas = total`.

Exportas los resultados como JSON o BibTeX desde el botón al final.

---

## Opción 2 — CLI desde terminal (Python local)

Para reproducibilidad, automatización o integración con tu pipeline
académico.

### Instalación (una vez)

```bash
git clone <repo> scholarly-profile-auditor
cd scholarly-profile-auditor
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Edita .env con tu email para "polite pool" de OpenAlex/Crossref
```

### Comandos

```bash
# Auditoría mínima: solo ORCID
spa audit --orcid 0000-0002-XXXX-XXXX --out ./out

# Auditoría completa con todos los inputs opcionales
spa audit \
  --orcid 0000-0002-XXXX-XXXX \
  --scholar "https://scholar.google.com/citations?user=XXXXXXX" \
  --refs ./mis_refs.bib \
  --alias "R. Apellido" --alias "Nombre Completo" \
  --whitelist ./whitelist.txt \
  --area fisico_matematicas \
  --out ./out

# Servidor + widget (con backend FastAPI)
spa serve --port 8088
# → abre http://127.0.0.1:8088/widget/index.html

# Configuración efectiva (debug)
spa config-show
```

### Salidas

Tras una corrida exitosa, `./out/<orcid>/` contiene:

```
canonical_works.json        # bibliografía consolidada con trazabilidad
canonical_works.bib         # equivalente BibTeX
report.html                 # reporte humano-legible
report.json                 # mismo contenido en JSON
audit_log.md                # bitácora + decisiones por obra
widget/data.json            # alimenta el widget si lo embebes
```

---

## Opción 3 — Como librería Python

```python
import asyncio
from app.services.pipeline import PipelineInput, run_pipeline
from app.services.exports import export_all
from pathlib import Path

async def main():
    inp = PipelineInput(
        orcid="0000-0002-XXXX-XXXX",
        scholar_url=None,
        user_refs_path=None,
        area_snii="fisico_matematicas",
    )
    result = await run_pipeline(inp)
    artifacts = export_all(result, Path("./out/mi-auditoria"))
    print(artifacts)

asyncio.run(main())
```

Análisis Cita A/B aparte:

```python
from app.metrics.snii_citations import run_snii_citation_analysis

per_work, summary = await run_snii_citation_analysis(
    works=result.works,
    author_orcid="0000-0002-XXXX-XXXX",
    author_name_variants=["R. Apellido", "Nombre Apellido"],
    only_confirmed=True,
)
print(f"Cita A total: {summary.total_cita_A}")
print(f"Cita B total: {summary.total_cita_B}")
print(f"Cumple Nivel II por A: {summary.meets_nivel_ii_by_A}")
```

---

## Limitaciones documentadas

1. **Cobertura de citaciones en matemáticas.** OpenAlex y Crossref tienen
   cobertura limitada del área. Para muchos autores el número de citas
   indexadas será 0 aunque tengan citas reales. Las bases que sí indexan
   bien matemáticas (MathSciNet, zbMATH) son cerradas y requieren acceso
   institucional; no están integradas.

2. **Google Scholar bloquea CORS y rate-limits agresivos.** Funciona
   ocasionalmente desde IPs residenciales, raramente desde datacenter.
   La librería Python `scholarly` lo intenta best-effort y degrada con
   gracia si falla.

3. **Releases de Zenodo.** Cada actualización de un release en Zenodo emite
   un DOI nuevo. La lógica de dedupe del proyecto fusiona estos releases
   por (título normalizado, año) — útil pero implica una concesión sobre
   la regla "dos DOIs distintos nunca se fusionan".

4. **No emite niveles SNII automáticos.** Política dura del proyecto:
   `emit_automatic_level: false` en `config/snii_reference_params.yaml`.
   El reporte ayuda a documentar el expediente; la decisión es del comité.
