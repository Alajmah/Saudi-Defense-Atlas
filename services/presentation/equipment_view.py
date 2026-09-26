"""Build a backend-neutral public equipment view from canonical SDA records.

The projector accepts project-domain records, never raw Wikibase Q/P/snaks. It
fails closed when a material Claim/Event cannot resolve its Evidence -> Document
-> Source chain, so the public API cannot silently publish an uncited fact.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class ProjectionError(ValueError):
    """Raised when canonical records are insufficient for a safe public view."""


_VISIBLE_CLAIM_STATES = {"active", "disputed"}
_FIELD_PREDICATES = {
    "manufacturer": {"manufacturer.manufactures.equipment"},
    "operator": {
        "organization.operates.equipment_variant",
        "military_unit.operates.equipment_variant",
    },
    "inventory_quantity": {"inventory.quantity"},
    "service_state": {"equipment.service_state"},
}


def _index(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ProjectionError(f"{label} record requires canonical SDA id")
        if record_id in result:
            raise ProjectionError(f"duplicate {label} id: {record_id}")
        result[record_id] = record
    return result


def _aliases(entity: Mapping[str, Any]) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {"ar": [], "en": []}
    aliases = entity.get("aliases")
    if not isinstance(aliases, Sequence) or isinstance(aliases, (str, bytes)):
        return values
    for alias in aliases:
        if not isinstance(alias, Mapping):
            continue
        language = alias.get("language")
        value = alias.get("value")
        if language in values and isinstance(value, str) and value:
            if value not in values[language]:
                values[language].append(value)
    for language in values:
        values[language].sort()
    return values


def _entity_value_id(claim: Mapping[str, Any]) -> str | None:
    value = claim.get("value")
    if not isinstance(value, Mapping) or value.get("kind") != "entity":
        return None
    entity_id = value.get("entity_id")
    return entity_id if isinstance(entity_id, str) else None


def _claim_direction(claim: Mapping[str, Any], target_id: str) -> str | None:
    if claim.get("subject_id") == target_id:
        return "outbound"
    if _entity_value_id(claim) == target_id:
        return "inbound"
    scope = claim.get("scope")
    if isinstance(scope, Mapping):
        entity_ids = scope.get("entity_ids")
        if isinstance(entity_ids, Sequence) and not isinstance(entity_ids, (str, bytes)):
            if target_id in entity_ids:
                return "scoped"
    return None


def _citation(
    link: Mapping[str, Any],
    *,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    evidence_id = link.get("evidence_id")
    if not isinstance(evidence_id, str) or evidence_id not in evidence_by_id:
        raise ProjectionError(f"unresolved Evidence link: {evidence_id!r}")
    evidence = evidence_by_id[evidence_id]

    document_id = evidence.get("document_id")
    if not isinstance(document_id, str) or document_id not in documents_by_id:
        raise ProjectionError(f"Evidence {evidence_id} has unresolved Document {document_id!r}")
    document = documents_by_id[document_id]

    source_id = document.get("source_id")
    if not isinstance(source_id, str) or source_id not in sources_by_id:
        raise ProjectionError(f"Document {document_id} has unresolved Source {source_id!r}")
    source = sources_by_id[source_id]

    locator = evidence.get("locator")
    if not isinstance(locator, Mapping) or not locator:
        raise ProjectionError(f"Evidence {evidence_id} requires a locator")

    url = (
        document.get("canonical_url")
        or document.get("retrieved_url")
        or document.get("archival_url")
    )
    return {
        "evidence_id": evidence_id,
        "evidence_role": str(link.get("role")),
        "document_id": document_id,
        "source_id": source_id,
        "source_class": source.get("source_class"),
        "publisher": dict(source.get("publisher") or {}),
        "document_title": (
            dict(document["title"]) if isinstance(document.get("title"), Mapping) else None
        ),
        "url": url if isinstance(url, str) else None,
        "published_at": (
            dict(document["published_at"])
            if isinstance(document.get("published_at"), Mapping)
            else None
        ),
        "retrieved_at": document.get("retrieved_at"),
        "locator": dict(locator),
    }


def _citations(
    links: Any,
    *,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(links, Sequence) or isinstance(links, (str, bytes)) or not links:
        raise ProjectionError("public material record requires at least one Evidence link")
    rendered: list[dict[str, Any]] = []
    for link in links:
        if not isinstance(link, Mapping):
            raise ProjectionError("Evidence link must be an object")
        rendered.append(
            _citation(
                link,
                evidence_by_id=evidence_by_id,
                documents_by_id=documents_by_id,
                sources_by_id=sources_by_id,
            )
        )
    rendered.sort(key=lambda item: (item["evidence_id"], item["evidence_role"]))
    return rendered


def _presented_entity(entity_id: str, entities_by_id: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    entity = entities_by_id.get(entity_id)
    if entity is None:
        raise ProjectionError(f"unresolved related Entity: {entity_id}")
    names = entity.get("names")
    if not isinstance(names, Mapping) or not names:
        raise ProjectionError(f"related Entity {entity_id} has no public name")
    return {
        "id": entity_id,
        "entity_type": str(entity.get("entity_type")),
        "names": dict(names),
    }


def _field_state(field: str, facts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    predicates = _FIELD_PREDICATES[field]
    matches = [fact for fact in facts if fact.get("predicate_id") in predicates]
    if not matches:
        return {
            "state": "unknown",
            "claim_ids": [],
            "reason": "No admitted canonical Claim establishes this field.",
        }
    claim_ids = sorted(str(fact["claim_id"]) for fact in matches)
    state = "disputed" if any(fact.get("claim_state") == "disputed" for fact in matches) else "known"
    return {"state": state, "claim_ids": claim_ids, "reason": None}


def build_equipment_view(
    *,
    entity_id: str,
    entities: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    projected_at: str,
    revision_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Return a deterministic public view for one equipment/equipment-variant Entity."""
    entities_by_id = _index(entities, "Entity")
    evidence_by_id = _index(evidence, "Evidence")
    documents_by_id = _index(documents, "Document")
    sources_by_id = _index(sources, "Source")

    entity = entities_by_id.get(entity_id)
    if entity is None:
        raise ProjectionError(f"unknown equipment Entity: {entity_id}")
    if entity.get("entity_type") not in {"equipment", "equipment_variant"}:
        raise ProjectionError(f"{entity_id} is not equipment/equipment_variant")
    if entity.get("record_status") != "active":
        raise ProjectionError(f"{entity_id} is not an active canonical Entity")

    names = entity.get("names")
    if not isinstance(names, Mapping) or not names:
        raise ProjectionError(f"{entity_id} requires at least one canonical public name")

    presented_facts: list[dict[str, Any]] = []
    relevant_claim_ids: set[str] = set()
    related_ids: set[str] = set()
    used_record_ids: set[str] = {entity_id}

    for claim in claims:
        if claim.get("claim_state") not in _VISIBLE_CLAIM_STATES:
            continue
        direction = _claim_direction(claim, entity_id)
        if direction is None:
            continue
        claim_id = claim.get("id")
        if not isinstance(claim_id, str):
            raise ProjectionError("relevant Claim requires canonical ID")
        citations = _citations(
            claim.get("evidence_links"),
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )
        fact = {
            "claim_id": claim_id,
            "predicate_id": claim.get("predicate_id"),
            "direction": direction,
            "subject_id": claim.get("subject_id"),
            "value": dict(claim.get("value") or {}),
            "confidence": claim.get("confidence"),
            "claim_state": claim.get("claim_state"),
            "citations": citations,
        }
        if isinstance(claim.get("validity"), Mapping):
            fact["validity"] = dict(claim["validity"])
        presented_facts.append(fact)
        relevant_claim_ids.add(claim_id)
        used_record_ids.add(claim_id)

        subject_id = claim.get("subject_id")
        value_id = _entity_value_id(claim)
        for candidate in (subject_id, value_id):
            if isinstance(candidate, str) and candidate != entity_id:
                related_ids.add(candidate)
        for citation in citations:
            used_record_ids.update(
                [citation["evidence_id"], citation["document_id"], citation["source_id"]]
            )

    presented_facts.sort(key=lambda item: item["claim_id"])

    presented_events: list[dict[str, Any]] = []
    for event in events:
        participants = event.get("participants")
        participant_ids = {
            participant.get("entity_id")
            for participant in participants
            if isinstance(participants, Sequence)
            and not isinstance(participants, (str, bytes))
            and isinstance(participant, Mapping)
            and isinstance(participant.get("entity_id"), str)
        } if isinstance(participants, Sequence) and not isinstance(participants, (str, bytes)) else set()
        related_entity_ids = event.get("related_entity_ids")
        related_entity_set = set(related_entity_ids) if isinstance(related_entity_ids, Sequence) and not isinstance(related_entity_ids, (str, bytes)) else set()
        related_claim_ids = event.get("related_claim_ids")
        related_claim_set = set(related_claim_ids) if isinstance(related_claim_ids, Sequence) and not isinstance(related_claim_ids, (str, bytes)) else set()

        if (
            entity_id not in participant_ids
            and entity_id not in related_entity_set
            and not relevant_claim_ids.intersection(related_claim_set)
        ):
            continue

        event_id = event.get("id")
        if not isinstance(event_id, str):
            raise ProjectionError("relevant Event requires canonical ID")
        citations = _citations(
            event.get("evidence_links"),
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )
        rendered_participants: list[dict[str, Any]] = []
        if isinstance(participants, Sequence) and not isinstance(participants, (str, bytes)):
            for participant in participants:
                if not isinstance(participant, Mapping):
                    raise ProjectionError(f"Event {event_id} participant is malformed")
                participant_id = participant.get("entity_id")
                if not isinstance(participant_id, str):
                    raise ProjectionError(f"Event {event_id} participant lacks Entity ID")
                related = _presented_entity(participant_id, entities_by_id)
                rendered_participants.append(
                    {
                        "entity_id": participant_id,
                        "role": str(participant.get("role")),
                        "names": related["names"],
                    }
                )
                if participant_id != entity_id:
                    related_ids.add(participant_id)
        rendered_participants.sort(key=lambda item: (item["role"], item["entity_id"]))

        presented_events.append(
            {
                "event_id": event_id,
                "event_type": event.get("event_type"),
                "names": dict(event["names"]) if isinstance(event.get("names"), Mapping) else None,
                "occurred_at": dict(event.get("occurred_at") or {}),
                "confidence": event.get("confidence"),
                "participants": rendered_participants,
                "related_claim_ids": sorted(
                    str(value) for value in related_claim_set if isinstance(value, str)
                ),
                "citations": citations,
            }
        )
        used_record_ids.add(event_id)
        for citation in citations:
            used_record_ids.update(
                [citation["evidence_id"], citation["document_id"], citation["source_id"]]
            )

    presented_events.sort(
        key=lambda item: (str(item["occurred_at"].get("value", "")), item["event_id"])
    )

    related_entities = [
        _presented_entity(related_id, entities_by_id)
        for related_id in sorted(related_ids)
    ]
    used_record_ids.update(related_ids)

    return {
        "id": entity_id,
        "entity_type": entity["entity_type"],
        "names": dict(names),
        "aliases": _aliases(entity),
        "descriptions": (
            dict(entity["descriptions"])
            if isinstance(entity.get("descriptions"), Mapping)
            else None
        ),
        "field_states": {
            field: _field_state(field, presented_facts)
            for field in ("manufacturer", "operator", "inventory_quantity", "service_state")
        },
        "facts": presented_facts,
        "events": presented_events,
        "related_entities": related_entities,
        "provenance": {
            "projected_at": projected_at,
            "record_ids": sorted(used_record_ids),
            "revision_ids": sorted(set(revision_ids)),
        },
    }
