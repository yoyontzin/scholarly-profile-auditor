# Changelog

Todos los cambios notables a este proyecto se documentan aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/), versionado [SemVer](https://semver.org/).

## [0.2.0] — 2026-05-15

### Added
- **Widget standalone con flujo human-in-the-loop de 3 pasos**:
  1. Identificación de autor por ORCID / URL de Google Scholar / nombre completo
     con búsqueda exhaustiva en OpenAlex Authors, ORCID Search y
     Semantic Scholar Author Search; usuario confirma con checklist.
  2. Búsqueda exhaustiva de obras en ORCID, OpenAlex, Semantic Scholar,
     arXiv y Crossref; deduplicación con score de confianza por
     número de fuentes; usuario marca cuáles son suyas.
  3. Análisis Cita A / Cita B sobre las obras confirmadas.
- Análisis de citas **Cita A** (`A(C) ∩ A(W) = ∅`) y **Cita B** (`E ∉ A(C)`)
  con definiciones textuales oficiales de los Criterios SNII Área I.
- Conector `app/connectors/semantic_scholar.py` para complementar OpenAlex
  cuando éste no indexa citaciones.
- Módulo `app/metrics/snii_citations.py` con dataclasses
  `WorkCitationAnalysis` y `GlobalCitationSummary`.
- 10 tests en `tests/test_snii_citations.py` que verifican la lógica de
  clasificación, la regla "evaluado en citante ⇒ overlap", el manejo de
  apóstrofes LaTeX Unicode (Semantic Scholar) y la identidad
  `A + (B-A) + autocitas = total`.
- Documentación Zenodo (`.zenodo.json`, `CITATION.cff`) y `LICENSE` MIT.
- Script `scripts/run_rpb.sh` para corrida local con todos los conectores.

### Fixed
- Normalización de nombres ahora elimina apóstrofes Unicode (U+2018, U+2019)
  que Semantic Scholar usa al serializar acentos (e.g. `P'erez-Buend'ia`).
  Antes esto causaba falsos negativos en el matching de autocitas.
- Si el evaluado está en el citante, `overlap` con A(W) es forzado a True
  (porque E ∈ A(W) trivialmente). Antes podía clasificarse como Cita A
  cuando los nombres venían en variantes (e.g. "J. Rogelio" vs "J. R.").

### Changed
- El módulo SNII no emite niveles automáticos. La política dura
  `emit_automatic_level: False` se preserva en config y en el código.

## [0.1.0] — 2026-05-11

### Added
- FASE 1: arquitectura, modelos Pydantic, configuración (`.env` + YAML),
  `SKILL.md`, `README.md`.
- FASE 2: conectores async (ORCID, OpenAlex, Crossref, DataCite, arXiv,
  Scholar) con httpx + aiolimiter + tenacity. Parsers BibTeX, RIS,
  CSL-JSON, CSV.
- FASE 3: deduplicación por DOI → arXiv → fuzzy título+año; scoring
  multi-señal de autoría con política "require_stable_id_for_confirm".
- FASE 4: métricas por fuente (sin sumar entre fuentes), módulo SNII-style
  inicial con `automatic_level: None` hard-coded.
- FASE 5: exports (`canonical_works.json`, `canonical_works.bib`,
  `report.html`, `audit_log.md`, `widget/data.json`).
- FASE 6: widget HTML embebible con backend FastAPI opcional.
- FASE 7: 44 tests en `pytest` (normalización, dedupe, scoring,
  conectores mockeados con respx).
