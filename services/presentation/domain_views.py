"""Typed backend-neutral public views for procurement programs and exercises."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .projection_support import (
    ProjectionError,
    index_by_id,
    render_citations,
)
from .relationship_graph import build_relationship_graph

_VISIBLE_CLAIM_STATES = {"active", "disputed"}
_PROCUREMENT_FACT_PREDICATES = {
    "procurement_program.lifecycle_state",
    "procurement.quantity",
}


def _active_entity(
    entity_id: str,
    *,
    expected_type: str,
    entities_by_id: Mapping[str, Mapping[str, Any]],
) -> Mapping[str, Any]:
    entity = entities_by_id.get(entity_id)
    if entity is None:
        raise ProjectionError(f"unknown {expected_type} Entity: {entity_id}")
    if entity.get("entity_type") != expected_type:
        raise ProjectionError(f"{entity_id} is not a {expected_type} Entity")
    if entity.get("record_status") != "active":
        raise ProjectionError(f"{entity_id} is not an active canonical Entity")
    names = entity.get("names")
    if not isinstance(names, Mapping) or not names:
        raise ProjectionError(f"{entity_id} requires at least one canonical public name")
    return entity


def _claim_ids_from_graph(graph: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    edges = graph.get("edges")
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes)):
        raise ProjectionError("relationship graph edges are malformed")
    for edge in edges:
        if not isinstance(edge, Mapping):
            raise ProjectionError("relationship graph edge is malformed")
        if edge.get("edge_kind") != "claim_relation":
            continue
        source_record_id = edge.get("source_record_id")
        if not isinstance(source_record_id, str) or not source_record_id:
            raise ProjectionError("claim relationship edge requires source_record_id")
        result.add(source_record_id)
    return result


def _staleness_for_claims(
    staleness_report: Mapping[str, Any],
    claim_ids: set[str],
    *,
    claims_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    items = staleness_report.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        raise ProjectionError("staleness report requires items")

    by_id: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if not isinstance(item, Mapping):
            raise ProjectionError("staleness item must be an object")
        claim_id = item.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ProjectionError("staleness item requires claim_id")
        if claim_id in by_id:
            raise ProjectionError(f"duplicate staleness item for Claim {claim_id}")
        by_id[claim_id] = item

    missing = sorted(claim_ids - set(by_id))
    if missing:
        raise ProjectionError(
            "domain view is missing staleness items for current Claims: "
            + ", ".join(missing)
        )

    rendered: list[dict[str, Any]] = []
    for claim_id in sorted(claim_ids):
        claim = claims_by_id.get(claim_id)
        if claim is None:
            raise ProjectionError(f"domain view references unknown Claim {claim_id}")
        item = by_id[claim_id]
        for field in ("subject_id", "predicate_id", "claim_state", "confidence"):
            if item.get(field) != claim.get(field):
                raise ProjectionError(
                    f"staleness item for Claim {claim_id} disagrees on {field}"
                )
        rendered.append(dict(item))
    return rendered


def _procurement_facts(
    *,
    entity_id: str,
    claims: Sequence[Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    facts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for claim in claims:
        if claim.get("claim_state") not in _VISIBLE_CLAIM_STATES:
            continue
        if claim.get("subject_id") != entity_id:
            continue
        predicate_id = claim.get("predicate_id")
        if predicate_id not in _PROCUREMENT_FACT_PREDICATES:
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ProjectionError("procurement fact requires canonical Claim ID")
        if claim_id in seen_ids:
            raise ProjectionError(f"duplicate procurement fact Claim ID: {claim_id}")
        seen_ids.add(claim_id)
        value = claim.get("value")
        if not isinstance(value, Mapping) or not value:
            raise ProjectionError(f"Claim {claim_id} requires a typed value")
        citations = render_citations(
            claim.get("evidence_links"),
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )
        fact: dict[str, Any] = {
            "claim_id": claim_id,
            "predicate_id": predicate_id,
            "value": dict(value),
            "confidence": claim.get("confidence"),
            "claim_state": claim.get("claim_state"),
            "citations": citations,
        }
        if isinstance(claim.get("validity"), Mapping):
            fact["validity"] = dict(claim["validity"])
        facts.append(fact)

    facts.sort(key=lambda item: item["claim_id"])
    return facts


def _lifecycle_history(facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    matches = [
        fact
        for fact in facts
        if fact.get("predicate_id") == "procurement_program.lifecycle_state"
    ]
    if not matches:
        return {
            "status": "unknown",
            "claim_ids": [],
            "observations": [],
            "reason": "No admitted canonical Claim documents lifecycle state history.",
        }

    observations: list[dict[str, Any]] = []
    has_disputed = False
    for fact in matches:
        claim_id = fact.get("claim_id")
        value = fact.get("value")
        if not isinstance(claim_id, str):
            raise ProjectionError("lifecycle fact requires Claim ID")
        if not isinstance(value, Mapping) or value.get("kind") != "string":
            raise ProjectionError(
                f"lifecycle Claim {claim_id} must use a string value"
            )
        rendered_value = value.get("value")
        if not isinstance(rendered_value, str) or not rendered_value:
            raise ProjectionError(f"lifecycle Claim {claim_id} has empty value")
        claim_state = fact.get("claim_state")
        if claim_state not in _VISIBLE_CLAIM_STATES:
            raise ProjectionError(f"lifecycle Claim {claim_id} has invalid public state")
        observations.append(
            {
                "claim_id": claim_id,
                "value": rendered_value,
                "claim_state": claim_state,
                "validity": (
                    dict(fact["validity"])
                    if isinstance(fact.get("validity"), Mapping)
                    else {}
                ),
            }
        )
        has_disputed = has_disputed or claim_state == "disputed"

    observations.sort(key=lambda item: item["claim_id"])
    return {
        "status": "disputed" if has_disputed else "documented",
        "claim_ids": [item["claim_id"] for item in observations],
        "observations": observations,
        "reason": (
            "At least one lifecycle-history Claim is explicitly disputed."
            if has_disputed
            else None
        ),
    }


def build_procurement_program_view(
    *,
    entity_id: str,
    entities: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    staleness_report: Mapping[str, Any],
    projected_at: str,
    revision_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a cited procurement view without inventing a current lifecycle state."""

    entities_by_id = index_by_id(entities, "Entity")
    claims_by_id = index_by_id(claims, "Claim")
    evidence_by_id = index_by_id(evidence, "Evidence")
    documents_by_id = index_by_id(documents, "Document")
    sources_by_id = index_by_id(sources, "Source")
    entity = _active_entity(
        entity_id,
        expected_type="procurement_program",
        entities_by_id=entities_by_id,
    )

    graph = build_relationship_graph(
        root_entity_ids=[entity_id],
        entities=entities,
        claims=claims,
        events=events,
        evidence=evidence,
        documents=documents,
        sources=sources,
        projected_at=projected_at,
        domains=["procurement"],
        revision_ids=revision_ids,
    )
    facts = _procurement_facts(
        entity_id=entity_id,
        claims=claims,
        evidence_by_id=evidence_by_id,
        documents_by_id=documents_by_id,
        sources_by_id=sources_by_id,
    )

    relevant_claim_ids = _claim_ids_from_graph(graph)
    relevant_claim_ids.update(str(fact["claim_id"]) for fact in facts)
    staleness = _staleness_for_claims(
        staleness_report,
        relevant_claim_ids,
        claims_by_id=claims_by_id,
    )

    record_ids = set(graph["provenance"]["record_ids"])
    for fact in facts:
        record_ids.add(str(fact["claim_id"]))
        for citation in fact["citations"]:
            record_ids.update(
                [citation["evidence_id"], citation["document_id"], citation["source_id"]]
            )

    return {
        "id": entity_id,
        "entity_type": "procurement_program",
        "names": dict(entity["names"]),
        "descriptions": (
            dict(entity["descriptions"])
            if isinstance(entity.get("descriptions"), Mapping)
            else None
        ),
        "lifecycle_history": _lifecycle_history(facts),
        "facts": facts,
        "graph": graph,
        "staleness": staleness,
        "provenance": {
            "projected_at": projected_at,
            "record_ids": sorted(record_ids),
            "revision_ids": sorted(set(revision_ids)),
        },
    }


