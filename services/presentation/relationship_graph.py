"""Build a bounded backend-neutral public relationship graph from canonical SDA records.

The graph uses a bounded single-pass expansion from explicit root Entity IDs.
Every edge is backed by either one canonical Claim or one canonical Event; the
projector never creates inferred entity-to-entity relationships. Material graph
records reuse the same fail-closed Evidence -> Document -> Source resolution as
the M1 public view.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from .equipment_view import (
    ProjectionError,
    _citations,
    _entity_value_id,
    _index,
)

_VISIBLE_CLAIM_STATES = {"active", "disputed"}
_DOMAIN_PREDICATES = {
    "procurement": {
        "manufacturer.manufactures.equipment",
        "company.participates_in.procurement_program",
        "procurement_program.acquires.equipment_variant",
        "contract.part_of.procurement_program",
        "contract.awarded_to.company",
    },
    "exercise": {
        "exercise.participant.organization",
        "exercise.uses.equipment_variant",
    },
}
_DOMAIN_EVENTS = {
    "procurement": {
        "procurement_request",
        "procurement_approval_or_notification",
        "contract_award",
        "contract_signature",
        "order",
        "delivery_start",
        "delivery",
        "entry_into_service",
        "cancellation",
        "suspension",
    },
    "exercise": {"exercise"},
}


def _sequence(value: Any) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _entity_node(entity_id: str, entities_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    entity = entities_by_id.get(entity_id)
    if entity is None:
        raise ProjectionError(f"unresolved graph Entity: {entity_id}")
    if entity.get("record_status") != "active":
        raise ProjectionError(f"graph Entity {entity_id} is not an active canonical Entity")
    names = entity.get("names")
    if not isinstance(names, Mapping) or not names:
        raise ProjectionError(f"graph Entity {entity_id} requires a public name")
    return {
        "id": entity_id,
        "node_kind": "entity",
        "entity_type": str(entity.get("entity_type")),
        "subtype": entity.get("subtype") if isinstance(entity.get("subtype"), str) else None,
        "names": dict(names),
    }


def _event_domain(event_type: Any, domains: set[str]) -> str | None:
    if not isinstance(event_type, str):
        return None
    for domain in sorted(domains):
        if event_type in _DOMAIN_EVENTS[domain]:
            return domain
    return None


def _participant_ids(event: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for participant in _sequence(event.get("participants")):
        if not isinstance(participant, Mapping):
            raise ProjectionError("Event participant must be an object")
        entity_id = participant.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ProjectionError("Event participant requires canonical Entity ID")
        result.add(entity_id)
    return result


def _related_entity_ids(event: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for entity_id in _sequence(event.get("related_entity_ids")):
        if not isinstance(entity_id, str) or not entity_id:
            raise ProjectionError("Event related_entity_ids must contain canonical Entity IDs")
        result.add(entity_id)
    return result


def _related_claim_ids(event: Mapping[str, Any]) -> set[str]:
    result: set[str] = set()
    for claim_id in _sequence(event.get("related_claim_ids")):
        if not isinstance(claim_id, str) or not claim_id:
            raise ProjectionError("Event related_claim_ids must contain canonical Claim IDs")
        result.add(claim_id)
    return result


def build_relationship_graph(
    *,
    root_entity_ids: Sequence[str],
    entities: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    projected_at: str,
    domains: Sequence[str] = ("procurement", "exercise"),
    revision_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Return a deterministic bounded procurement/exercise graph.

    Expansion semantics are deliberately single-pass: Claims are selected only
    when one endpoint is an explicit root Entity. Matching Events may then attach
    to those selected Entities/Claims, but newly discovered nodes never trigger
    another Claim or Event expansion pass.
    """

    roots = list(root_entity_ids)
    if not roots or any(not isinstance(value, str) or not value for value in roots):
        raise ProjectionError("relationship graph requires at least one canonical root Entity ID")
    if len(set(roots)) != len(roots):
        raise ProjectionError("relationship graph root Entity IDs must be unique")
    root_set = set(roots)

    domain_values = list(domains)
    if len(set(domain_values)) != len(domain_values):
        raise ProjectionError("relationship graph domains must be unique")
    selected_domains = set(domain_values)
    if not selected_domains or not selected_domains.issubset(_DOMAIN_PREDICATES):
        raise ProjectionError("relationship graph domains must be procurement and/or exercise")

    entities_by_id = _index(entities, "Entity")
    evidence_by_id = _index(evidence, "Evidence")
    documents_by_id = _index(documents, "Document")
    sources_by_id = _index(sources, "Source")

    for root_id in roots:
        _entity_node(root_id, entities_by_id)

    allowed_predicates = set().union(*(_DOMAIN_PREDICATES[domain] for domain in selected_domains))
    selected_entity_ids: set[str] = set(roots)
    selected_claims: list[Mapping[str, Any]] = []
    selected_claim_ids: set[str] = set()

    for claim in claims:
        if claim.get("claim_state") not in _VISIBLE_CLAIM_STATES:
            continue
        predicate_id = claim.get("predicate_id")
        if predicate_id not in allowed_predicates:
            continue
        subject_id = claim.get("subject_id")
        value_id = _entity_value_id(claim)
        if not isinstance(subject_id, str) or not isinstance(value_id, str):
            continue
        if subject_id not in root_set and value_id not in root_set:
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id:
            raise ProjectionError("selected graph Claim requires canonical ID")
        selected_claims.append(claim)
        selected_claim_ids.add(claim_id)
        selected_entity_ids.update((subject_id, value_id))

    selected_events: list[Mapping[str, Any]] = []
    for event in events:
        if _event_domain(event.get("event_type"), selected_domains) is None:
            continue
        participant_ids = _participant_ids(event)
        related_entity_ids = _related_entity_ids(event)
        related_claim_ids = _related_claim_ids(event)
        if (
            not selected_entity_ids.intersection(participant_ids | related_entity_ids)
            and not selected_claim_ids.intersection(related_claim_ids)
        ):
            continue
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ProjectionError("selected graph Event requires canonical ID")
        selected_events.append(event)
        selected_entity_ids.update(participant_ids)
        selected_entity_ids.update(related_entity_ids)

    nodes = [_entity_node(entity_id, entities_by_id) for entity_id in sorted(selected_entity_ids)]
    edges: list[dict[str, Any]] = []
    timeline: list[dict[str, Any]] = []
    used_record_ids: set[str] = set(selected_entity_ids)

    for claim in selected_claims:
        claim_id = str(claim["id"])
        subject_id = str(claim["subject_id"])
        value_id = _entity_value_id(claim)
        if value_id is None:
            raise ProjectionError(f"selected graph Claim {claim_id} lost its Entity value")
        citations = _citations(
            claim.get("evidence_links"),
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )
        edge = {
            "id": f"claim:{claim_id}",
            "edge_kind": "claim_relation",
            "source_record_id": claim_id,
            "from_id": subject_id,
            "to_id": value_id,
            "relation": str(claim.get("predicate_id")),
            "confidence": claim.get("confidence"),
            "state": claim.get("claim_state"),
            "validity": dict(claim["validity"]) if isinstance(claim.get("validity"), Mapping) else None,
            "citations": citations,
        }
        edges.append(edge)
        used_record_ids.add(claim_id)
        for citation in citations:
            used_record_ids.update(
                [citation["evidence_id"], citation["document_id"], citation["source_id"]]
            )

    event_nodes: list[dict[str, Any]] = []
    for event in selected_events:
        event_id = str(event["id"])
        occurred_at = event.get("occurred_at")
        if not isinstance(occurred_at, Mapping) or not occurred_at:
            raise ProjectionError(f"selected graph Event {event_id} requires occurred_at")
        citations = _citations(
            event.get("evidence_links"),
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )
        event_node = {
            "id": event_id,
            "node_kind": "event",
            "event_type": str(event.get("event_type")),
            "names": dict(event["names"]) if isinstance(event.get("names"), Mapping) else None,
            "occurred_at": dict(occurred_at),
            "confidence": event.get("confidence"),
            "citations": citations,
        }
        event_nodes.append(event_node)
        timeline.append(
            {
                "event_id": event_id,
                "event_type": event_node["event_type"],
                "names": event_node["names"],
                "occurred_at": dict(occurred_at),
                "confidence": event.get("confidence"),
                "citations": citations,
            }
        )
        used_record_ids.add(event_id)
        for citation in citations:
            used_record_ids.update(
                [citation["evidence_id"], citation["document_id"], citation["source_id"]]
            )

        seen_event_edges: set[str] = set()
        for participant in _sequence(event.get("participants")):
            assert isinstance(participant, Mapping)
            entity_id = str(participant["entity_id"])
            role = str(participant.get("role"))
            edge_id = f"event:{event_id}:participant:{role}:{entity_id}"
            if edge_id in seen_event_edges:
                raise ProjectionError(f"duplicate Event participant edge: {edge_id}")
            seen_event_edges.add(edge_id)
            edges.append(
                {
                    "id": edge_id,
                    "edge_kind": "event_participation",
                    "source_record_id": event_id,
                    "from_id": event_id,
                    "to_id": entity_id,
                    "relation": role,
                    "confidence": event.get("confidence"),
                    "state": None,
                    "validity": None,
                    "citations": citations,
                }
            )

        for entity_id in sorted(_related_entity_ids(event)):
            edge_id = f"event:{event_id}:related:{entity_id}"
            if edge_id in seen_event_edges:
                raise ProjectionError(f"duplicate Event related edge: {edge_id}")
            seen_event_edges.add(edge_id)
            edges.append(
                {
                    "id": edge_id,
                    "edge_kind": "event_related_entity",
                    "source_record_id": event_id,
                    "from_id": event_id,
                    "to_id": entity_id,
                    "relation": "related_entity",
                    "confidence": event.get("confidence"),
                    "state": None,
                    "validity": None,
                    "citations": citations,
                }
            )

    nodes.extend(sorted(event_nodes, key=lambda item: item["id"]))
    nodes.sort(key=lambda item: (item["node_kind"], item["id"]))
    edges.sort(key=lambda item: item["id"])
    timeline.sort(key=lambda item: (str(item["occurred_at"].get("value", "")), item["event_id"]))

    node_ids = {node["id"] for node in nodes}
    if len(node_ids) != len(nodes):
        raise ProjectionError("relationship graph contains duplicate node IDs")
    edge_ids = {edge["id"] for edge in edges}
    if len(edge_ids) != len(edges):
        raise ProjectionError("relationship graph contains duplicate edge IDs")
    for edge in edges:
        if edge["from_id"] not in node_ids or edge["to_id"] not in node_ids:
            raise ProjectionError(f"relationship graph edge {edge['id']} references a missing node")

    return {
        "scope": {
            "root_entity_ids": sorted(roots),
            "domains": sorted(selected_domains),
            "expansion": "bounded_single_pass",
        },
        "nodes": nodes,
        "edges": edges,
        "timeline": timeline,
        "provenance": {
            "projected_at": projected_at,
            "record_ids": sorted(used_record_ids),
            "revision_ids": sorted(set(revision_ids)),
        },
    }
