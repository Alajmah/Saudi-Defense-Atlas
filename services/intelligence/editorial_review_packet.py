"""Public M4 editorial review-packet boundary with first-pass hardening."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any

from ._editorial_review_packet_core import (
    EditorialReviewPacketError,
    build_editorial_review_packet as _build_core_packet,
)


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EditorialReviewPacketError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EditorialReviewPacketError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise EditorialReviewPacketError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _verify_temporal_order(
    *,
    queue_item: Mapping[str, Any],
    extraction_run: Mapping[str, Any],
    resolution_run: Mapping[str, Any],
    proposal: Mapping[str, Any],
    created_at: str,
) -> None:
    queue_created = _parse_datetime(queue_item.get("created_at"), "queue created_at")
    extraction_started = _parse_datetime(
        extraction_run.get("started_at"), "extraction started_at"
    )
    extraction_completed = _parse_datetime(
        extraction_run.get("completed_at"), "extraction completed_at"
    )
    resolution_created = _parse_datetime(
        resolution_run.get("created_at"), "resolution created_at"
    )
    proposal_created = _parse_datetime(proposal.get("created_at"), "proposal created_at")
    packet_created = _parse_datetime(created_at, "review packet created_at")

    if queue_created > extraction_started:
        raise EditorialReviewPacketError("queue item must exist before extraction starts")
    if extraction_started > extraction_completed:
        raise EditorialReviewPacketError("extraction started_at cannot postdate completed_at")
    if resolution_created < extraction_completed:
        raise EditorialReviewPacketError("resolution run cannot predate completed extraction")
    if proposal_created < extraction_completed:
        raise EditorialReviewPacketError("proposal cannot predate completed extraction")
    if packet_created < max(extraction_completed, resolution_created, proposal_created):
        raise EditorialReviewPacketError("review packet cannot predate its upstream artifacts")


def _verify_deterministic_proposal_identity(
    extraction_run: Mapping[str, Any], proposal: Mapping[str, Any]
) -> None:
    extraction_id = extraction_run.get("id")
    mutations = proposal.get("mutations")
    if not isinstance(extraction_id, str) or not extraction_id:
        raise EditorialReviewPacketError("extraction run requires ID")
    if not isinstance(mutations, Sequence) or isinstance(mutations, (str, bytes)):
        raise EditorialReviewPacketError("proposal mutations must be an array")
    expected_id = _stable_id("SDA-PROP-AI", extraction_id, mutations)
    if proposal.get("id") != expected_id:
        raise EditorialReviewPacketError(
            "proposal ID does not bind the exact resolver mutation payload"
        )


def _resolution_entity_ids(
    resolution_run: Mapping[str, Any], outcome: str
) -> list[str]:
    records = resolution_run.get("entity_resolutions")
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise EditorialReviewPacketError("entity_resolutions must be an array")
    result: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise EditorialReviewPacketError("entity resolution must be an object")
        if record.get("outcome") != outcome:
            continue
        candidate_id = record.get("candidate_entity_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise EditorialReviewPacketError("entity resolution requires candidate ID")
        result.append(candidate_id)
    return sorted(set(result))


def build_editorial_review_packet(
    *,
    queue_item: Mapping[str, Any],
    extraction_run: Mapping[str, Any],
    resolution_run: Mapping[str, Any],
    proposal: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Build a content-bound, temporally valid, human-review-only packet."""

    _verify_temporal_order(
        queue_item=queue_item,
        extraction_run=extraction_run,
        resolution_run=resolution_run,
        proposal=proposal,
        created_at=created_at,
    )
    _verify_deterministic_proposal_identity(extraction_run, proposal)

    packet = _build_core_packet(
        queue_item=queue_item,
        extraction_run=extraction_run,
        resolution_run=resolution_run,
        proposal=proposal,
        created_at=created_at,
    )

    summary = packet.get("assessment_summary")
    if not isinstance(summary, dict):
        raise EditorialReviewPacketError("review packet requires assessment_summary")
    ambiguous_entities = _resolution_entity_ids(resolution_run, "ambiguous")
    unresolved_entities = _resolution_entity_ids(resolution_run, "unresolved")

    summary["blocked_ambiguous_candidate_ids"] = sorted(
        set(summary.get("blocked_ambiguous_candidate_ids", [])) | set(ambiguous_entities)
    )
    summary["blocked_unresolved_candidate_ids"] = sorted(
        set(summary.get("blocked_unresolved_candidate_ids", [])) | set(unresolved_entities)
    )

    flags = set(packet.get("review_flags", []))
    if ambiguous_entities:
        flags.add("ambiguity_blocked")
    if unresolved_entities:
        flags.add("unresolved_entity_blocked")
    packet["review_flags"] = sorted(flags)

    # The final packet identity is content-addressed after all review context is
    # attached, so a changed assessment summary cannot reuse an old packet ID.
    packet_without_id = {key: value for key, value in packet.items() if key != "id"}
    packet["id"] = _stable_id("SDA-REVIEW-PACKET", packet_without_id)
    return packet


__all__ = ["EditorialReviewPacketError", "build_editorial_review_packet"]