def build_exercise_view(
    *,
    entity_id: str,
    entities: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    staleness_report: Mapping[str, Any],
    projected_at: str,
    revision_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a cited exercise view from explicit exercise Claims and Events."""

    entities_by_id = index_by_id(entities, "Entity")
    claims_by_id = index_by_id(claims, "Claim")
    entity = _active_entity(
        entity_id,
        expected_type="exercise",
        entities_by_id=entities_by_id,
    )
    graph = build_relationship_graph(
        root_entity_ids=[entity_id],
        entities=entities,
        claims=claims,
        events=events,
        evidence=evidence,
        documents=documents,
        sources=sources,
        projected_at=projected_at,
        domains=["exercise"],
        revision_ids=revision_ids,
    )
    relevant_claim_ids = _claim_ids_from_graph(graph)
    staleness = _staleness_for_claims(
        staleness_report,
        relevant_claim_ids,
        claims_by_id=claims_by_id,
    )

    return {
        "id": entity_id,
        "entity_type": "exercise",
        "names": dict(entity["names"]),
        "descriptions": (
            dict(entity["descriptions"])
            if isinstance(entity.get("descriptions"), Mapping)
            else None
        ),
        "graph": graph,
        "staleness": staleness,
        "provenance": {
            "projected_at": projected_at,
            "record_ids": list(graph["provenance"]["record_ids"]),
            "revision_ids": sorted(set(revision_ids)),
        },
    }
