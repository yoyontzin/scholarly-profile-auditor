# Arquitectura

Documento técnico para mantenedores. Describe módulos, decisiones de diseño
y reglas duras.

## Diagrama de flujo

```
                ┌──────────────────────────────────────┐
                │     ENTRADA (UI o CLI)               │
                │  ORCID / Scholar URL / Nombre        │
                └───────────────┬──────────────────────┘
                                │
                ┌───────────────▼──────────────────────┐
                │  PASO 1: Identificación              │
                │  ─ OpenAlex Authors search           │
                │  ─ ORCID Search                       │
                │  ─ Semantic Scholar Author search    │
                │  → consolidación → checklist usuario  │
                └───────────────┬──────────────────────┘
                                │
                ┌───────────────▼──────────────────────┐
                │  PASO 2: Búsqueda exhaustiva obras   │
                │  ─ ORCID /works                       │
                │  ─ OpenAlex /works?author.id          │
                │  ─ Semantic Scholar /author/{id}/papers│
                │  ─ arXiv author query                 │
                │  ─ Crossref by author name            │
                │  → dedupe (DOI > arXiv > título+año)  │
                │  → score de confianza (n fuentes)     │
                │  → checklist usuario                  │
                └───────────────┬──────────────────────┘
                                │
                ┌───────────────▼──────────────────────┐
                │  PASO 3: Análisis Cita A / Cita B    │
                │  ─ Para cada obra:                    │
                │    OpenAlex /works?filter=cites:Wxx   │
                │    + Semantic Scholar /paper/.../citations │
                │  ─ Clasificar cada citante:           │
                │    A: A(C) ∩ A(W) = ∅                 │
                │    B: E ∉ A(C)                        │
                │    autocita: E ∈ A(C)                 │
                │  ─ Verificar invariante:              │
                │    A + (B-A) + autocitas = total      │
                └───────────────┬──────────────────────┘
                                │
                ┌───────────────▼──────────────────────┐
                │  SALIDAS                              │
                │  report.html · canonical_works.json   │
                │  canonical_works.bib · audit_log.md   │
                │  widget/data.json                     │
                └──────────────────────────────────────┘
```

## Módulos principales

| Módulo | Responsabilidad |
|---|---|
| `app/core/normalize.py` | Normalización de DOI, arXiv, ORCID, nombres. Manejo de apóstrofes Unicode LaTeX (U+2019). |
| `app/core/config.py` | Carga de `.env` + `config.yaml` + `snii_reference_params.yaml`. |
| `app/connectors/base.py` | `BaseConnector` con httpx async + aiolimiter (rate-limit por host) + tenacity (retries con backoff exponencial). |
| `app/connectors/orcid.py` | ORCID API v3.0 pública. |
| `app/connectors/openalex.py` | OpenAlex Authors + Works + citers, cursor pagination. |
| `app/connectors/crossref.py` | Enriquecimiento por DOI. |
| `app/connectors/datacite.py` | Para Zenodo / GitHub releases con DOI. |
| `app/connectors/arxiv.py` | Lib `arxiv` (Atom XML), wrappeada en async. |
| `app/connectors/scholar.py` | Best-effort vía `scholarly`, degrada con gracia si Scholar bloquea. |
| `app/connectors/semantic_scholar.py` | Fuente complementaria de citaciones. |
| `app/connectors/parsers/` | BibTeX (bibtexparser), RIS (rispy), CSL-JSON, CSV permisivo. |
| `app/reconciliation/dedupe.py` | Tres pasadas: DOI → arXiv → fuzzy título+año (rapidfuzz token_set_ratio ≥ 92). |
| `app/reconciliation/scoring.py` | Scoring multi-señal con pesos en `config.yaml`. Política `require_stable_id_for_confirm`. |
| `app/reconciliation/conflicts.py` | Detecta discrepancias year/title/venue entre fuentes. |
| `app/metrics/citations.py` | Métricas por fuente (no suma entre fuentes), h-index, i10-index, producción por año/tipo. |
| `app/metrics/snii_citations.py` | **Análisis Cita A / Cita B con definiciones oficiales SNII Área I.** |
| `app/metrics/coauthor.py` | Grafo de coautoría con nodos ponderados. |
| `app/services/pipeline.py` | Orquesta etapas 1–10, devuelve `PipelineResult`. |
| `app/services/exports.py` | Genera los 6 artefactos (flujo CLI completo). |
| `app/services/from_widget.py` | **Conexión widget → CLI**: convierte el JSON exportado por el widget en report.html / .bib / audit_log.md / report.json. |
| `app/api/routes.py` | FastAPI: `POST /api/audit` y servir `widget/`. |
| `app/cli.py` | Typer: `spa audit`, `spa serve`, `spa config-show`. |
| `app/main.py` | Punto de entrada FastAPI. |
| `widget/perfil-academico-snii.html` | App de 3 pasos full-browser, sin backend. |

## Reglas duras (políticas del proyecto)

Estas reglas están codificadas y no se desactivan por configuración:

1. **No emitir niveles SNII automáticos.** `automatic_level: None` se
   hard-codea en `app/metrics/snii.py` y `snii_citations.py`. Aun si el
   archivo de parámetros dice otra cosa, el código nunca lo emite.
2. **Cita A ⊆ Cita B siempre.** Verificable por inspección de la lógica
   en `_classify_citer`: `is_A = !overlap` y `overlap` incluye
   `evaluado_en_citante`, por lo que `is_auto ⇒ !is_A`. Y `is_auto ⇒ !is_B`.
