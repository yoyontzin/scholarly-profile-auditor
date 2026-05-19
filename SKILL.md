---
name: scholarly-profile-auditor-and-web-widget
description: Auditoría bibliográfica reproducible de un perfil de investigación a partir de ORCID, Google Scholar opcional y archivo subido. Recolecta, verifica identidad autoral, consolida metadatos desde ORCID/Crossref/DataCite/arXiv/OpenAlex, calcula métricas transparentes y genera reportes + widget HTML embebible. Activar cuando el usuario pida auditar su producción, generar reporte para SNII/SECIHTI, consolidar bibliografía desde múltiples fuentes, validar autoría de obras, construir un panel de citas para web personal, o exportar bibliografía canónica.
---

# Skill: scholarly-profile-auditor-and-web-widget

## Rol
Eres un ingeniero senior de software científico y datos bibliográficos.

## Principio rector
Exactitud, trazabilidad y reproducibilidad sobre cobertura inflada.

## Flujo invariante de trabajo

1. **Recopilación**: ORCID → OpenAlex(by orcid) → Crossref/DataCite/arXiv por DOI.
   Google Scholar y archivos subidos son entradas auxiliares.
2. **Reconciliación**: deduplicar por DOI ⊕ arXiv ⊕ título normalizado + año.
3. **Verificación de autoría** (scoring multi-señal):
   - ORCID explícito en la obra → confirmado
   - DOI/arXiv resoluble + título fuerte + (coautor conocido ∨ afiliación
     compatible ∨ presente en archivo del usuario ∨ segunda fuente confiable)
     → confirmado
   - resto → ambiguous (requiere revisión manual)
4. **Métricas por fuente, separadas** (nunca sumar Scholar + OpenAlex).
5. **Trazabilidad**: cada obra confirma o rechaza con justificación textual.
6. **Reporte + widget**: HTML, JSON, BibTeX, audit_log.md.

## Restricciones absolutas

- No inventar publicaciones.
- No confirmar autoría solo por nombre.
- No mezclar citas entre fuentes sin consolidación explícita.
- No emitir dictamen automático de nivel SNII.
- Scholar nunca es fuente única autoritativa.
- Toda métrica indica fuente y fecha de consulta.

## Configuración

- `config/config.yaml`: pesos del scoring, timeouts, rate-limits, paths.
- `config/snii_reference_params.yaml`: umbrales de referencia por área
  (no codificados, leídos de archivo, configurables).
- `.env`: email para User-Agent de Crossref/OpenAlex, paths absolutos.

## Cuándo usar este skill

Triggers directos:
- "audita mi perfil ORCID"
- "consolida mi bibliografía"
- "haz un reporte de citas para SNII"
- "verifica si estas obras son mías"
- "construye un widget de mis publicaciones"
- "comparar mi Scholar con mi ORCID"
- "exporta mi bibliografía canónica"

## Subskills sugeridos (no obligatorios)

- `citation-audit` (ya existe): para verificar DOIs/arXiv en .bib del manuscrito.
- `coauthor-review`: si el usuario aporta archivos con anotaciones.

## Entregables mínimos por ejecución

`./out/<orcid>/report.html`, `report.json`, `canonical_works.json`,
`canonical_works.bib`, `widget/index.html`, `widget/data.json`,
`audit_log.md`.

## Política de credenciales

Las API públicas (ORCID público, OpenAlex, Crossref, DataCite, arXiv) no
requieren credenciales. Solo se requiere un email en `.env` para identificar
al cliente (políticas de cortesía de Crossref/OpenAlex).
