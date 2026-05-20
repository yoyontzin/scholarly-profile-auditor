"""Conexión widget → CLI.

El widget HTML (perfil-academico-snii.html) hace el análisis con
human-in-the-loop (identificación, confirmación de obras, Cita A/B) y exporta
un JSON. Este módulo consume ESE JSON y regenera los artefactos formales del
backend (report.html, canonical_works.bib, audit_log.md, report.json), sin
re-ejecutar el análisis. Así una sola corrida del widget alimenta el documento
de respaldo para el expediente.

Formato de entrada esperado (lo que produce el botón "Descargar JSON" del widget):
{
  "author": {orcid, display_name, given_names, family_names, scholar_url,
             openalex_id, external_ids[], researcher_urls[], affiliations[],
             country, keywords[]},
  "works": [{title, year, doi, type, category, work_authors[],
             total, cita_A, cita_B, autocita, B_minus_A,
             detalle:[{title, year, authors[], tipo}]}],
  "totals": {A, B, auto, BmA, total},
  "production_by_type": {<cat>: {label, obras, cita_A, cita_B, autocitas, titulos[]}},
  "snii_area": {id, label, thresholds:{nivel_ii, nivel_iii, h_ii, h_iii, count_basis}, note, source},
  "generated_at": "..."
}
"""

from __future__ import annotations

import html as _html
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def _esc(s: Any) -> str:
    return _html.escape(str(s if s is not None else ""))


def _full_name(author: dict) -> str:
    g, f = author.get("given_names"), author.get("family_names")
    if g and f:
        return f"{g} {f}"
    return author.get("display_name") or author.get("orcid") or "—"