3. **Identidad numérica: A + (B − A) + autocitas = total.** Probada con
   datos sintéticos en `tests/test_snii_citations.py::TestInvariante`.
4. **Si el evaluado está en el citante, está en A(W).** Porque W es un
   trabajo del evaluado. Esto evita falsos negativos cuando el matching
   por nombre de A(W) falla por variantes (e.g. "J. Rogelio" vs "J. R.").
5. **Citas por fuente no se suman entre fuentes** sin política de
   consolidación explícita. Las políticas declaradas: `report_per_source_only`
   (default) y `max_per_work` (explícitamente etiquetada como heurística).
6. **Dos DOIs distintos no se fusionan en dedupe**, excepto por la regla
   especial Zenodo (mismos título+año en DOIs `10.5281/zenodo.*`).
7. **Google Scholar nunca es fuente única autoritativa.** Confianza ≤ 0.5
   por construcción en `scholar.py`. Su ausencia no falla el pipeline.

## Manejo de credenciales

Ninguna API usada requiere autenticación:

- ORCID Public API v3.0: sin auth para registros públicos.
- OpenAlex: sin auth; pasar `mailto=` activa la "polite pool" (rate-limits más generosos).
- Crossref: idem.
- DataCite: sin auth.
- arXiv: sin auth, rate-limit conservador (1 req/s).
- Semantic Scholar: sin auth, rate-limit estricto (~1 req/s).
- Google Scholar: sin API; `scholarly` parsea HTML público y suele bloquearse.

El email para el User-Agent se configura vía `.env` (`SPA_USER_EMAIL`).
Si no se setea, las APIs siguen funcionando pero con rate-limits agresivos.

## Decisiones arquitectónicas notables

### 1. DuckDB sobre SQLite (declarado, no usado todavía)

Para análisis columnar (citas por año, joins entre fuentes), DuckDB es
sustancialmente más rápido. Está declarado en `pyproject.toml` para Fase
8 (caché persistente entre corridas). El pipeline actual mantiene todo en
memoria; suficiente para perfiles individuales.

### 2. Rate-limit por host, no global

`AsyncLimiter` por host en `BaseConnector._limiter_for()`. Los proveedores
imponen límites independientes; un limiter global desperdicia capacidad.

### 3. Cliente httpx compartido vs por-conector

Compartido (singleton de clase) para reusar pool de conexiones HTTP/2 si
está disponible. Cada conector usa el mismo `BaseConnector._client`.

### 4. Reintentos con backoff

`tenacity` con `wait_exponential` ataca 5xx y `httpx.TransportError`.
Distinción `RetryableError` vs `FatalError`. Respeta `Retry-After` si lo
recibe.

### 5. Widget sin backend

`widget/perfil-academico-snii.html` corre sin servidor llamando a APIs públicas
directamente vía CORS. Esto:

- Elimina la fricción de instalación para el usuario final.
- Embebe trivialmente en una página académica personal.
- Confina los costos de cómputo (rate-limits) al navegador del usuario.

El backend FastAPI sigue existiendo (`spa serve`) para casos donde la
auditoría se quiere ejecutar server-side o cuando se quiere persistir
resultados en una base local.

### 6. Tres pasos con human-in-the-loop

La identificación robusta de autor en bibliometría no es resoluble
automáticamente con alta precisión, especialmente para nombres comunes
o autores con afiliaciones múltiples. El flujo de checklist en cada paso
respeta este límite y delega las decisiones críticas al humano,
documentándolas en el JSON exportable.

## Tests

```bash
PYTHONPATH=. pytest -q
```

- `tests/test_normalize.py` — 15 tests de normalización (incluye fix Unicode).
- `tests/test_dedupe.py` — 8 tests de deduplicación.
- `tests/test_scoring.py` — 5 tests de scoring de autoría.
- `tests/test_connectors.py` — 3 tests de conectores con respx mock.
- `tests/test_parsers.py` — 4 tests de parsers.
- `tests/test_metrics.py` — 9 tests de métricas y SNII.
- `tests/test_snii_citations.py` — 10+ tests de Cita A / Cita B (definiciones
  oficiales, invariantes, casos edge Unicode).

Total ≥ 54 tests, todos verdes en CI estándar.

## Estructura de archivos

```
scholarly-profile-auditor/
├── app/
│   ├── api/                FastAPI routes
│   ├── connectors/         Conectores HTTP + parsers
│   │   └── parsers/
│   ├── core/               Config, logging, normalize
│   ├── metrics/            citations, coauthor, snii, snii_citations
│   ├── models/             Pydantic models
│   ├── reconciliation/     dedupe, scoring, conflicts
│   ├── services/           pipeline, exports
│   ├── templates/          Jinja2 (report.html.j2)
│   ├── cli.py
│   └── main.py
├── config/
│   ├── config.yaml
│   └── snii_reference_params.yaml
├── docs/
│   ├── USAGE.md
│   └── ARCHITECTURE.md (este archivo)
├── examples/
│   ├── sample_run.md
│   └── synthetic_demo.py
├── scripts/
│   ├── run_rpb.sh
│   ├── run_server.sh
│   └── run_demo.sh
├── tests/                  pytest suite
├── widget/
│   ├── index.html          (con backend FastAPI)
│   ├── perfil-academico-snii.html     (sin backend, 3 pasos)
│   └── app.js
├── .env.example
├── .gitignore
├── .zenodo.json
├── CHANGELOG.md
├── CITATION.cff
├── LICENSE
├── pyproject.toml
├── README.md
├── requirements.txt
└── SKILL.md
```
