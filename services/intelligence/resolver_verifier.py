"""Deterministic M4 candidate resolver/verifier and AMBER proposal preparation.

This module is deliberately conservative. It performs exact multilingual name/alias
matching only, preserves ambiguity, compares resolved candidate Claims/Events with
canonical records, and may prepare a human-review ChangeProposal. It never approves,
writes canonical knowledge, publishes, or promotes model self-confidence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


class ResolverVerifierError(ValueError):
    """Raised when candidate resolution/verification cannot proceed safely."""


_RESOLVER_VERSION = "resolver-verifier-v0.1"
_EVENT_ROLES = {
    "buyer",
    "seller",
    "contractor",
    "operator",
    "recipient",
    "manufacturer",
    "host",
    "participant",
    "observer",
    "supplier",
    "other",
}
_CANDIDATE_RE = re.compile(r"^CAND-[A-Z0-9][A-Z0-9._-]{0,63}$")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"


def _normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def _sequence(value: Any, label: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ResolverVerifierError(f"{label} must be an array")
    result: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ResolverVerifierError(f"{label} must contain objects")
        result.append(item)
    return result


def _index(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        record_id = record.get("id")
        if not isinstance(record_id, str) or not record_id:
            raise ResolverVerifierError(f"{label} requires canonical id")
        if record_id in result:
            raise ResolverVerifierError(f"duplicate {label} id: {record_id}")
        result[record_id] = record
    return result


def _candidate_index(records: Sequence[Mapping[str, Any]], label: str) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in records:
        candidate_id = record.get("candidate_id")
        if not isinstance(candidate_id, str) or not _CANDIDATE_RE.fullmatch(candidate_id):
            raise ResolverVerifierError(f"{label} requires CAND-* identity")
        if candidate_id in result:
            raise ResolverVerifierError(f"duplicate {label} candidate id: {candidate_id}")
        result[candidate_id] = record
    return result


def _terms(record: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    names: set[str] = set()
    aliases: set[str] = set()
    localized = record.get("names")
    if isinstance(localized, Mapping):
        for value in localized.values():
            if isinstance(value, str) and value.strip():
                names.add(_normalize_text(value))
    raw_aliases = record.get("aliases", [])
    if isinstance(raw_aliases, Sequence) and not isinstance(raw_aliases, (str, bytes)):
        for alias in raw_aliases:
            if isinstance(alias, Mapping):
                value = alias.get("value")
                if isinstance(value, str) and value.strip():
                    aliases.add(_normalize_text(value))
    return names, aliases


def _resolve_entities(
    candidate_entities: Sequence[Mapping[str, Any]],
    canonical_entities: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, str | None]]:
    canonical = [item for item in canonical_entities if item.get("record_status") == "active"]
    resolutions: list[dict[str, Any]] = []
    resolved: dict[str, str | None] = {}

    for candidate in sorted(candidate_entities, key=lambda item: str(item.get("candidate_id"))):
        candidate_id = str(candidate["candidate_id"])
        entity_type = candidate.get("entity_type")
        candidate_names, candidate_aliases = _terms(candidate)
        candidate_all = candidate_names | candidate_aliases
        if not candidate_all:
            raise ResolverVerifierError(f"candidate Entity {candidate_id} has no resolvable name/alias")

        matches: list[tuple[str, str]] = []
        for entity in canonical:
            if entity.get("entity_type") != entity_type:
                continue
            entity_id = entity.get("id")
            if not isinstance(entity_id, str) or not entity_id:
                raise ResolverVerifierError("canonical Entity requires id")
            canonical_names, canonical_aliases = _terms(entity)
            if candidate_names & canonical_names:
                matches.append((entity_id, "exact_name"))
            elif candidate_all & (canonical_names | canonical_aliases):
                matches.append((entity_id, "exact_alias"))

        match_ids = sorted({item[0] for item in matches})
        if len(match_ids) == 1:
            basis = "exact_name" if any(item == (match_ids[0], "exact_name") for item in matches) else "exact_alias"
            resolved[candidate_id] = match_ids[0]
            resolutions.append(
                {
                    "candidate_entity_id": candidate_id,
                    "outcome": "matched",
                    "match_basis": basis,
                    "canonical_entity_id": match_ids[0],
                    "candidate_match_ids": match_ids,
                }
            )
        elif len(match_ids) > 1:
            resolved[candidate_id] = None
            resolutions.append(
                {
                    "candidate_entity_id": candidate_id,
                    "outcome": "ambiguous",
                    "match_basis": "ambiguous_exact",
                    "canonical_entity_id": None,
                    "candidate_match_ids": match_ids,
                }
            )
        else:
            resolved[candidate_id] = None
            resolutions.append(
                {
                    "candidate_entity_id": candidate_id,
                    "outcome": "unresolved",
                    "match_basis": "none",
                    "canonical_entity_id": None,
                    "candidate_match_ids": [],
                }
            )
    return resolutions, resolved


def _candidate_ref(value: Any, resolved: Mapping[str, str | None], label: str) -> str | None:
    if not isinstance(value, Mapping) or value.get("kind") != "candidate_entity":
        raise ResolverVerifierError(f"{label} must be candidate_entity reference")
    candidate_id = value.get("candidate_id")
    if not isinstance(candidate_id, str) or candidate_id not in resolved:
        raise ResolverVerifierError(f"{label} has unknown candidate entity")
    return resolved[candidate_id]


def _resolved_claim_value(value: Any, resolved: Mapping[str, str | None]) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        raise ResolverVerifierError("candidate Claim value must be an object")
    if value.get("kind") == "candidate_entity":
        entity_id = _candidate_ref(value, resolved, "candidate Claim value")
        if entity_id is None:
            return None
        return {"kind": "entity", "entity_id": entity_id}
    return copy.deepcopy(dict(value))


def _claim_assessments(
    candidate_claims: Sequence[Mapping[str, Any]],
    canonical_claims: Sequence[Mapping[str, Any]],
    resolved: Mapping[str, str | None],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any] | None]]:
    assessments: list[dict[str, Any]] = []
    prepared: dict[str, dict[str, Any] | None] = {}

    for candidate in sorted(candidate_claims, key=lambda item: str(item.get("candidate_id"))):
        candidate_id = str(candidate["candidate_id"])
        subject = _candidate_ref(candidate.get("subject"), resolved, f"Claim {candidate_id} subject")
        value = _resolved_claim_value(candidate.get("value"), resolved)
        if subject is None or value is None:
            assessments.append(
                {"candidate_claim_id": candidate_id, "outcome": "blocked_unresolved", "canonical_claim_ids": []}
            )
            prepared[candidate_id] = None
            continue

        predicate = candidate.get("predicate_id")
        relevant = [
            claim
            for claim in canonical_claims
            if claim.get("subject_id") == subject
            and claim.get("predicate_id") == predicate
            and claim.get("claim_state") in {"active", "disputed"}
        ]
        same = sorted(
            str(claim["id"])
            for claim in relevant
            if _stable_json(claim.get("value")) == _stable_json(value)
        )
        if same:
            assessments.append(
                {"candidate_claim_id": candidate_id, "outcome": "duplicate", "canonical_claim_ids": same}
            )
            prepared[candidate_id] = None
            continue

        conflicts = sorted(str(claim["id"]) for claim in relevant)
        outcome = "conflict" if conflicts else "new"
        assessments.append(
            {"candidate_claim_id": candidate_id, "outcome": outcome, "canonical_claim_ids": conflicts}
        )
        prepared[candidate_id] = {
            "subject_id": subject,
            "predicate_id": predicate,
            "value": value,
            "validity": copy.deepcopy(candidate.get("validity")),
            "claim_state": "disputed" if outcome == "conflict" else "active",
        }

    return assessments, prepared


def _event_signature(event: Mapping[str, Any]) -> str:
    participants = event.get("participants", [])
    normalized_participants = sorted(
        (str(item.get("entity_id")), str(item.get("role")))
        for item in participants
        if isinstance(item, Mapping)
    )
    related = sorted(str(item) for item in event.get("related_entity_ids", []))
    return _stable_json(
        {
            "event_type": event.get("event_type"),
            "occurred_at": event.get("occurred_at"),
            "ended_at": event.get("ended_at"),
            "participants": normalized_participants,
            "related_entity_ids": related,
        }
    )


def _event_assessments(
    candidate_events: Sequence[Mapping[str, Any]],
    canonical_events: Sequence[Mapping[str, Any]],
    resolved: Mapping[str, str | None],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any] | None]]:
    by_signature: dict[str, list[str]] = {}
    for event in canonical_events:
        event_id = event.get("id")
        if not isinstance(event_id, str) or not event_id:
            raise ResolverVerifierError("canonical Event requires id")
        by_signature.setdefault(_event_signature(event), []).append(event_id)

    assessments: list[dict[str, Any]] = []
    prepared: dict[str, dict[str, Any] | None] = {}

    for candidate in sorted(candidate_events, key=lambda item: str(item.get("candidate_id"))):
        candidate_id = str(candidate["candidate_id"])
        participants: list[dict[str, str]] = []
        blocked = False
        for item in _sequence(candidate.get("participants", []), f"Event {candidate_id} participants"):
            role = item.get("role")
            if role not in _EVENT_ROLES:
                raise ResolverVerifierError(f"Event {candidate_id} uses unsupported participant role {role!r}")
            entity_id = _candidate_ref(item.get("entity"), resolved, f"Event {candidate_id} participant")
            if entity_id is None:
                blocked = True
            else:
                participants.append({"entity_id": entity_id, "role": str(role)})

        related_ids: list[str] = []
        related = candidate.get("related_entities", [])
        if not isinstance(related, Sequence) or isinstance(related, (str, bytes)):
            raise ResolverVerifierError(f"Event {candidate_id} related_entities must be array")
        for ref in related:
            entity_id = _candidate_ref(ref, resolved, f"Event {candidate_id} related entity")
            if entity_id is None:
                blocked = True
            else:
                related_ids.append(entity_id)

        if blocked:
            assessments.append(
                {"candidate_event_id": candidate_id, "outcome": "blocked_unresolved", "canonical_event_ids": []}
            )
            prepared[candidate_id] = None
            continue

        event_payload = {
            "event_type": candidate.get("event_type"),
            "occurred_at": copy.deepcopy(candidate.get("occurred_at")),
            "ended_at": copy.deepcopy(candidate.get("ended_at")),
            "participants": sorted(participants, key=lambda item: (item["entity_id"], item["role"])),
            "related_entity_ids": sorted(set(related_ids)),
        }
        signature = _event_signature(event_payload)
        duplicates = sorted(by_signature.get(signature, []))
        if duplicates:
            assessments.append(
                {"candidate_event_id": candidate_id, "outcome": "duplicate", "canonical_event_ids": duplicates}
            )
            prepared[candidate_id] = None
        else:
            assessments.append(
                {"candidate_event_id": candidate_id, "outcome": "new", "canonical_event_ids": []}
            )
            prepared[candidate_id] = event_payload

    return assessments, prepared


def _materialize_evidence(
    extraction_run: Mapping[str, Any],
    used_candidate_evidence_ids: set[str],
) -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    candidates = extraction_run.get("candidates")
    if not isinstance(candidates, Mapping):
        raise ResolverVerifierError("extraction run requires candidates")
    evidence_records = _candidate_index(_sequence(candidates.get("evidence", []), "candidate evidence"), "Evidence")
    completed_at = extraction_run.get("completed_at")
    if not isinstance(completed_at, str) or not completed_at:
        raise ResolverVerifierError("extraction run requires completed_at")

    materialized: dict[str, dict[str, Any]] = {}
    id_map: dict[str, str] = {}
    for candidate_id in sorted(used_candidate_evidence_ids):
        candidate = evidence_records.get(candidate_id)
        if candidate is None:
            raise ResolverVerifierError(f"unresolved candidate Evidence {candidate_id}")
        evidence_id = _stable_id("SDA-EVID-AI", extraction_run.get("id"), candidate_id)
        id_map[candidate_id] = evidence_id
        materialized[candidate_id] = {
            "id": evidence_id,
            "document_id": candidate.get("document_id"),
            "locator": copy.deepcopy(candidate.get("locator")),
            "excerpt": None,
            "excerpt_sha256": candidate.get("excerpt_sha256"),
            "language": None,
            "captured_at": completed_at,
            "capture_method": "model_extraction",
            "notes": f"Materialized from {extraction_run.get('id')} candidate {candidate_id}; factual admission remains review-gated.",
        }
    return materialized, id_map


def build_resolution_verification(
    *,
    extraction_run: Mapping[str, Any],
    canonical_entities: Sequence[Mapping[str, Any]],
    canonical_claims: Sequence[Mapping[str, Any]],
    canonical_events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve an accepted extraction run and prepare at most one AMBER proposal."""

    validation = extraction_run.get("validation")
    authority = extraction_run.get("authority")
    if not isinstance(validation, Mapping) or validation.get("status") != "accepted_for_candidate_review":
        raise ResolverVerifierError("resolver requires accepted extraction run")
    if not isinstance(authority, Mapping) or authority.get("mode") != "candidate_only":
        raise ResolverVerifierError("resolver requires candidate-only extraction authority")
    if authority.get("canonical_mutation_authority") is not False or authority.get("publication_authority") is not False:
        raise ResolverVerifierError("extraction run exceeded candidate-only authority")

    extraction_id = extraction_run.get("id")
    completed_at = extraction_run.get("completed_at")
    if not isinstance(extraction_id, str) or not extraction_id:
        raise ResolverVerifierError("extraction run requires id")
    if not isinstance(completed_at, str) or not completed_at:
        raise ResolverVerifierError("extraction run requires completed_at")

    _index(canonical_entities, "Entity")
    _index(canonical_claims, "Claim")
    _index(canonical_events, "Event")

    candidates = extraction_run.get("candidates")
    if not isinstance(candidates, Mapping):
        raise ResolverVerifierError("extraction run requires candidates")
    candidate_entities = _sequence(candidates.get("entities", []), "candidate entities")
    candidate_claims = _sequence(candidates.get("claims", []), "candidate claims")
    candidate_events = _sequence(candidates.get("events", []), "candidate events")
    _candidate_index(candidate_entities, "Entity")
    _candidate_index(candidate_claims, "Claim")
    _candidate_index(candidate_events, "Event")

    entity_resolutions, resolved = _resolve_entities(candidate_entities, canonical_entities)
    claim_assessments, prepared_claims = _claim_assessments(candidate_claims, canonical_claims, resolved)
    event_assessments, prepared_events = _event_assessments(candidate_events, canonical_events, resolved)

    claim_by_id = _candidate_index(candidate_claims, "Claim")
    event_by_id = _candidate_index(candidate_events, "Event")
    used_evidence: set[str] = set()
    for candidate_id, prepared in prepared_claims.items():
        if prepared is not None:
            refs = claim_by_id[candidate_id].get("evidence_candidate_ids", [])
            used_evidence.update(str(item) for item in refs)
    for candidate_id, prepared in prepared_events.items():
        if prepared is not None:
            refs = event_by_id[candidate_id].get("evidence_candidate_ids", [])
            used_evidence.update(str(item) for item in refs)

    evidence_payloads, evidence_id_map = _materialize_evidence(extraction_run, used_evidence)
    mutations: list[dict[str, Any]] = []
    for candidate_id in sorted(evidence_payloads):
        payload = evidence_payloads[candidate_id]
        mutations.append(
            {
                "id": _stable_id("SDA-MUT-AI", extraction_id, "evidence", candidate_id),
                "action": "create",
                "resource_type": "evidence",
                "payload": payload,
            }
        )

    conflict_present = False
    assessment_by_claim = {item["candidate_claim_id"]: item for item in claim_assessments}
    for candidate_id in sorted(prepared_claims):
        prepared = prepared_claims[candidate_id]
        if prepared is None:
            continue
        candidate = claim_by_id[candidate_id]
        assessment = assessment_by_claim[candidate_id]
        conflict_present = conflict_present or assessment["outcome"] == "conflict"
        claim_id = _stable_id("SDA-CLAIM-AI", extraction_id, candidate_id)
        evidence_links = [
            {"evidence_id": evidence_id_map[str(item)], "role": "supports"}
            for item in candidate.get("evidence_candidate_ids", [])
        ]
        payload: dict[str, Any] = {
            "id": claim_id,
            "subject_id": prepared["subject_id"],
            "predicate_id": prepared["predicate_id"],
            "value": prepared["value"],
            "confidence": "unverified",
            "evidence_links": evidence_links,
            "claim_state": prepared["claim_state"],
            "supersedes_claim_ids": [],
            "verified_at": None,
            "created_at": completed_at,
        }
        if prepared.get("validity") is not None:
            payload["validity"] = prepared["validity"]
        mutations.append(
            {
                "id": _stable_id("SDA-MUT-AI", extraction_id, "claim", candidate_id),
                "action": "create",
                "resource_type": "claim",
                "payload": payload,
            }
        )

    for candidate_id in sorted(prepared_events):
        prepared = prepared_events[candidate_id]
        if prepared is None:
            continue
        candidate = event_by_id[candidate_id]
        event_id = _stable_id("SDA-EVENT-AI", extraction_id, candidate_id)
        payload = {
            "id": event_id,
            "event_type": prepared["event_type"],
            "occurred_at": prepared["occurred_at"],
            "participants": prepared["participants"],
            "related_entity_ids": prepared["related_entity_ids"],
            "related_claim_ids": [],
            "confidence": "unverified",
            "evidence_links": [
                {"evidence_id": evidence_id_map[str(item)], "role": "supports"}
                for item in candidate.get("evidence_candidate_ids", [])
            ],
            "notes": f"Prepared from {extraction_id}; human review required before canonical admission.",
            "created_at": completed_at,
        }
        if prepared.get("ended_at") is not None:
            payload["ended_at"] = prepared["ended_at"]
        mutations.append(
            {
                "id": _stable_id("SDA-MUT-AI", extraction_id, "event", candidate_id),
                "action": "create",
                "resource_type": "event",
                "payload": payload,
            }
        )

    proposal: dict[str, Any] | None = None
    proposal_id: str | None = None
    if mutations:
        proposal_id = _stable_id("SDA-PROP-AI", extraction_id, mutations)
        reasons = ["ai_candidate_requires_human_review", "resolver_verifier_has_no_approval_authority"]
        if conflict_present:
            reasons.append("conflicting_canonical_claim_preserved")
        proposal = {
            "id": proposal_id,
            "created_at": completed_at,
            "created_by": {"kind": "system", "id": "m4-resolver-verifier"},
            "source_document_ids": sorted(set(str(item) for item in extraction_run.get("source_document_ids", []))),
            "risk_class": "AMBER",
            "policy_outcome": "human_review_required",
            "policy_reasons": reasons,
            "rationale": "Deterministically resolved AI candidates; canonical admission requires independent human review.",
            "supersedes_proposal_id": None,
            "mutations": mutations,
        }

    run = {
        "id": _stable_id("SDA-AIRV", extraction_id, _RESOLVER_VERSION),
        "extraction_run_id": extraction_id,
        "created_at": completed_at,
        "resolver_version": _RESOLVER_VERSION,
        "authority": {
            "mode": "proposal_preparation_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "entity_resolutions": entity_resolutions,
        "claim_assessments": claim_assessments,
        "event_assessments": event_assessments,
        "change_proposal_id": proposal_id,
    }
    return run, proposal
