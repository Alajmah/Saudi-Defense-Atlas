"""Shared fail-closed helpers for backend-neutral public SDA projections."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


class ProjectionError(ValueError):
    """Raised when canonical records are insufficient for a safe public view."""


def index_by_id(
    records: Sequence[Mapping[str, Any]],
    label: str,
) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ProjectionError(f"{label} record requires canonical SDA id")
        if record_id in result:
            raise ProjectionError(f"duplicate {label} id: {record_id}")
        result[record_id] = record
    return result


def entity_value_id(claim: Mapping[str, Any]) -> str | None:
    value = claim.get("value")
    if not isinstance(value, Mapping) or value.get("kind") != "entity":
        return None
    entity_id = value.get("entity_id")
    return entity_id if isinstance(entity_id, str) and entity_id else None


def render_citation(
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
        raise ProjectionError(
            f"Evidence {evidence_id} has unresolved Document {document_id!r}"
        )
    document = documents_by_id[document_id]

    source_id = document.get("source_id")
    if not isinstance(source_id, str) or source_id not in sources_by_id:
        raise ProjectionError(
            f"Document {document_id} has unresolved Source {source_id!r}"
        )
    source = sources_by_id[source_id]

    locator = evidence.get("locator")
    if not isinstance(locator, Mapping) or not locator:
        raise ProjectionError(f"Evidence {evidence_id} requires a locator")

    role = link.get("role")
    if role not in {"supports", "contradicts", "contextualizes"}:
        raise ProjectionError(
            f"Evidence {evidence_id} has invalid public role {role!r}"
        )

    publisher = source.get("publisher")
    source_class = source.get("source_class")
    retrieved_at = document.get("retrieved_at")
    if not isinstance(publisher, Mapping) or not publisher:
        raise ProjectionError(f"Source {source_id} requires publisher metadata")
    if source_class not in {"A", "B", "C", "D", "E"}:
        raise ProjectionError(f"Source {source_id} has invalid source_class")
    if not isinstance(retrieved_at, str) or not retrieved_at:
        raise ProjectionError(f"Document {document_id} requires retrieved_at")

    url = (
        document.get("canonical_url")
        or document.get("retrieved_url")
        or document.get("archival_url")
    )
    return {
        "evidence_id": evidence_id,
        "evidence_role": role,
        "document_id": document_id,
        "source_id": source_id,
        "source_class": source_class,
        "publisher": dict(publisher),
        "document_title": (
            dict(document["title"])
            if isinstance(document.get("title"), Mapping)
            else None
        ),
        "url": url if isinstance(url, str) else None,
        "published_at": (
            dict(document["published_at"])
            if isinstance(document.get("published_at"), Mapping)
            else None
        ),
        "retrieved_at": retrieved_at,
        "locator": dict(locator),
    }


def render_citations(
    links: Any,
    *,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(links, Sequence) or isinstance(links, (str, bytes)) or not links:
        raise ProjectionError(
            "public material record requires at least one Evidence link"
        )
    rendered: list[dict[str, Any]] = []
    for link in links:
        if not isinstance(link, Mapping):
            raise ProjectionError("Evidence link must be an object")
        rendered.append(
            render_citation(
                link,
                evidence_by_id=evidence_by_id,
                documents_by_id=documents_by_id,
                sources_by_id=sources_by_id,
            )
        )
    if not any(item["evidence_role"] == "supports" for item in rendered):
        raise ProjectionError(
            "public material record requires at least one supporting Evidence link"
        )
    rendered.sort(key=lambda item: (item["evidence_id"], item["evidence_role"]))
    return rendered
