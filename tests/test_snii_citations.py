"""Tests exhaustivos del análisis Cita A / Cita B.

Verifican literalmente las definiciones oficiales SNII Área I:
  Cita A ⇔ A(C) ∩ A(W) = ∅
  Cita B ⇔ E ∉ A(C)
  Autocita ⇔ E ∈ A(C)
  Invariante: A + (B-A) + autocitas = total
"""

from app.core.normalize import normalize_person_name
from app.metrics.snii_citations import (
    SNII_MATH_THRESHOLDS,
    WorkCitationAnalysis,
    _classify_citer,
    aggregate_global,
)


# Variantes del autor evaluado: comparten persona real distinta serialización.
EVALUADO_VARIANTS = {
    normalize_person_name(v) for v in [
        "Rogelio Pérez-Buendía",
        "J. R. Pérez-Buendía",
        "Jesús Rogelio Pérez Buendía",
        "Rogelio Yoyontzin",
        "P'erez-Buend'ia",        # serialización LaTeX de Semantic Scholar
    ]
}


def _citer(*author_names_with_optional_orcid):
    """Construye un dict citante estilo OpenAlex con authorships."""
    authorships = []
    for entry in author_names_with_optional_orcid:
        if isinstance(entry, tuple):
            name, orcid = entry
            au = {"display_name": name, "orcid": f"https://orcid.org/{orcid}"}
        else:
            au = {"display_name": entry}
        authorships.append({"author": au})
    return {"authorships": authorships}


# ---------------------------------------------------------------------------
# Casos canónicos del documento SNII
# ---------------------------------------------------------------------------
class TestCitaA:
    """Cita A = A(C) ∩ A(W) = ∅. Ningún autor del trabajo aparece en el citante."""

    def test_citante_totalmente_externo_es_A(self):
        work_authors = {normalize_person_name("Rogelio Pérez-Buendía")}
        cit = _citer("John Smith", "Jane Doe")
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_A is True
        assert is_B is True
        assert is_auto is False

    def test_citante_con_coautor_no_es_A_pero_si_B(self):
        """Coautor histórico cita el paper, pero Rogelio NO firma → no es A, sí es B."""
        work_authors = {
            normalize_person_name("Rogelio Pérez-Buendía"),
            normalize_person_name("Yuriria Cortés-Poza"),
        }
        cit = _citer("Yuriria Cortés-Poza", "Stranger McStrangerson")
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_A is False     # Cortés-Poza aparece en A(W)
        assert is_B is True      # Rogelio NO firma el citante
        assert is_auto is False

    def test_autocita_implica_no_A_aunque_overlap_falle_por_nombre(self):
        """
        Caso real detectado: W tiene 'J. Rogelio Pérez-Buendía' y el citante
        trae 'J. R. Pérez-Buendía'. El matching exacto por A(W) falla, pero
        E ∈ A(C) ⇒ E ∈ A(W) trivialmente (porque W es trabajo de E).
        """
        work_authors = {normalize_person_name("J. Rogelio Pérez-Buendía")}
        cit = _citer("J. R. Pérez-Buendía", "Víctor Nopal-Coello")
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_auto is True
        assert is_A is False     # ← regla "evaluado en citante ⇒ overlap"
        assert is_B is False     # autocita

    def test_apostrofes_unicode_latex_no_rompen_match(self):
        """Semantic Scholar serializa 'á' como apóstrofe + a en algunos nombres."""
        work_authors = {normalize_person_name("Pérez-Buendía")}
        # Apóstrofe U+2019 entre P y erez
        cit = _citer("J. R. P’erez-Buend’ia")
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_auto is True

    def test_orcid_match_aunque_nombre_no(self):
        """Si OpenAlex expone ORCID del citante, debe matchear aunque el nombre venga raro."""
        work_authors = {normalize_person_name("Pérez-Buendía")}
        cit = _citer(("R. P. Buendía", "0000-0002-7739-4779"))   # nombre raro + ORCID correcto
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_auto is True
        assert is_A is False


class TestCitaB:
    """Cita B = E ∉ A(C). El investigador evaluado no firma el citante."""

    def test_E_no_firma_es_B(self):
        work_authors = {normalize_person_name("Pérez-Buendía"), normalize_person_name("Cortés-Poza")}
        cit = _citer("Some External Researcher", "Cortés-Poza")
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_B is True
        assert is_A is False    # overlap por Cortés-Poza
        assert is_auto is False

    def test_E_firma_no_es_B(self):
        work_authors = {normalize_person_name("Pérez-Buendía")}
        cit = _citer("Rogelio Pérez-Buendía", "Stranger")
        is_A, is_B, is_auto, _ = _classify_citer(
            cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
        )
        assert is_B is False
        assert is_auto is True


