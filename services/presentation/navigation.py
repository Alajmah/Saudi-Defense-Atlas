"""Public M3 navigation projection over already-approved public projections.

Filter navigation consumes SearchDocument only. Timeline navigation consumes the
bounded RelationshipGraphView timeline only. This module does not inspect raw
Claims/Events and does not infer current state from event ordering.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from .projection_support import ProjectionError

_BACKEND_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])")
_ENTITY_FACETS = ("service_ids", "manufacturer_ids", "country_ids")
_STRING_FACETS = ("equipment_classes", "status_values")
_REQUIRED_FACETS = (*_ENTITY_FACETS, *_STRING_FACETS)
_ENTITY_FACET_TYPES = {
    "service_ids": {"organization", "military_unit"},
    "manufacturer_ids": {"organization"},
    "country_ids": {"country"},
}


def _utc(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectionError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise ProjectionError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _assert_no_backend_ids(value: Any) -> None:
    if _BACKEND_ID_RE.search(repr(value)):
        raise ProjectionError("backend Q/P identifier leaked into navigation projection")


def _string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ProjectionError(f"{label} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise ProjectionError(f"{label} contains invalid value")
        result.append(item)
    if len(result) != len(set(result)):
        raise ProjectionError(f"{label} contains duplicate values")
    return result


def _localized_names(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ProjectionError(f"{label} requires localized names")
    result: dict[str, str] = {}
    for locale in ("ar", "en"):
        text = value.get(locale)
        if text is None:
            continue
        if not isinstance(text, str) or not text:
            raise ProjectionError(f"{label}.{locale} must be non-empty")
        result[locale] = text
    if not result:
        raise ProjectionError(f"{label} requires ar or en name")
    return result


def _index_search_documents(
    documents: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise ProjectionError("search_documents must be an array")
    indexed: dict[str, Mapping[str, Any]] = {}
    for raw in documents:
        if not isinstance(raw, Mapping):
            raise ProjectionError("SearchDocument must be an object")
        document_id = raw.get("id")
        entity_type = raw.get("entity_type")
        if not isinstance(document_id, str) or not document_id:
            raise ProjectionError("SearchDocument requires canonical SDA id")
        if document_id in indexed:
            raise ProjectionError(f"duplicate SearchDocument id: {document_id}")
        if not isinstance(entity_type, str) or not entity_type:
            raise ProjectionError(f"SearchDocument {document_id} requires entity_type")
        _localized_names(raw.get("names"), f"SearchDocument {document_id}.names")
        facets = raw.get("facets")
        if not isinstance(facets, Mapping) or set(facets) != set(_REQUIRED_FACETS):
            raise ProjectionError(f"SearchDocument {document_id} has invalid facet shape")
        for facet in _REQUIRED_FACETS:
            _string_array(facets.get(facet), f"SearchDocument {document_id}.{facet}")
        revision_ids = _string_array(
            raw.get("revision_ids"), f"SearchDocument {document_id}.revision_ids"
        )
        if not revision_ids:
            raise ProjectionError(f"SearchDocument {document_id} requires revision_ids")
        _assert_no_backend_ids(raw)
        indexed[document_id] = raw
    return indexed


def _build_filter_catalog(
    indexed: Mapping[str, Mapping[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    entity_type_counts: Counter[str] = Counter()
    facet_counts: dict[str, Counter[str]] = {
        facet: Counter() for facet in _REQUIRED_FACETS
    }

    for document in indexed.values():
        entity_type_counts[str(document["entity_type"])] += 1
        facets = document["facets"]
        for facet in _REQUIRED_FACETS:
            for value in facets[facet]:
                facet_counts[facet][value] += 1

    result: dict[str, list[dict[str, Any]]] = {
        "entity_types": [
            {"value": value, "count": entity_type_counts[value]}
            for value in sorted(entity_type_counts)
        ]
    }

    for facet in _ENTITY_FACETS:
        options: list[dict[str, Any]] = []
        allowed_types = _ENTITY_FACET_TYPES[facet]
        for entity_id in sorted(facet_counts[facet]):
            target = indexed.get(entity_id)
            if target is None:
                raise ProjectionError(
                    f"filter facet {facet} references missing SearchDocument {entity_id}"
                )
            if target.get("entity_type") not in allowed_types:
                raise ProjectionError(
                    f"filter facet {facet} target {entity_id} has incompatible entity_type"
                )
            options.append(
                {
                    "id": entity_id,
                    "names": _localized_names(
                        target.get("names"), f"filter target {entity_id}.names"
                    ),
                    "count": facet_counts[facet][entity_id],
                }
            )
        result[facet] = options

    for facet in _STRING_FACETS:
        result[facet] = [
            {"value": value, "count": facet_counts[facet][value]}
            for value in sorted(facet_counts[facet])
        ]

    return result


def _supporting_citations(value: Any, event_id: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ProjectionError(f"timeline event {event_id} requires citations")
    citations: dict[tuple[str, str, str], dict[str, Any]] = {}
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ProjectionError(f"timeline event {event_id} citation must be an object")
        if raw.get("evidence_role") != "supports":
            continue
        evidence_id = raw.get("evidence_id")
        document_id = raw.get("document_id")
        source_id = raw.get("source_id")
        if not all(
            isinstance(item, str) and item
            for item in (evidence_id, document_id, source_id)
        ):
            raise ProjectionError(f"timeline event {event_id} citation identity is incomplete")
        key = (evidence_id, document_id, source_id)
        rendered = {
            "evidence_id": evidence_id,
            "evidence_role": "supports",
            "document_id": document_id,
            "source_id": source_id,
            "url": raw.get("url") if isinstance(raw.get("url"), str) else None,
        }
        existing = citations.get(key)
        if existing is not None and existing != rendered:
            raise ProjectionError(
                f"timeline event {event_id} has conflicting duplicate citation identity"
            )
        citations[key] = rendered
    if not citations:
        raise ProjectionError(f"timeline event {event_id} requires supporting Evidence")
    return [citations[key] for key in sorted(citations)]


def _event_material(raw: Mapping[str, Any], event_id: str) -> dict[str, Any]:
    event_type = raw.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        raise ProjectionError(f"timeline event {event_id} requires event_type")
    names_raw = raw.get("names")
    names = None if names_raw is None else _localized_names(names_raw, f"event {event_id}.names")
    occurred_at = raw.get("occurred_at")
    if not isinstance(occurred_at, Mapping):
        raise ProjectionError(f"timeline event {event_id} requires occurred_at")
    occurred_value = occurred_at.get("value")
    occurred_precision = occurred_at.get("precision")
    if not isinstance(occurred_value, str) or not occurred_value:
        raise ProjectionError(f"timeline event {event_id} occurred_at.value is invalid")
    if occurred_precision not in {"year", "month", "day", "second", "unknown"}:
        raise ProjectionError(f"timeline event {event_id} occurred_at.precision is invalid")
    ended_at_raw = raw.get("ended_at")
    if ended_at_raw is not None and not isinstance(ended_at_raw, Mapping):
        raise ProjectionError(f"timeline event {event_id} ended_at is invalid")
    confidence = raw.get("confidence")
    if confidence not in {"verified", "high", "medium", "low", "unverified"}:
        raise ProjectionError(f"timeline event {event_id} confidence is invalid")
    return {
        "event_id": event_id,
        "event_type": event_type,
        "names": names,
        "occurred_at": dict(occurred_at),
        "ended_at": None if ended_at_raw is None else dict(ended_at_raw),
        "confidence": confidence,
    }


def _merge_citation(
    citations: dict[tuple[str, str, str], dict[str, Any]],
    item: dict[str, Any],
    event_id: str,
) -> None:
    key = (item["evidence_id"], item["document_id"], item["source_id"])
    existing = citations.get(key)
    if existing is not None and existing != item:
        raise ProjectionError(
            f"timeline event {event_id} citation conflicts across public graph projections"
        )
    citations[key] = item


def _build_timeline(
    relationship_graphs: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], set[str], set[str]]:
    if not isinstance(relationship_graphs, Sequence) or isinstance(
        relationship_graphs, (str, bytes)
    ):
        raise ProjectionError("relationship_graphs must be an array")

    events: dict[str, dict[str, Any]] = {}
    graph_record_ids: set[str] = set()
    revision_ids: set[str] = set()

    for graph in relationship_graphs:
        if not isinstance(graph, Mapping):
            raise ProjectionError("RelationshipGraphView must be an object")
        _assert_no_backend_ids(graph)
        scope = graph.get("scope")
        if not isinstance(scope, Mapping):
            raise ProjectionError("RelationshipGraphView requires scope")
        roots = _string_array(scope.get("root_entity_ids"), "graph root_entity_ids")
        domains = _string_array(scope.get("domains"), "graph domains")
        if not roots or not domains or any(domain not in {"procurement", "exercise"} for domain in domains):
            raise ProjectionError("RelationshipGraphView has invalid roots/domains")
        if scope.get("expansion") != "bounded_single_pass":
            raise ProjectionError("timeline navigation accepts bounded_single_pass graphs only")

        provenance = graph.get("provenance")
        if not isinstance(provenance, Mapping):
            raise ProjectionError("RelationshipGraphView requires provenance")
        graph_records = _string_array(
            provenance.get("record_ids"), "graph provenance record_ids"
        )
        graph_record_ids.update(graph_records)
        revision_ids.update(
            _string_array(provenance.get("revision_ids"), "graph provenance revision_ids")
        )

        timeline = graph.get("timeline")
        if not isinstance(timeline, Sequence) or isinstance(timeline, (str, bytes)):
            raise ProjectionError("RelationshipGraphView timeline must be an array")
        for raw in timeline:
            if not isinstance(raw, Mapping):
                raise ProjectionError("timeline item must be an object")
            event_id = raw.get("event_id")
            if not isinstance(event_id, str) or not event_id:
                raise ProjectionError("timeline item requires event_id")
            if event_id not in graph_records:
                raise ProjectionError(
                    f"timeline event {event_id} is missing from graph provenance record_ids"
                )
            material = _event_material(raw, event_id)
            citations = _supporting_citations(raw.get("citations"), event_id)
            existing = events.get(event_id)
            if existing is None:
                citation_map: dict[tuple[str, str, str], dict[str, Any]] = {}
                for item in citations:
                    _merge_citation(citation_map, item, event_id)
                events[event_id] = {
                    **material,
                    "domains": set(domains),
                    "root_entity_ids": set(roots),
                    "citations": citation_map,
                }
                continue
            for field in ("event_type", "names", "occurred_at", "ended_at", "confidence"):
                if existing[field] != material[field]:
                    raise ProjectionError(
                        f"timeline event {event_id} conflicts across public graph projections"
                    )
            existing["domains"].update(domains)
            existing["root_entity_ids"].update(roots)
            for item in citations:
                _merge_citation(existing["citations"], item, event_id)

    rendered: list[dict[str, Any]] = []
    for event_id, item in events.items():
        rendered.append(
            {
                "event_id": event_id,
                "event_type": item["event_type"],
                "names": item["names"],
                "occurred_at": item["occurred_at"],
                "ended_at": item["ended_at"],
                "confidence": item["confidence"],
                "domains": sorted(item["domains"]),
                "root_entity_ids": sorted(item["root_entity_ids"]),
                "citations": [item["citations"][key] for key in sorted(item["citations"])],
            }
        )

    # ISO-like values are ordered oldest-first. Unknown-precision records remain
    # explicit and sort after known temporal values rather than being guessed.
    rendered.sort(
        key=lambda item: (
            item["occurred_at"].get("precision") == "unknown",
            item["occurred_at"].get("value", ""),
            item["event_id"],
        )
    )
    return rendered, graph_record_ids, revision_ids


def build_navigation_view(
    *,
    search_documents: Sequence[Mapping[str, Any]],
    relationship_graphs: Sequence[Mapping[str, Any]],
    projected_at: str,
) -> dict[str, Any]:
    """Build deterministic filter and timeline navigation from public projections."""

    indexed = _index_search_documents(search_documents)
    filters = _build_filter_catalog(indexed)
    timeline, graph_record_ids, graph_revision_ids = _build_timeline(relationship_graphs)

    revision_ids = set(graph_revision_ids)
    for document in indexed.values():
        revision_ids.update(document["revision_ids"])

    view = {
        "projected_at": _utc(projected_at, "projected_at"),
        "filters": filters,
        "timeline": timeline,
        "provenance": {
            "search_document_ids": sorted(indexed),
            "graph_record_ids": sorted(graph_record_ids),
            "revision_ids": sorted(revision_ids),
        },
    }
    _assert_no_backend_ids(view)
    return view
