"""Cross-record authority and referential checks for M4 AI extraction runs.

JSON Schema owns structural typing. This module owns the boundary between a claimed
editorial queue item and a candidate-only model extraction bundle. It deliberately
does not resolve CAND-* entity mentions to canonical SDA entities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class AIExtractionBoundaryError(ValueError):
    """Raised when an extraction run violates candidate-only authority boundaries."""


def _utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise AIExtractionBoundaryError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise AIExtractionBoundaryError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise AIExtractionBoundaryError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _string_set(value: Any, label: str, *, nonempty: bool = True) -> set[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AIExtractionBoundaryError(f"{label} must be an array")
    rendered: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise AIExtractionBoundaryError(f"{label} contains invalid identity")
        rendered.append(item)
    if nonempty and not rendered:
        raise AIExtractionBoundaryError(f"{label} must not be empty")
    if len(rendered) != len(set(rendered)):
        raise AIExtractionBoundaryError(f"{label} contains duplicate identities")
    return set(rendered)


def _candidate_records(candidates: Mapping[str, Any], name: str) -> list[Mapping[str, Any]]:
    value = candidates.get(name)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise AIExtractionBoundaryError(f"candidates.{name} must be an array")
    rendered: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise AIExtractionBoundaryError(f"candidates.{name} must contain objects")
        rendered.append(item)
    return rendered


def _candidate_ref_id(value: Any, label: str) -> str:
    if not isinstance(value, Mapping) or value.get("kind") != "candidate_entity":
        raise AIExtractionBoundaryError(f"{label} must be a candidate_entity reference")
    candidate_id = value.get("candidate_id")
    if not isinstance(candidate_id, str) or not candidate_id.startswith("CAND-"):
        raise AIExtractionBoundaryError(f"{label} requires CAND-* identity")
    return candidate_id


def validate_ai_extraction_run(
    *,
    queue_item: Mapping[str, Any],
    run: Mapping[str, Any],
) -> None:
    """Fail closed unless an extraction run is safe to enter candidate review."""

    if queue_item.get("lane") != "candidate_extraction":
        raise AIExtractionBoundaryError("AI extraction requires candidate_extraction queue lane")
    if queue_item.get("state") != "claimed":
        raise AIExtractionBoundaryError("AI extraction requires a claimed queue item")
    if queue_item.get("ai_extraction_allowed") is not True:
        raise AIExtractionBoundaryError("queue item does not authorize candidate extraction")
    if queue_item.get("canonical_mutation_authority") is not False:
        raise AIExtractionBoundaryError("queue item must not have canonical mutation authority")

    queue_id = queue_item.get("id")
    if not isinstance(queue_id, str) or run.get("queue_item_id") != queue_id:
        raise AIExtractionBoundaryError("extraction run queue_item_id does not match claimed item")

    queue_documents = _string_set(queue_item.get("document_ids"), "queue document_ids")
    run_documents = _string_set(run.get("source_document_ids"), "run source_document_ids")
    if not run_documents.issubset(queue_documents):
        raise AIExtractionBoundaryError("extraction run references Document outside queue provenance")

    started = _utc(run.get("started_at"), "started_at")
    completed = _utc(run.get("completed_at"), "completed_at")
    if completed < started:
        raise AIExtractionBoundaryError("completed_at precedes started_at")

    authority = run.get("authority")
    if not isinstance(authority, Mapping):
        raise AIExtractionBoundaryError("extraction run requires authority block")
    if (
        authority.get("mode") != "candidate_only"
        or authority.get("canonical_mutation_authority") is not False
        or authority.get("publication_authority") is not False
    ):
        raise AIExtractionBoundaryError("extraction run exceeded candidate-only authority")

    validation = run.get("validation")
    if not isinstance(validation, Mapping):
        raise AIExtractionBoundaryError("extraction run requires validation block")
    status = validation.get("status")
    if status not in {"accepted_for_candidate_review", "rejected"}:
        raise AIExtractionBoundaryError("unknown extraction validation status")

    evaluation = run.get("evaluation_trace")
    if not isinstance(evaluation, Mapping):
        raise AIExtractionBoundaryError("extraction run requires evaluation_trace")
    checks = evaluation.get("checks")
    if not isinstance(checks, Sequence) or isinstance(checks, (str, bytes)) or not checks:
        raise AIExtractionBoundaryError("evaluation_trace.checks must not be empty")
    check_statuses: list[str] = []
    check_ids: set[str] = set()
    for check in checks:
        if not isinstance(check, Mapping):
            raise AIExtractionBoundaryError("evaluation check must be an object")
        check_id = check.get("check_id")
        check_status = check.get("status")
        if not isinstance(check_id, str) or not check_id or check_id in check_ids:
            raise AIExtractionBoundaryError("evaluation check IDs must be unique and non-empty")
        if check_status not in {"pass", "fail"}:
            raise AIExtractionBoundaryError("evaluation check status must be pass/fail")
        check_ids.add(check_id)
        check_statuses.append(check_status)

    candidates = run.get("candidates")
    if not isinstance(candidates, Mapping):
        raise AIExtractionBoundaryError("extraction run requires candidates object")
    evidence = _candidate_records(candidates, "evidence")
    entities = _candidate_records(candidates, "entities")
    claims = _candidate_records(candidates, "claims")
    events = _candidate_records(candidates, "events")

    if status == "rejected":
        if any((evidence, entities, claims, events)):
            raise AIExtractionBoundaryError("rejected extraction run must not expose candidate records")
        if "fail" not in check_statuses:
            raise AIExtractionBoundaryError("rejected extraction run requires failed evaluation check")
        return

    if any(result != "pass" for result in check_statuses):
        raise AIExtractionBoundaryError("accepted extraction run contains failed evaluation check")
    if not any((entities, claims, events)):
        raise AIExtractionBoundaryError("accepted extraction run contains no substantive candidates")

    all_records = [*evidence, *entities, *claims, *events]
    all_ids: set[str] = set()
    for record in all_records:
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id.startswith("CAND-"):
            raise AIExtractionBoundaryError("every candidate record requires CAND-* identity")
        if candidate_id in all_ids:
            raise AIExtractionBoundaryError(f"duplicate candidate identity: {candidate_id}")
        all_ids.add(candidate_id)

    evidence_ids = {str(item["candidate_id"]) for item in evidence}
    entity_ids = {str(item["candidate_id"]) for item in entities}

    for item in evidence:
        document_id = item.get("document_id")
        if document_id not in run_documents:
            raise AIExtractionBoundaryError(
                f"candidate Evidence {item.get('candidate_id')} references out-of-scope Document"
            )

    def require_evidence_refs(record: Mapping[str, Any], label: str) -> None:
        refs = _string_set(record.get("evidence_candidate_ids"), f"{label} evidence_candidate_ids")
        unresolved = refs - evidence_ids
        if unresolved:
            raise AIExtractionBoundaryError(
                f"{label} has unresolved candidate Evidence: {', '.join(sorted(unresolved))}"
            )

    for entity in entities:
        require_evidence_refs(entity, f"Entity {entity.get('candidate_id')}")

    for claim in claims:
        claim_id = claim.get("candidate_id")
        require_evidence_refs(claim, f"Claim {claim_id}")
        subject_id = _candidate_ref_id(claim.get("subject"), f"Claim {claim_id} subject")
        if subject_id not in entity_ids:
            raise AIExtractionBoundaryError(f"Claim {claim_id} has unresolved subject candidate")
        value = claim.get("value")
        if isinstance(value, Mapping) and value.get("kind") == "candidate_entity":
            value_id = _candidate_ref_id(value, f"Claim {claim_id} value")
            if value_id not in entity_ids:
                raise AIExtractionBoundaryError(f"Claim {claim_id} has unresolved value candidate")

    for event in events:
        event_id = event.get("candidate_id")
        require_evidence_refs(event, f"Event {event_id}")
        participants = event.get("participants")
        if not isinstance(participants, Sequence) or isinstance(participants, (str, bytes)):
            raise AIExtractionBoundaryError(f"Event {event_id} participants must be an array")
        for participant in participants:
            if not isinstance(participant, Mapping):
                raise AIExtractionBoundaryError(f"Event {event_id} participant must be an object")
            entity_id = _candidate_ref_id(participant.get("entity"), f"Event {event_id} participant")
            if entity_id not in entity_ids:
                raise AIExtractionBoundaryError(f"Event {event_id} has unresolved participant candidate")
        related = event.get("related_entities")
        if not isinstance(related, Sequence) or isinstance(related, (str, bytes)):
            raise AIExtractionBoundaryError(f"Event {event_id} related_entities must be an array")
        for ref in related:
            entity_id = _candidate_ref_id(ref, f"Event {event_id} related entity")
            if entity_id not in entity_ids:
                raise AIExtractionBoundaryError(f"Event {event_id} has unresolved related candidate")