# ---------------------------------------------------------------------------
# report.html
# ---------------------------------------------------------------------------
def render_report_html(data: dict) -> str:
    author = data.get("author", {})
    name = _full_name(author)
    totals = data.get("totals", {})
    A = totals.get("A", 0); B = totals.get("B", 0)
    BmA = totals.get("BmA", 0); auto = totals.get("auto", 0)
    works = data.get("works", [])
    area = data.get("snii_area", {})
    fecha = datetime.utcnow().isoformat() + "Z"

    id_rows = []
    if author.get("orcid"):
        id_rows.append(f'<tr><th>ORCID</th><td><a href="https://orcid.org/{_esc(author["orcid"])}">https://orcid.org/{_esc(author["orcid"])}</a></td></tr>')
    if author.get("scholar_url"):
        id_rows.append(f'<tr><th>Google Scholar</th><td><a href="{_esc(author["scholar_url"])}">{_esc(author["scholar_url"])}</a></td></tr>')
    if author.get("openalex_id"):
        id_rows.append(f'<tr><th>OpenAlex</th><td>openalex.org/{_esc(author["openalex_id"])}</td></tr>')
    for e in author.get("external_ids", []) or []:
        id_rows.append(f'<tr><th>{_esc(e.get("type"))}</th><td>{_esc(e.get("value"))}</td></tr>')
    for u in author.get("researcher_urls", []) or []:
        if "scholar.google." not in (u.get("url") or ""):
            id_rows.append(f'<tr><th>{_esc(u.get("name") or "Web")}</th><td><a href="{_esc(u.get("url"))}">{_esc(u.get("url"))}</a></td></tr>')
    if author.get("affiliations"):
        id_rows.append(f'<tr><th>Afiliaciones</th><td>{"<br>".join(_esc(x) for x in author["affiliations"][:5])}</td></tr>')
    if author.get("country"):
        id_rows.append(f'<tr><th>País</th><td>{_esc(author["country"])}</td></tr>')
    if author.get("keywords"):
        id_rows.append(f'<tr><th>Áreas</th><td>{" · ".join(_esc(x) for x in author["keywords"])}</td></tr>')

    prod_rows = ""
    for info in (data.get("production_by_type", {}) or {}).values():
        prod_rows += (f'<tr><td>{_esc(info.get("label"))}</td><td>{info.get("obras",0)}</td>'
                      f'<td>{info.get("cita_A",0)}</td><td>{info.get("cita_B",0)}</td>'
                      f'<td>{info.get("autocitas",0)}</td></tr>')
    prod_rows += f'<tr class="tot"><td>TOTAL</td><td>{len(works)}</td><td>{A}</td><td>{B}</td><td>{auto}</td></tr>'

    umbral_html = ""
    th = area.get("thresholds", {}) if area else {}
    if th and (th.get("nivel_ii") is not None or th.get("nivel_iii") is not None):
        def cmp(v, t):
            if t is None:
                return "—"
            return f"{v} ✓ cumple" if v >= t else f"{v} ✗ faltan {t - v}"
        umbral_html = (
            f'<h2>Umbrales SNII — {_esc(area.get("label",""))}</h2>'
            '<table><thead><tr><th>Nivel</th><th>Requisito</th><th>Por Cita A</th><th>Por Cita B</th></tr></thead><tbody>'
            f'<tr><td>Nivel II</td><td>{"≥ "+str(th["nivel_ii"]) if th.get("nivel_ii") is not None else "—"}</td><td>{cmp(A, th.get("nivel_ii"))}</td><td>{cmp(B, th.get("nivel_ii"))}</td></tr>'
            f'<tr><td>Nivel III</td><td>{"≥ "+str(th["nivel_iii"]) if th.get("nivel_iii") is not None else "—"}</td><td>{cmp(A, th.get("nivel_iii"))}</td><td>{cmp(B, th.get("nivel_iii"))}</td></tr>'
            f'</tbody></table><p class="note">{_esc(area.get("note",""))}</p>'
        )

    detalle_html = ""
    for w in sorted(works, key=lambda x: -(x.get("year") or 0)):
        det = w.get("detalle") or []
        if det:
            lis = "".join(
                f'<li>[{d.get("year") or "?"}] <em>{_esc(d.get("title"))}</em> — '
                f'{_esc(", ".join(d.get("authors", [])))} → <strong>{_esc(d.get("tipo"))}</strong></li>'
                for d in det
            )
            citas = f"<ul>{lis}</ul>"
        else:
            citas = '<p class="note">— sin citas indexadas en OpenAlex ni Semantic Scholar —</p>'
        detalle_html += (
            f'<div class="obra"><h3>[{w.get("year") or "?"}] {_esc(w.get("title"))}</h3>'
            f'<p class="note">{("DOI: "+_esc(w["doi"])+" · ") if w.get("doi") else ""}'
            f'tipo: {_esc(w.get("type") or "—")} · A={w.get("cita_A",0)} B={w.get("cita_B",0)} '
            f'autocitas={w.get("autocita",0)}</p>{citas}</div>'
        )

    return f"""<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<title>Reporte de citas SNII — {_esc(name)}</title>
<style>
  body{{font-family:Georgia,'Times New Roman',serif;color:#1a1a1a;max-width:900px;margin:2rem auto;padding:0 1.5rem;line-height:1.5}}
  h1{{font-size:1.6rem;border-bottom:3px double #333;padding-bottom:.3rem}}
  h2{{font-size:1.25rem;color:#2c3e50;border-bottom:1px solid #ccc;margin-top:2rem}}
  h3{{font-size:1.05rem;margin:.8rem 0 .2rem}}
  table{{width:100%;border-collapse:collapse;margin:.8rem 0;font-size:.95em}}
  th,td{{border:1px solid #bbb;padding:.35rem .6rem;text-align:left}}
  thead th{{background:#eee}} tr.tot{{font-weight:bold;background:#f5f5f5}}
  .note{{color:#666;font-size:.88em}} .obra{{margin:.6rem 0;padding:.4rem .8rem;border-left:3px solid #ccc}}
  .disc{{background:#f8f4e8;border-left:4px solid #c8861d;padding:.6rem 1rem;margin:1rem 0;font-size:.92em}}
  ul{{margin:.3rem 0 .6rem 1.2rem}} footer{{margin-top:2rem;border-top:1px solid #ccc;padding-top:.6rem;color:#666;font-size:.85em}}
  @media print{{body{{margin:0}}}}
</style></head><body>
<h1>Reporte de citas SNII — Cita A / Cita B</h1>
<p><strong>{_esc(name)}</strong><br>Generado: {_esc(fecha)} · vía widget → CLI</p>
<h2>Identidad del investigador</h2><table>{"".join(id_rows)}</table>
<h2>Producción por tipo de producto</h2>
<table><thead><tr><th>Tipo</th><th>Obras</th><th>Cita A</th><th>Cita B</th><th>Autocitas</th></tr></thead><tbody>{prod_rows}</tbody></table>
<h2>Resumen de citas</h2>
<table><tbody>
<tr><th>Cita A (estrictamente externa)</th><td>{A}</td></tr>
<tr><th>Cita B (sin el evaluado)</th><td>{B}</td></tr>
<tr><th>Citas por coautor histórico (B − A)</th><td>{BmA}</td></tr>
<tr><th>Autocitas estrictas</th><td>{auto}</td></tr>
</tbody></table>
{umbral_html}
<h2>Definiciones oficiales (SECIHTI)</h2>
<p><strong>Cita A:</strong> el citante no incluye a ningún autor del trabajo citado.
<strong>Cita B:</strong> el citante no incluye al investigador evaluado.
Invariante: Cita A + (B−A) + autocitas = total.</p>
<h2>Detalle por obra</h2>{detalle_html}
<div class="disc"><strong>Aviso.</strong> No emite dictamen automático de nivel SNII;
es documentación. El conteo proviene de fuentes abiertas con cobertura parcial en
matemáticas. La evaluación cualitativa compete al comité.</div>
<footer>Scholarly Profile Auditor · generado desde el JSON del widget.</footer>
</body></html>"""


