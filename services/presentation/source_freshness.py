"""Policy-driven acquisition freshness for registered SDA sources.

This module reports monitoring/retrieval health only. A source being due does
not mean the source is unreliable, that its content is stale, or that any SDA
Claim is false. Claim re-verification remains a separate concern.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any


class SourceFreshnessError(ValueError):
    """Raised when source/document freshness inputs are inconsistent."""


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise SourceFreshnessError(f"{label} requires an ISO date-time string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SourceFreshnessError(f"{label} is not a valid ISO date-time") from exc
    if parsed.tzinfo is None:
        raise SourceFreshnessError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_days(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise SourceFreshnessError(f"{label} must be an integer >= 1")
    return value


def build_source_freshness_report(
    *,
    sources: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    as_of: str,
    default_poll_days: int,
    source_poll_days: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Return deterministic acquisition freshness for active registered Sources."""

    as_of_dt = _parse_utc(as_of, "as_of")
    default_days = _positive_days(default_poll_days, "default_poll_days")

    policy: dict[str, int] = {}
    for source_id, days in dict(source_poll_days or {}).items():
        if not isinstance(source_id, str) or not source_id:
            raise SourceFreshnessError("source_poll_days keys must be canonical source IDs")
        policy[source_id] = _positive_days(days, f"source_poll_days[{source_id!r}]")

    source_by_id: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            raise SourceFreshnessError("Source requires canonical ID")
        if source_id in source_by_id:
            raise SourceFreshnessError(f"duplicate Source ID: {source_id}")
        source_by_id[source_id] = source

    unknown_policy = sorted(set(policy) - set(source_by_id))
    if unknown_policy:
        raise SourceFreshnessError(
            "source polling policy references unknown Sources: " + ", ".join(unknown_policy)
        )

    documents_by_source: dict[str, list[tuple[datetime, str]]] = {
        source_id: [] for source_id in source_by_id
    }
    seen_documents: set[str] = set()
    for document in documents:
        document_id = document.get("id")
        source_id = document.get("source_id")
        if not isinstance(document_id, str) or not document_id:
            raise SourceFreshnessError("Document requires canonical ID")
        if document_id in seen_documents:
            raise SourceFreshnessError(f"duplicate Document ID: {document_id}")
        seen_documents.add(document_id)
        if not isinstance(source_id, str) or source_id not in source_by_id:
            raise SourceFreshnessError(
                f"Document {document_id} references unknown Source {source_id!r}"
            )
        retrieved_dt = _parse_utc(
            document.get("retrieved_at"), f"Document {document_id} retrieved_at"
        )
        if retrieved_dt > as_of_dt:
            raise SourceFreshnessError(
                f"Document {document_id} retrieved_at occurs after report as_of"
            )
        documents_by_source[source_id].append((retrieved_dt, document_id))

    items: list[dict[str, Any]] = []
    for source_id in sorted(source_by_id):
        source = source_by_id[source_id]
        if source.get("active", True) is not True:
            continue

        publisher = source.get("publisher")
        source_class = source.get("source_class")
        if not isinstance(publisher, Mapping) or not publisher:
            raise SourceFreshnessError(f"Source {source_id} requires publisher metadata")
        if source_class not in {"A", "B", "C", "D", "E"}:
            raise SourceFreshnessError(f"Source {source_id} has invalid source_class")

        poll_days = policy.get(source_id, default_days)
        source_documents = documents_by_source[source_id]
        if not source_documents:
            items.append(
                {
                    "source_id": source_id,
                    "publisher": dict(publisher),
                    "source_class": source_class,
                    "document_count": 0,
                    "latest_document_id": None,
                    "latest_retrieved_at": None,
                    "age_days": None,
                    "poll_after_days": poll_days,
                    "next_retrieval_due_at": None,
                    "status": "never_retrieved",
                    "reason": (
                        "No Document retrieval is recorded for this active Source; "
                        "acquisition coverage has not yet been demonstrated."
                    ),
                }
            )
            continue

        latest_dt, latest_document_id = max(
            source_documents, key=lambda value: (value[0], value[1])
        )
        due_at = latest_dt + timedelta(days=poll_days)
        age_days = int((as_of_dt - latest_dt).total_seconds() // 86400)
        status = "due" if as_of_dt >= due_at else "fresh"
        reason = (
            f"Source retrieval has reached its {poll_days}-day polling deadline; "
            "a new acquisition check is due. This does not imply factual staleness."
            if status == "due"
            else f"Source retrieval remains within its {poll_days}-day polling window."
        )
        items.append(
            {
                "source_id": source_id,
                "publisher": dict(publisher),
                "source_class": source_class,
                "document_count": len(source_documents),
                "latest_document_id": latest_document_id,
                "latest_retrieved_at": _format_utc(latest_dt),
                "age_days": age_days,
                "poll_after_days": poll_days,
                "next_retrieval_due_at": _format_utc(due_at),
                "status": status,
                "reason": reason,
            }
        )

    summary = {
        "total": len(items),
        "fresh": sum(item["status"] == "fresh" for item in items),
        "due": sum(item["status"] == "due" for item in items),
        "never_retrieved": sum(item["status"] == "never_retrieved" for item in items),
    }
    return {
        "as_of": _format_utc(as_of_dt),
        "policy": {
            "default_poll_days": default_days,
            "source_poll_days": dict(sorted(policy.items())),
        },
        "summary": summary,
        "items": items,
    }