class TestInvariante:
    """Invariante numérica: A + (B-A) + autocitas = total para cualquier dataset."""

    def test_identidad_numerica(self):
        # Dataset sintético: 10 citantes mezclados
        work_authors = {normalize_person_name("Pérez-Buendía"), normalize_person_name("Nopal-Coello")}
        casos = [
            ("Externo 1", "Externo 2"),                         # A, B
            ("Externo 3",),                                     # A, B
            ("Pérez-Buendía",),                                 # autocita
            ("Pérez-Buendía", "Externo 4"),                     # autocita
            ("Nopal-Coello", "Externo 5"),                      # B-A
            ("Nopal-Coello",),                                  # B-A
            ("Externo 6", "Externo 7", "Externo 8"),            # A, B
            ("Rogelio Pérez-Buendía", "Nopal-Coello"),          # autocita
            ("Externo 9",),                                     # A, B
            ("Externo 10",),                                    # A, B
        ]
        total = len(casos)
        cita_A = cita_B = autocita = 0
        for autores in casos:
            cit = _citer(*autores)
            is_A, is_B, is_auto, _ = _classify_citer(
                cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
            )
            if is_A: cita_A += 1
            if is_B: cita_B += 1
            if is_auto: autocita += 1
        # Por construcción esperamos:
        #   A = 5 (filas 1,2,7,9,10)
        #   B = 7 (filas 1,2,5,6,7,9,10)
        #   autocita = 3 (filas 3,4,8)
        #   B - A = 2 (filas 5,6)
        assert cita_A == 5
        assert cita_B == 7
        assert autocita == 3
        assert cita_A + (cita_B - cita_A) + autocita == total
        assert cita_A + autocita + (cita_B - cita_A) == 10

    def test_invariante_subset_relation(self):
        """A ⊆ B siempre. Probado: para cualquier citante, is_A ⇒ is_B."""
        work_authors = {normalize_person_name("Pérez-Buendía")}
        for case in [
            ("X",), ("Y", "Z"), ("Pérez-Buendía",), ("Pérez-Buendía", "X"),
            ("Cortés-Poza",), ("Cortés-Poza", "X"),
        ]:
            cit = _citer(*case)
            is_A, is_B, is_auto, _ = _classify_citer(
                cit, work_authors, "0000-0002-7739-4779", EVALUADO_VARIANTS
            )
            if is_A:
                assert is_B, f"Violación A⊆B en caso {case}"


class TestAggregateGlobal:
    """aggregate_global agrega correctamente sobre múltiples obras."""

    def test_suma_correcta(self):
        per_work = [
            WorkCitationAnalysis(
                work_internal_id="w1", title="W1", year=2020, doi="10.1/a",
                openalex_id="W1", work_authors=["Pérez-Buendía"],
                total_citers=5, cita_A=3, cita_B=4, autocita_estricta=1,
                cita_por_coautor_historico=1,
                top_external_citers_A={"X": 2, "Y": 1},
            ),
            WorkCitationAnalysis(
                work_internal_id="w2", title="W2", year=2021, doi="10.1/b",
                openalex_id="W2", work_authors=["Pérez-Buendía"],
                total_citers=3, cita_A=2, cita_B=3, autocita_estricta=0,
                cita_por_coautor_historico=1,
                top_external_citers_A={"Z": 2},
            ),
        ]
        g = aggregate_global(per_work)
        assert g.total_cita_A == 5
        assert g.total_cita_B == 7
        assert g.total_autocita_estricta == 1
        assert g.total_cita_coautor_historico == 2
        assert g.autores_citantes_distintos_A_global == 3  # X, Y, Z
        assert g.works_with_citations == 2

    def test_umbrales_snii_no_se_emite_nivel_automatico(self):
        """Política dura del proyecto."""
        per_work = [
            WorkCitationAnalysis(
                work_internal_id="w", title="t", year=2024, doi=None,
                openalex_id=None, work_authors=[],
                total_citers=50, cita_A=50, cita_B=50,
                autocita_estricta=0, cita_por_coautor_historico=0,
            )
        ]
        g = aggregate_global(per_work)
        assert g.meets_nivel_ii_by_A is True
        assert g.meets_nivel_iii_by_A is True
        # Ningún atributo "level_assigned" o "automatic_level"
        assert not any(
            "level" in f.lower() and "assigned" in f.lower()
            for f in g.__dataclass_fields__
        )

    def test_diversidad_zero_si_no_citas_externas(self):
        per_work = [
            WorkCitationAnalysis(
                work_internal_id="w", title="t", year=2024, doi=None,
                openalex_id=None, work_authors=[],
                total_citers=0, cita_A=0, cita_B=0,
                autocita_estricta=0, cita_por_coautor_historico=0,
            )
        ]
        g = aggregate_global(per_work)
        assert g.diversity_ratio_A == 0.0


class TestUmbrales:
    """Umbrales oficiales SNII Matemáticas."""

    def test_umbrales_son_los_documentados(self):
        assert SNII_MATH_THRESHOLDS["nivel_ii_min_citas"] == 20
        assert SNII_MATH_THRESHOLDS["nivel_iii_min_citas"] == 40
