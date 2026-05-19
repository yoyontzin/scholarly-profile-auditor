"""Red de coautoría: nodos y aristas a partir de obras confirmadas."""

from __future__ import annotations

from collections import Counter

from app.core.normalize import normalize_person_name
from app.models.verification import VerificationStatus
from app.models.work import WorkRecord


def build_coauthor_network(
    works: list[WorkRecord],
    author_display_name: str,
) -> dict:
    """Devuelve un grafo simple (lista de nodos y aristas)."""
    author_norm = normalize_person_name(author_display_name)
    edge_counter: Counter[tuple[str, str]] = Counter()
    node_counter: Counter[str] = Counter()

    for w in works:
        if not (
            w.verification and w.verification.status == VerificationStatus.CONFIRMED
        ):
            continue
        coauthors = [a for a in w.authors if normalize_person_name(a) != author_norm]
        for a in coauthors:
            node_counter[a] += 1
            # arista autor↔coautor
            edge = tuple(sorted([author_display_name, a]))
            edge_counter[edge] += 1
        # aristas entre coautores (densidad)
        for i in range(len(coauthors)):
            for j in range(i + 1, len(coauthors)):
                edge = tuple(sorted([coauthors[i], coauthors[j]]))
                edge_counter[edge] += 1

    nodes = [
        {"id": name, "weight": w} for name, w in node_counter.most_common()
    ]
    nodes.insert(0, {"id": author_display_name, "weight": sum(node_counter.values()) or 1})

    edges = [
        {"source": a, "target": b, "weight": w}
        for (a, b), w in edge_counter.most_common()
    ]
    return {"nodes": nodes, "edges": edges}
