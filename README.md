# Scholarly Profile Auditor

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-54%2B%20passing-brightgreen.svg)](tests/)

Auditoría bibliográfica reproducible con flujo guiado en tres pasos.
Clasifica citas como **Cita A** (estrictamente externa) y **Cita B**
(excluye solo autocitas del evaluado), según las definiciones oficiales
del SNII (México), Área I — Físico-Matemáticas.

> **Principio rector**: exactitud, trazabilidad y reproducibilidad sobre
> cobertura inflada. No se infieren publicaciones, no se confirma autoría
> sin evidencia, no se consolidan citas ciegamente entre fuentes.
> **No emite niveles SNII automáticos.**

## Flujo de tres pasos

```
1. IDENTIFICACIÓN            2. OBRAS DEL AUTOR           3. CITAS A/B
   ORCID                       ORCID works                  OpenAlex citers
   Scholar URL          →      OpenAlex             →       Semantic Scholar
   Nombre + búsqueda           Semantic Scholar             Clasificación A/B
   Checklist usuario           arXiv                        Umbrales SNII
                               Crossref
                               Checklist usuario
```

## Dos formas de usarlo

### A) Widget en el navegador (sin instalación)

Abre [`widget/perfil-academico-snii.html`](widget/perfil-academico-snii.html) en cualquier navegador moderno. Funciona enteramente client-side llamando a APIs públicas vía CORS. Embebible en tu página académica:

```html
<iframe src="perfil-academico-snii.html?orcid=0000-0002-XXXX-XXXX"
        width="100%" height="1200" style="border:none"></iframe>
```

### B) CLI Python (reproducible, automatizable)

```bash
git clone https://github.com/yoyontzin/scholarly-profile-auditor.git
cd scholarly-profile-auditor
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env       # editar con tu email
spa audit --orcid 0000-0002-XXXX-XXXX --out ./out
open out/0000-0002-XXXX-XXXX/report.html
```

## Definiciones oficiales SNII implementadas

Para Área I — Físico-Matemáticas, [documento oficial SECIHTI](https://portal.amelica.org/ameli/static/media/observatorio/Criterios%20Area%20I-FF.pdf):

| Tipo | Definición textual | Fórmula |
|---|---|---|
| **Cita A** | "Realizadas en productos firmados por autores, entre los cuales no se encuentra ninguno que sea autor del trabajo… Excluye autocitas de todos los autores." | $A(C) \cap A(W) = \emptyset$ |
| **Cita B** | "Pueden incluir uno o varios autores del trabajo citado, pero no el investigador evaluado. Excluye únicamente las autocitas del autor seleccionado." | $E \notin A(C)$ |
| **Autocita estricta** | (caso complementario) | $E \in A(C)$ |

**Invariante**: Cita A + (B − A) + autocitas = total de citantes. Verificada
programáticamente.

**Umbrales SNII Matemáticas**: Nivel II ≥ 20 citas, Nivel III ≥ 40 citas.

## Fuentes integradas

| Fuente | Búsqueda autor | Obras | Citantes | Notas |
|---|---|---|---|---|
| ORCID Public API | ✓ | ✓ | — | Autoritativo para identidad. |
| OpenAlex | ✓ | ✓ | ✓ | API gratuita, sin auth. |
| Semantic Scholar | ✓ | ✓ | ✓ | Complementa OpenAlex; cobertura distinta. |
| Crossref | — | ✓ (por nombre) | conteo | Enriquecimiento de metadata. |
| DataCite | — | ✓ (Zenodo) | — | Clasificación correcta de software/datasets. |
| arXiv | — | ✓ (por nombre) | — | Atom XML query. |
| Google Scholar | (deshabilitado en widget — bloquea CORS) | ✓ (CLI best-effort) | — | Frecuentemente bloqueado. |

## Documentación

- [USAGE.md](docs/USAGE.md) — guía detallada de uso, las 3 opciones.
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — módulos, decisiones técnicas, reglas duras.
- [CHANGELOG.md](CHANGELOG.md) — historial de versiones.
- [CITATION.cff](CITATION.cff) — cómo citar este software.

## Tests

```bash
PYTHONPATH=. pytest -q
```

Cobertura: normalización, deduplicación, scoring, parsers, métricas,
**clasificación Cita A/B con casos sintéticos exhaustivos** (incluye edge
cases Unicode LaTeX y la regla "evaluado en citante ⇒ overlap").

## Licencia y citación

MIT. Si lo usas en investigación, cita usando [CITATION.cff](CITATION.cff):

> Pérez-Buendía, R. (2026). *Scholarly Profile Auditor: bibliographic audit
> with SNII Cita A/B classification* (Version 0.4.1) [Software]. Zenodo.
> https://doi.org/10.5281/zenodo.22684475

DOI conceptual (siempre apunta a la última versión):
`10.5281/zenodo.22684475`.  DOI de la versión actual v0.4.1:
`10.5281/zenodo.22684476`.

## Limitaciones honestas

1. **Cobertura de citas en matemáticas es limitada en fuentes abiertas.**
   MathSciNet y zbMATH son cerradas y no están integradas; OpenAlex y
   Semantic Scholar sub-reportan. Para Google Scholar, el widget browser
   no puede consultarlo por CORS; el CLI lo intenta best-effort.
2. **No emite niveles SNII automáticos.** Política dura del proyecto.
3. **Releases múltiples de Zenodo** del mismo trabajo se fusionan por
   título+año (concesión documentada sobre la regla "dos DOIs nunca se
   fusionan").

## Contribuciones

Issues y pull requests son bienvenidos. Para discusiones sobre
interpretación de criterios SNII, abre un issue con etiqueta `policy`.
