"""Policy-driven staleness projection for current canonical SDA Claims.

Staleness indicates that re-verification is due. It is not a truth/falsity
judgment and never supersedes or withdraws a Claim automatically.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timedelta, timezone
from typing import Any


class StalenessError(ValueError):
    """Raised when staleness input or policy is internally inconsistent."""


_VISIBLE_STATES = {"active", "disputed"}


def _parse_utc(value: str, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise StalenessError(f"{label} requires an ISO date-time string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise StalenessError(f"{label} is not a valid ISO date-time") from exc
    if parsed.tzinfo is None:
        raise StalenessError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _positive_days(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise StalenessError(f"{label} must be an integer >= 1")
    return value


def build_staleness_report(
    *,
    claims: Sequence[Mapping[str, Any]],
    as_of: str,
    default_review_days: int,
    predicate_review_days: Mapping[str, int] | None = None,
) -> dict[str, Any]:
    """Return a deterministic review-due report for active/disputed Claims."""

    as_of_dt = _parse_utc(as_of, "as_of")
    default_days = _positive_days(default_review_days, "default_review_days")
    predicate_policy: dict[str, int] = {}
    for predicate_id, days in dict(predicate_review_days or {}).items():
        if not isinstance(predicate_id, str) or not predicate_id:
            raise StalenessError("predicate_review_days keys must be non-empty strings")
        predicate_policy[predicate_id] = _positive_days(
            days, f"predicate_review_days[{predicate_id!r}]"
        )

    seen_ids: set[str] = set()
    items: list[dict[str, Any]] = []

    for claim in claims:
        claim_id = claim.get("id")
        if not isinstance(claim_id, str) or not claim_id:
            raise StalenessError("Claim collection requires canonical IDs")
        if claim_id in seen_ids:
            raise StalenessError(f"duplicate Claim ID in staleness input: {claim_id}")
        seen_ids.add(claim_id)

        if claim.get("claim_state") not in _VISIBLE_STATES:
            continue

        subject_id = claim.get("subject_id")
        predicate_id = claim.get("predicate_id")
        claim_state = claim.get("claim_state")
        confidence = claim.get("confidence")

        if not isinstance(subject_id, str) or not subject_id:
            raise StalenessError(f"Claim {claim_id} requires subject_id")
        if not isinstance(predicate_id, str) or not predicate_id:
            raise StalenessError(f"Claim {claim_id} requires predicate_id")
        if not isinstance(confidence, str) or not confidence:
            raise StalenessError(f"Claim {claim_id} requires confidence")

        review_days = predicate_policy.get(predicate_id, default_days)
        verified_at = claim.get("verified_at")

        if verified_at is None:
            normalized_verified_at = None
            review_due_at = None
            status = "unverified"
            age_days = None
            reason = "Claim has no verified_at timestamp; re-verification is required."
        else:
            verified_dt = _parse_utc(verified_at, f"Claim {claim_id} verified_at")
            if verified_dt > as_of_dt:
                raise StalenessError(
                    f"Claim {claim_id} verified_at occurs after report as_of"
                )
            normalized_verified_at = _format_utc(verified_dt)
            review_due_dt = verified_dt + timedelta(days=review_days)
            review_due_at = _format_utc(review_due_dt)
            elapsed = as_of_dt - verified_dt
            age_days = int(elapsed.total_seconds() // 86400)
            due = as_of_dt >= review_due_dt
            if due:
                status = "due"
                reason = (
                    f"Claim has reached its {review_days}-day review deadline; "
                    "re-verification is due, but the Claim is not automatically false."
                )
            else:
                status = "fresh"
                reason = (
                    f"Claim remains before its {review_days}-day review deadline."
                )

        items.append(
            {
                "claim_id": claim_id,
                "subject_id": subject_id,
                "predicate_id": predicate_id,
                "claim_state": claim_state,
                "confidence": confidence,
                "verified_at": normalized_verified_at,
                "age_days": age_days,
                "review_after_days": review_days,
                "review_due_at": review_due_at,
                "status": status,
                "reason": reason,
            }
        )

    items.sort(key=lambda item: item["claim_id"])
    summary = {
        "total": len(items),
        "fresh": sum(item["status"] == "fresh" for item in items),
        "due": sum(item["status"] == "due" for item in items),
        "unverified": sum(item["status"] == "unverified" for item in items),
    }

    return {
        "as_of": _format_utc(as_of_dt),
        "policy": {
            "default_review_days": default_days,
            "predicate_review_days": dict(sorted(predicate_policy.items())),
        },
        "summary": summary,
        "items": items,
    }
