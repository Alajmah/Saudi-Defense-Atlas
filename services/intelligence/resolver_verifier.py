"""Public deterministic M4 resolver/verifier boundary.

The core implementation in ``_resolver_verifier_core`` carries the reviewed
proposal semantics (originally v0.2), the v0.3 audit correction that preserves
the ambiguous-vs-unresolved distinction downstream, and the v0.4 reconciliation
of ``manufacturer.manufactures.equipment`` target types (equipment or
equipment_variant, per canonical precedent and the designation-typing
convention). Each behavior change bumped the version so resolution-run identity
never reuses a recorded version under different semantics.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ._resolver_verifier_core import (
    ResolverVerifierError,
    build_resolution_verification as _build_core_resolution_verification,
)

_PUBLIC_RESOLVER_VERSION = "resolver-verifier-v0.4"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"


def _candidate_ref_id(value: Any) -> str | None:
    if not isinstance(value, Mapping) or value.get("kind") != "candidate_entity":
        return None
    candidate_id = value.get("candidate_id")
    return candidate_id if isinstance(candidate_id, str) and candidate_id else None


def _claim_entity_refs(candidate: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    subject_id = _candidate_ref_id(candidate.get("subject"))
    value_id = _candidate_ref_id(candidate.get("value"))
    if subject_id is not None:
        refs.add(subject_id)
    if value_id is not None:
        refs.add(value_id)
    return refs


def _event_entity_refs(candidate: Mapping[str, Any]) -> set[str]:
    refs: set[str] = set()
    participants = candidate.get("participants", [])
    if isinstance(participants, Sequence) and not isinstance(participants, (str, bytes)):
        for participant in participants:
            if not isinstance(participant, Mapping):
                continue
            candidate_id = _candidate_ref_id(participant.get("entity"))
            if candidate_id is not None:
                refs.add(candidate_id)
    related = candidate.get("related_entities", [])
    if isinstance(related, Sequence) and not isinstance(related, (str, bytes)):
        for reference in related:
            candidate_id = _candidate_ref_id(reference)
            if candidate_id is not None:
                refs.add(candidate_id)
    return refs


def _records_by_candidate_id(value: Any, label: str) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ResolverVerifierError(f"{label} must be an array")
    result: dict[str, Mapping[str, Any]] = {}
    for record in value:
        if not isinstance(record, Mapping):
            raise ResolverVerifierError(f"{label} must contain objects")
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not candidate_id:
            raise ResolverVerifierError(f"{label} candidate requires id")
        if candidate_id in result:
            raise ResolverVerifierError(f"duplicate {label} candidate id: {candidate_id}")
        result[candidate_id] = record
    return result


def _preserve_ambiguity(
    *,
    run: dict[str, Any],
    extraction_run: Mapping[str, Any],
) -> None:
    ambiguous_ids = {
        item.get("candidate_entity_id")
        for item in run.get("entity_resolutions", [])
        if isinstance(item, Mapping) and item.get("outcome") == "ambiguous"
    }
    ambiguous_ids = {item for item in ambiguous_ids if isinstance(item, str)}
    if not ambiguous_ids:
        return

    candidates = extraction_run.get("candidates")
    if not isinstance(candidates, Mapping):
        raise ResolverVerifierError("extraction run requires candidates")
    claims = _records_by_candidate_id(candidates.get("claims", []), "Claim")
    events = _records_by_candidate_id(candidates.get("events", []), "Event")

    for assessment in run.get("claim_assessments", []):
        if not isinstance(assessment, dict) or assessment.get("outcome") != "blocked_unresolved":
            continue
        candidate_id = assessment.get("candidate_claim_id")
        candidate = claims.get(candidate_id) if isinstance(candidate_id, str) else None
        if candidate is not None and _claim_entity_refs(candidate) & ambiguous_ids:
            assessment["outcome"] = "blocked_ambiguous"

    for assessment in run.get("event_assessments", []):
        if not isinstance(assessment, dict) or assessment.get("outcome") != "blocked_unresolved":
            continue
        candidate_id = assessment.get("candidate_event_id")
        candidate = events.get(candidate_id) if isinstance(candidate_id, str) else None
        if candidate is not None and _event_entity_refs(candidate) & ambiguous_ids:
            assessment["outcome"] = "blocked_ambiguous"


def build_resolution_verification(
    *,
    extraction_run: Mapping[str, Any],
    canonical_entities: Sequence[Mapping[str, Any]],
    canonical_claims: Sequence[Mapping[str, Any]],
    canonical_events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve candidates while preserving ambiguous vs unresolved audit semantics."""

    run, proposal = _build_core_resolution_verification(
        extraction_run=extraction_run,
        canonical_entities=canonical_entities,
        canonical_claims=canonical_claims,
        canonical_events=canonical_events,
    )
    _preserve_ambiguity(run=run, extraction_run=extraction_run)

    extraction_id = run.get("extraction_run_id")
    if not isinstance(extraction_id, str) or not extraction_id:
        raise ResolverVerifierError("resolution run requires extraction_run_id")
    run["resolver_version"] = _PUBLIC_RESOLVER_VERSION
    run["id"] = _stable_id("SDA-AIRV", extraction_id, _PUBLIC_RESOLVER_VERSION)
    return run, proposal


__all__ = ["ResolverVerifierError", "build_resolution_verification"]
