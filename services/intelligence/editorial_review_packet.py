"""Deterministic M4 editorial review-packet construction.

A review packet binds the exact AMBER ChangeProposal payload to the queue,
extraction, resolver/verifier, source-document context, and assessment summary a
human editor must see. It cannot approve, mutate canonical knowledge, or publish.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class EditorialReviewPacketError(ValueError):
    """Raised when the review handoff is incomplete or internally inconsistent."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"


def _utc(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EditorialReviewPacketError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EditorialReviewPacketError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise EditorialReviewPacketError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _string_set(value: Any, label: str, *, nonempty: bool = True) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditorialReviewPacketError(f"{label} must be an array")
    result: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item:
            raise EditorialReviewPacketError(f"{label} must contain non-empty IDs")
        if item in result:
            raise EditorialReviewPacketError(f"{label} contains duplicate ID {item}")
        result.add(item)
    if nonempty and not result:
        raise EditorialReviewPacketError(f"{label} must not be empty")
    return result


def _assessment_ids(
    records: Any,
    *,
    id_field: str,
    outcome: str,
) -> list[str]:
    if not isinstance(records, Sequence) or isinstance(records, (str, bytes)):
        raise EditorialReviewPacketError("resolution assessments must be arrays")
    result: list[str] = []
    for record in records:
        if not isinstance(record, Mapping):
            raise EditorialReviewPacketError("resolution assessment must be an object")
        if record.get("outcome") != outcome:
            continue
        candidate_id = record.get(id_field)
        if not isinstance(candidate_id, str) or not candidate_id:
            raise EditorialReviewPacketError("resolution assessment requires candidate ID")
        result.append(candidate_id)
    return sorted(set(result))


def _require_authority(resolution_run: Mapping[str, Any]) -> None:
    authority = resolution_run.get("authority")
    expected = {
        "mode": "proposal_preparation_only",
        "approval_authority": False,
        "canonical_mutation_authority": False,
        "publication_authority": False,
    }
    if authority != expected:
        raise EditorialReviewPacketError("resolver/verifier authority exceeded proposal-preparation-only boundary")


def build_editorial_review_packet(
    *,
    queue_item: Mapping[str, Any],
    extraction_run: Mapping[str, Any],
    resolution_run: Mapping[str, Any],
    proposal: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Bind one exact resolver proposal into a human-review-only packet."""

    queue_id = queue_item.get("id")
    extraction_id = extraction_run.get("id")
    resolution_id = resolution_run.get("id")
    proposal_id = proposal.get("id")
    for label, value in (
        ("queue item", queue_id),
        ("extraction run", extraction_id),
        ("resolution run", resolution_id),
        ("proposal", proposal_id),
    ):
        if not isinstance(value, str) or not value:
            raise EditorialReviewPacketError(f"{label} requires ID")

    if queue_item.get("lane") != "candidate_extraction":
        raise EditorialReviewPacketError("review packet requires candidate_extraction queue lane")
    if queue_item.get("state") not in {"queued", "claimed"}:
        raise EditorialReviewPacketError("review packet requires an active queue item")
    if queue_item.get("ai_extraction_allowed") is not True:
        raise EditorialReviewPacketError("queue item does not authorize candidate extraction")
    if queue_item.get("canonical_mutation_authority") is not False:
        raise EditorialReviewPacketError("queue item exceeded non-canonical authority")

    if extraction_run.get("queue_item_id") != queue_id:
        raise EditorialReviewPacketError("extraction run does not belong to queue item")
    validation = extraction_run.get("validation")
    if not isinstance(validation, Mapping) or validation.get("status") != "accepted_for_candidate_review":
        raise EditorialReviewPacketError("review packet requires accepted extraction run")
    extraction_authority = extraction_run.get("authority")
    if (
        not isinstance(extraction_authority, Mapping)
        or extraction_authority.get("mode") != "candidate_only"
        or extraction_authority.get("canonical_mutation_authority") is not False
        or extraction_authority.get("publication_authority") is not False
    ):
        raise EditorialReviewPacketError("extraction authority exceeded candidate-only boundary")

    if resolution_run.get("extraction_run_id") != extraction_id:
        raise EditorialReviewPacketError("resolution run does not belong to extraction run")
    if resolution_run.get("change_proposal_id") != proposal_id:
        raise EditorialReviewPacketError("resolution run is not bound to this proposal")
    _require_authority(resolution_run)

    queue_documents = _string_set(queue_item.get("document_ids"), "queue document_ids")
    extraction_documents = _string_set(
        extraction_run.get("source_document_ids"), "extraction source_document_ids"
    )
    proposal_documents = _string_set(proposal.get("source_document_ids"), "proposal source_document_ids")
    if queue_documents != extraction_documents:
        raise EditorialReviewPacketError(
            "multi-source review context must include exactly the queue documents used for extraction"
        )
    if extraction_documents != proposal_documents:
        raise EditorialReviewPacketError("proposal source documents differ from extraction context")

    source_ids = _string_set(queue_item.get("source_ids"), "queue source_ids")
    if proposal.get("risk_class") != "AMBER" or proposal.get("policy_outcome") != "human_review_required":
        raise EditorialReviewPacketError("AI resolver proposal must remain AMBER human-review-required")

    mutations = proposal.get("mutations")
    if not isinstance(mutations, Sequence) or isinstance(mutations, (str, bytes)) or not mutations:
        raise EditorialReviewPacketError("review packet requires non-empty proposal mutations")

    mutation_ids: set[str] = set()
    inventory = {"total": 0, "evidence": 0, "claims": 0, "events": 0}
    evidence_ids: set[str] = set()
    evidence_document_ids: set[str] = set()
    factual_evidence_refs: set[str] = set()

    for mutation in mutations:
        if not isinstance(mutation, Mapping):
            raise EditorialReviewPacketError("proposal mutation must be an object")
        mutation_id = mutation.get("id")
        resource_type = mutation.get("resource_type")
        payload = mutation.get("payload")
        if not isinstance(mutation_id, str) or not mutation_id or mutation_id in mutation_ids:
            raise EditorialReviewPacketError("proposal mutation IDs must be unique and non-empty")
        mutation_ids.add(mutation_id)
        if mutation.get("action") != "create" or resource_type not in {"evidence", "claim", "event"}:
            raise EditorialReviewPacketError("AI review packet accepts create Evidence/Claim/Event mutations only")
        if not isinstance(payload, Mapping):
            raise EditorialReviewPacketError("proposal mutation payload must be an object")

        inventory["total"] += 1
        if resource_type == "evidence":
            inventory["evidence"] += 1
            evidence_id = payload.get("id")
            document_id = payload.get("document_id")
            if not isinstance(evidence_id, str) or not evidence_id:
                raise EditorialReviewPacketError("Evidence mutation requires canonical ID")
            if evidence_id in evidence_ids:
                raise EditorialReviewPacketError("duplicate Evidence payload ID in proposal")
            if not isinstance(document_id, str) or document_id not in extraction_documents:
                raise EditorialReviewPacketError("Evidence mutation escaped extraction document provenance")
            evidence_ids.add(evidence_id)
            evidence_document_ids.add(document_id)
        else:
            inventory["claims" if resource_type == "claim" else "events"] += 1
            links = payload.get("evidence_links")
            if not isinstance(links, Sequence) or isinstance(links, (str, bytes)) or not links:
                raise EditorialReviewPacketError("factual mutation requires Evidence links")
            for link in links:
                if not isinstance(link, Mapping) or link.get("role") != "supports":
                    raise EditorialReviewPacketError("AI factual mutation requires supporting Evidence only")
                evidence_id = link.get("evidence_id")
                if not isinstance(evidence_id, str) or not evidence_id:
                    raise EditorialReviewPacketError("factual mutation has invalid Evidence ID")
                factual_evidence_refs.add(evidence_id)

    if not evidence_ids:
        raise EditorialReviewPacketError("review packet requires materialized Evidence mutations")
    if not factual_evidence_refs.issubset(evidence_ids):
        raise EditorialReviewPacketError("factual mutation references Evidence outside exact proposal")

    claims = resolution_run.get("claim_assessments", [])
    events = resolution_run.get("event_assessments", [])
    summary = {
        "new_claim_candidate_ids": _assessment_ids(claims, id_field="candidate_claim_id", outcome="new"),
        "conflict_claim_candidate_ids": _assessment_ids(claims, id_field="candidate_claim_id", outcome="conflict"),
        "duplicate_claim_candidate_ids": _assessment_ids(claims, id_field="candidate_claim_id", outcome="duplicate"),
        "new_event_candidate_ids": _assessment_ids(events, id_field="candidate_event_id", outcome="new"),
        "possible_duplicate_event_candidate_ids": _assessment_ids(events, id_field="candidate_event_id", outcome="possible_duplicate"),
        "blocked_ambiguous_candidate_ids": sorted(set(
            _assessment_ids(claims, id_field="candidate_claim_id", outcome="blocked_ambiguous")
            + _assessment_ids(events, id_field="candidate_event_id", outcome="blocked_ambiguous")
        )),
        "blocked_unresolved_candidate_ids": sorted(set(
            _assessment_ids(claims, id_field="candidate_claim_id", outcome="blocked_unresolved")
            + _assessment_ids(events, id_field="candidate_event_id", outcome="blocked_unresolved")
        )),
        "blocked_policy_candidate_ids": _assessment_ids(
            claims, id_field="candidate_claim_id", outcome="blocked_policy"
        ),
    }

    flags = {"ai_generated_proposal"}
    if len(extraction_documents) > 1:
        flags.add("multi_source_context")
    if summary["conflict_claim_candidate_ids"]:
        flags.add("conflict_present")
    if summary["blocked_ambiguous_candidate_ids"]:
        flags.add("ambiguity_blocked")
    if summary["blocked_unresolved_candidate_ids"]:
        flags.add("unresolved_entity_blocked")
    if summary["blocked_policy_candidate_ids"]:
        flags.add("policy_blocked")
    if summary["duplicate_claim_candidate_ids"] or summary["possible_duplicate_event_candidate_ids"]:
        flags.add("duplicates_suppressed")

    normalized_created_at = _utc(created_at, "created_at")
    proposal_hash = _sha256(proposal)
    packet = {
        "id": _stable_id("SDA-REVIEW-PACKET", queue_id, extraction_id, resolution_id, proposal_id, proposal_hash),
        "queue_item_id": queue_id,
        "extraction_run_id": extraction_id,
        "resolution_run_id": resolution_id,
        "proposal_id": proposal_id,
        "proposal_sha256": proposal_hash,
        "created_at": normalized_created_at,
        "review_state": "awaiting_human",
        "risk_class": "AMBER",
        "source_ids": sorted(source_ids),
        "source_document_ids": sorted(extraction_documents),
        "evidence_document_ids": sorted(evidence_document_ids),
        "mutation_inventory": inventory,
        "assessment_summary": summary,
        "review_flags": sorted(flags),
        "authority": {
            "mode": "review_handoff_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }
    return packet


__all__ = ["EditorialReviewPacketError", "build_editorial_review_packet"]
