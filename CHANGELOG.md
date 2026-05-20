# Changelog

Todos los cambios notables a este proyecto se documentan aquí.
Formato: [Keep a Changelog](https://keepachangelog.com/), versionado [SemVer](https://semver.org/).

## [0.3.0] — 2026-05-19

### Added
- **Conexión widget → CLI** (`spa from-json archivo.json`): el JSON exportado
  por el widget se convierte en los artefactos formales (`report.html`,
  `canonical_works.bib`, `audit_log.md`, `report.json`) con el motor Python
  testeado. Nuevo módulo `app/services/from_widget.py` + 8 tests.
- **Reporte HTML formal y bitácora descargables desde el propio widget**
  (botones "Descargar reporte HTML" / "Descargar bitácora .md"): documento
  imprimible para el expediente sin necesidad de Python.
- Applet renombrado a `widget/perfil-academico-snii.html` (canónico);
  `index.html` y `standalone.html` redirigen a él.
- **Reporte unificado en el widget.** El Paso 3 ahora muestra, junto al
  análisis Cita A/B, una tabla de **producción por tipo de producto**
  (artículos arbitrados y memorias, capítulos, libros, preprints, software,
  datasets, otros) con sus citas A/B y autocitas agregadas. Integra en el
  navegador lo que antes solo producía el backend (`app/metrics/snii.py`).
- **Producción por tipo en el JSON exportado** (`production_by_type`): por
  categoría, conteo de obras, citas A/B/autocitas y lista de títulos con año
  y DOI. Documento autocontenido para el expediente SNII.
- Tema visual de **pizarrón gris tipo Keynote** con matemática de fondo a tiza
  (diagrama conmutativo, curva elíptica, superficie K3, torre p-ádica, Fermat,
  grafo dinámico funcional, función Z de Weil, ζ de Euler), distribuida y con
  rotaciones como un pizarrón real; layout de dos columnas en pantallas anchas.
- Tipografía manuscrita (Caveat + Patrick Hand), créditos al autor y enlace a
  la página personal; botón flotante de **nueva búsqueda**; **checkbox maestro**
  para seleccionar/deseleccionar todas las obras.
- Selector de **área SNII** (I–Matemáticas/Física/Astronomía/Tierra, II, III,
  sin área) con umbrales oficiales por nivel leídos de
  `config/snii_reference_params.yaml`.
- Cabecera de identidad del autor en el reporte: ORCID, OpenAlex, Semantic
  Scholar, Scopus, página web, afiliaciones, país y keywords.
- Ordenamiento de obras candidatas de **más a menos probable** con score
  ponderado por confiabilidad de fuente (ORCID > OpenAlex/SS > arXiv/Crossref)
  y etiquetas legibles (declarada en ORCID / muy probable / probable / revisar).
- CI de GitHub Actions (`.github/workflows/ci.yml`): tests en Python 3.11/3.12
  y validación de sintaxis del widget.

### Fixed
- **Cita A ya no es igual a Cita B por defecto.** El cálculo dependía de
  detectar a los coautores del trabajo en los citantes, pero esa lista nunca
  se poblaba (las obras de ORCID no la traen). Ahora se obtiene la identidad
  completa de los coautores desde OpenAlex (nombres + ORCIDs) antes de
  clasificar, tanto en el widget como en el módulo Python.
- **Regla "evaluado en citante ⇒ overlap con A(W)"** añadida en el backend
  (`_classify_citer`), en paridad con el widget: una autocita nunca se cuenta
  como Cita A aunque el nombre no matchee A(W) por variantes.
- **Normalización de nombres** ahora elimina también el apóstrofe recto ASCII
  (`'`) además de los tipográficos, agudo y grave; corrige autocitas mal
  clasificadas como Cita B cuando la fuente serializa "P'erez-Buend'ia".
- **Matching robusto por inicial+apellido** ("J. R." ↔ "J. Rogelio").
- `widget/index.html` ahora redirige a `standalone.html` (antes abría el
  widget que requería backend y fallaba con `file://`).
- `.gitignore` ignora `.DS_Store`.

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
