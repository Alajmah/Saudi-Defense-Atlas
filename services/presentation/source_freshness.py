"""Policy-driven acquisition freshness for registered SDA feeds.

Freshness is based on successful retrieval receipts, not Document creation.
An unchanged re-fetch therefore refreshes acquisition health without mutating
canonical Document identity. `due` never implies that source content or SDA
Claims are stale or false.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any


class SourceFreshnessError(ValueError):
    """Raised when source/feed/receipt freshness inputs are inconsistent."""


def _field(record: Any, name: str) -> Any:
    if isinstance(record, Mapping):
        return record.get(name)
    return getattr(record, name, None)


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
    feeds: Sequence[Any],
    retrieval_receipts: Sequence[Any],
    as_of: str,
    default_poll_days: int,
    feed_poll_days: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Return deterministic acquisition freshness for active registered feeds."""

    as_of_dt = _parse_utc(as_of, "as_of")
    default_days = _positive_days(default_poll_days, "default_poll_days")

    source_by_id: dict[str, Mapping[str, Any]] = {}
    for source in sources:
        source_id = source.get("id")
        if not isinstance(source_id, str) or not source_id:
            raise SourceFreshnessError("Source requires canonical ID")
        if source_id in source_by_id:
            raise SourceFreshnessError(f"duplicate Source ID: {source_id}")
        source_by_id[source_id] = source

    feed_by_key: dict[str, tuple[str, Any]] = {}
    for index, feed in enumerate(feeds):
        source_id = _field(feed, "source_id")
        feed_key = _field(feed, "document_key")
        if not isinstance(source_id, str) or source_id not in source_by_id:
            raise SourceFreshnessError(
                f"registered feed {index} references unknown Source {source_id!r}"
            )
        if not isinstance(feed_key, str) or not feed_key:
            raise SourceFreshnessError(f"registered feed {index} requires document_key")
        if feed_key in feed_by_key:
            raise SourceFreshnessError(f"duplicate registered feed key: {feed_key}")
        feed_by_key[feed_key] = (source_id, feed)

    policy: dict[str, int] = {}
    for feed_key, days in dict(feed_poll_days or {}).items():
        if not isinstance(feed_key, str) or not feed_key:
            raise SourceFreshnessError("feed_poll_days keys must be registered feed keys")
        if feed_key not in feed_by_key:
            raise SourceFreshnessError(
                f"feed polling policy references unknown feed: {feed_key}"
            )
        policy[feed_key] = _positive_days(days, f"feed_poll_days[{feed_key!r}]")

    receipts_by_feed: dict[str, list[datetime]] = {feed_key: [] for feed_key in feed_by_key}
    for index, receipt in enumerate(retrieval_receipts):
        source_id = _field(receipt, "source_id")
        feed_key = _field(receipt, "document_key")
        observed_at = _field(receipt, "observed_at")
        status_code = _field(receipt, "status_code")
        if not isinstance(feed_key, str) or feed_key not in feed_by_key:
            raise SourceFreshnessError(
                f"retrieval receipt {index} references unknown feed {feed_key!r}"
            )
        expected_source_id = feed_by_key[feed_key][0]
        if source_id != expected_source_id:
            raise SourceFreshnessError(
                f"retrieval receipt {index} source/feed identity mismatch"
            )
        if status_code != 200:
            raise SourceFreshnessError(
                f"retrieval receipt {index} is not a successful HTTP 200 observation"
            )
        observed_dt = _parse_utc(observed_at, f"retrieval receipt {index} observed_at")
        if observed_dt > as_of_dt:
            raise SourceFreshnessError(
                f"retrieval receipt {index} observed_at occurs after report as_of"
            )
        receipts_by_feed[feed_key].append(observed_dt)

    items: list[dict[str, Any]] = []
    for feed_key in sorted(feed_by_key):
        source_id, _feed = feed_by_key[feed_key]
        source = source_by_id[source_id]
        if source.get("active", True) is not True:
            continue

        publisher = source.get("publisher")
        source_class = source.get("source_class")
        if not isinstance(publisher, Mapping) or not publisher:
            raise SourceFreshnessError(f"Source {source_id} requires publisher metadata")
        if source_class not in {"A", "B", "C", "D", "E"}:
            raise SourceFreshnessError(f"Source {source_id} has invalid source_class")

        poll_days = policy.get(feed_key, default_days)
        feed_receipts = receipts_by_feed[feed_key]
        if not feed_receipts:
            items.append(
                {
                    "source_id": source_id,
                    "feed_key": feed_key,
                    "publisher": dict(publisher),
                    "source_class": source_class,
                    "receipt_count": 0,
                    "latest_observed_at": None,
                    "age_days": None,
                    "poll_after_days": poll_days,
                    "next_check_due_at": None,
                    "status": "never_retrieved",
                    "reason": (
                        "No successful retrieval receipt is recorded for this registered feed; "
                        "acquisition coverage has not yet been demonstrated."
                    ),
                }
            )
            continue

        latest_dt = max(feed_receipts)
        due_at = latest_dt + timedelta(days=poll_days)
        age_days = int((as_of_dt - latest_dt).total_seconds() // 86400)
        status = "due" if as_of_dt >= due_at else "fresh"
        reason = (
            f"The last successful feed retrieval has reached its {poll_days}-day polling "
            "deadline; a new acquisition check is due. This does not imply factual staleness."
            if status == "due"
            else f"The last successful feed retrieval remains within its {poll_days}-day polling window."
        )
        items.append(
            {
                "source_id": source_id,
                "feed_key": feed_key,
                "publisher": dict(publisher),
                "source_class": source_class,
                "receipt_count": len(feed_receipts),
                "latest_observed_at": _format_utc(latest_dt),
                "age_days": age_days,
                "poll_after_days": poll_days,
                "next_check_due_at": _format_utc(due_at),
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
            "feed_poll_days": dict(sorted(policy.items())),
        },
        "summary": summary,
        "items": items,
    }