# ---------------------------------------------------------------------------
# canonical_works.bib
# ---------------------------------------------------------------------------
_BIB_TYPE = {
    "arbitrados": "article", "capitulos": "incollection", "libros": "book",
    "preprints": "unpublished", "software": "misc", "datasets": "misc", "otros": "misc",
}


def render_bibtex(data: dict) -> str:
    author = data.get("author", {})
    lines = [
        f"% Bibliografía generada desde el widget Perfil Académico SNII",
        f"% Autor: {_full_name(author)}  ORCID: {author.get('orcid','—')}",
        f"% Generado: {datetime.utcnow().isoformat()}Z",
        "",
    ]
    used: set[str] = set()
    for i, w in enumerate(data.get("works", [])):
        cat = w.get("category", "otros")
        btype = _BIB_TYPE.get(cat, "misc")
        first = (w.get("work_authors") or ["anon"])[0].split()[-1].lower()
        first = "".join(c for c in first if c.isalpha()) or "anon"
        key = f"{first}{w.get('year','nd')}{i}"
        while key in used:
            key += "x"
        used.add(key)
        fields = [f"  title = {{{(w.get('title') or '').replace('{','').replace('}','')}}}"]
        if w.get("work_authors"):
            fields.append(f"  author = {{{' and '.join(w['work_authors'])}}}")
        if w.get("year"):
            fields.append(f"  year = {{{w['year']}}}")
        if w.get("doi"):
            fields.append(f"  doi = {{{w['doi']}}}")
        fields.append(f"  note = {{Cita A={w.get('cita_A',0)}, Cita B={w.get('cita_B',0)}, autocitas={w.get('autocita',0)}}}")
        lines.append(f"@{btype}{{{key},\n" + ",\n".join(fields) + "\n}\n")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# audit_log.md
# ---------------------------------------------------------------------------
def render_audit_log(data: dict) -> str:
    author = data.get("author", {})
    t = data.get("totals", {})
    L = [
        f"# Bitácora de auditoría de citas — {author.get('display_name','')}",
        f"ORCID: {author.get('orcid','—')} · generado: {datetime.utcnow().isoformat()}Z",
        "", "## Resumen",
        f"- Cita A: {t.get('A',0)}", f"- Cita B: {t.get('B',0)}",
        f"- B − A: {t.get('BmA',0)}", f"- Autocitas: {t.get('auto',0)}",
        f"- Obras analizadas: {len(data.get('works',[]))}", "",
        "## Decisión por obra", "",
    ]
    for w in sorted(data.get("works", []), key=lambda x: -(x.get("year") or 0)):
        L.append(f"### [{w.get('year') or '?'}] {w.get('title','')}")
        L.append(f"- DOI: `{w.get('doi') or '—'}` · tipo: {w.get('type') or '—'} · "
                 f"A={w.get('cita_A',0)} B={w.get('cita_B',0)} autocitas={w.get('autocita',0)}")
        for d in (w.get("detalle") or []):
            L.append(f"  - [{d.get('year') or '?'}] {d.get('title','')} — "
                     f"{', '.join(d.get('authors', []))} → **{d.get('tipo')}**")
        if not (w.get("detalle") or []):
            L.append("  - (sin citas indexadas)")
        L.append("")
    L.append("---")
    L.append("Cita A = A(C) ∩ A(W) = ∅. Cita B = E ∉ A(C). Definiciones SNII Área I.")
    return "\n".join(L)


# ---------------------------------------------------------------------------
# Orquestador
# ---------------------------------------------------------------------------
def generate_from_widget_json(json_path: str | Path, out_dir: str | Path) -> dict[str, Path]:
    """Lee el JSON del widget y genera report.html, canonical_works.bib,
    audit_log.md y una copia normalizada report.json. Devuelve los paths."""
    json_path = Path(json_path)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data = json.loads(json_path.read_text(encoding="utf-8"))

    outputs = {
        "report.html": render_report_html(data),
        "canonical_works.bib": render_bibtex(data),
        "audit_log.md": render_audit_log(data),
        "report.json": json.dumps(data, indent=2, ensure_ascii=False),
    }
    paths: dict[str, Path] = {}
    for name, content in outputs.items():
        p = out_dir / name
        p.write_text(content, encoding="utf-8")
        paths[name] = p
    return paths
