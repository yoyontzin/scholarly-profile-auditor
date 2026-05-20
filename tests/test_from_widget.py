"""Tests de la conexión widget → CLI (app.services.from_widget)."""

import json

from app.services.from_widget import (
    generate_from_widget_json,
    render_audit_log,
    render_bibtex,
    render_report_html,
)

WIDGET_JSON = {
    "author": {
        "orcid": "0000-0002-7739-4779",
        "display_name": "J. R. Pérez-Buendía",
        "given_names": "Jesús Rogelio",
        "family_names": "Pérez-Buendía",
        "openalex_id": "A5089579526",
        "external_ids": [{"type": "Scopus Author ID", "value": "57204980058"}],
        "affiliations": ["CIMAT"],
        "country": "MX",
        "keywords": ["p-adic Hodge Theory"],
    },
    "works": [
        {"title": "K3-surfaces", "year": 2019, "doi": "10.1/a",
         "type": "journal-article", "category": "arbitrados",
         "work_authors": ["J. Rogelio Pérez-Buendía"],
         "total": 0, "cita_A": 0, "cita_B": 0, "autocita": 0, "B_minus_A": 0, "detalle": []},
        {"title": "Coral growth", "year": 2026, "doi": "10.1/b",
         "type": "journal-article", "category": "arbitrados",
         "work_authors": ["A. Fuquen-Tibata", "J. R. Pérez-Buendía"],
         "total": 2, "cita_A": 1, "cita_B": 1, "autocita": 1, "B_minus_A": 0,
         "detalle": [
             {"title": "Spectral Geometry", "year": 2026, "authors": ["Á. Morán"], "tipo": "Cita A"},
             {"title": "Hierarchical p-Adic", "year": 2026, "authors": ["J. R. Pérez-Buendía"], "tipo": "AUTOCITA"},
         ]},
    ],
    "totals": {"A": 1, "B": 1, "auto": 1, "BmA": 0, "total": 2},
    "production_by_type": {
        "arbitrados": {"label": "Artículos arbitrados y memorias", "obras": 2,
                       "cita_A": 1, "cita_B": 1, "autocitas": 1, "titulos": []},
    },
    "snii_area": {"id": "area1_matematicas", "label": "Área I — Matemáticas",
                  "thresholds": {"nivel_ii": 20, "nivel_iii": 40, "count_basis": "A"},
                  "note": "Matemáticas."},
    "generated_at": "2026-05-20",
}


class TestRenderReportHtml:
    def test_incluye_autor_y_orcid(self):
        h = render_report_html(WIDGET_JSON)
        assert "Pérez-Buendía" in h
        assert "0000-0002-7739-4779" in h

    def test_incluye_produccion_por_tipo(self):
        h = render_report_html(WIDGET_JSON)
        assert "Artículos arbitrados y memorias" in h

    def test_incluye_umbrales_del_area(self):
        h = render_report_html(WIDGET_JSON)
        assert "≥ 20" in h and "Nivel III" in h

    def test_clasifica_detalle_de_citas(self):
        h = render_report_html(WIDGET_JSON)
        assert "Cita A" in h and "AUTOCITA" in h

    def test_no_emite_nivel_automatico(self):
        h = render_report_html(WIDGET_JSON)
        assert "NO emite dictamen" in h or "No emite dictamen" in h


class TestRenderBibtex:
    def test_genera_entradas(self):
        bib = render_bibtex(WIDGET_JSON)
        assert bib.count("@") >= 2          # dos obras
        assert "doi = {10.1/a}" in bib
        assert "Cita A=1" in bib            # nota con conteo


class TestRenderAuditLog:
    def test_resumen_y_decisiones(self):
        md = render_audit_log(WIDGET_JSON)
        assert "Cita A: 1" in md
        assert "AUTOCITA" in md
        assert "Coral growth" in md


class TestGenerateFromWidgetJson:
    def test_genera_los_cuatro_artefactos(self, tmp_path):
        jf = tmp_path / "widget.json"
        jf.write_text(json.dumps(WIDGET_JSON), encoding="utf-8")
        out = generate_from_widget_json(jf, tmp_path / "out")
        assert set(out.keys()) == {"report.html", "canonical_works.bib", "audit_log.md", "report.json"}
        for p in out.values():
            assert p.exists() and p.stat().st_size > 0
        # report.json es JSON válido y conserva los totales
        data = json.loads(out["report.json"].read_text())
        assert data["totals"]["A"] == 1
