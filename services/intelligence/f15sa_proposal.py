"""Build the first M1 typed proposal from deterministic evidence.

This module owns no entity-resolution or canonical-write authority. Callers must
supply already-resolved SDA entity IDs and an immutable Source/Document/Evidence
bundle. The result is an AMBER ChangeProposal requiring human review.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Sequence


class ProposalBuildError(ValueError):
    """Raised when required resolved identities/evidence are incomplete."""


@dataclass(frozen=True)
class ResolvedF15SAEntities:
    rsaf_id: str
    f15sa_id: str
    boeing_id: str

    def validate(self) -> None:
        for label, value in (
            ("rsaf_id", self.rsaf_id),
            ("f15sa_id", self.f15sa_id),
            ("boeing_id", self.boeing_id),
        ):
            if not value or not value.startswith("SDA-"):
                raise ProposalBuildError(f"{label} must be a resolved SDA canonical ID")
        if len({self.rsaf_id, self.f15sa_id, self.boeing_id}) != 3:
            raise ProposalBuildError("resolved entities must be distinct")


def _stable_suffix(payload: Mapping[str, Any], length: int = 20) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:length].upper()


def _evidence_by_label(evidence: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    result: dict[str, Mapping[str, Any]] = {}
    for record in evidence:
        locator = record.get("locator")
        label = locator.get("fragment") if isinstance(locator, Mapping) else None
        if not isinstance(label, str) or not label:
            raise ProposalBuildError("every Evidence record must expose locator.fragment")
        if label in result:
            raise ProposalBuildError(f"duplicate Evidence fragment label: {label}")
        result[label] = record
    required = {
        "publication-date",
        "final-delivery",
        "variant-context",
        "manufacturer-context",
    }
    missing = sorted(required - result.keys())
    if missing:
        raise ProposalBuildError(f"missing required Evidence: {', '.join(missing)}")
    return result


def build_f15sa_proposal(
    *,
    source_record: Mapping[str, Any],
    document_record: Mapping[str, Any],
    evidence_records: Sequence[Mapping[str, Any]],
    resolved: ResolvedF15SAEntities,
    published_date: str,
    delivery_date: str,
    created_at: str,
) -> dict[str, Any]:
    """Return one schema-oriented AMBER ChangeProposal for the first M1 slice."""
    resolved.validate()
    evidence = _evidence_by_label(evidence_records)

    source_id = str(source_record.get("id", ""))
    document_id = str(document_record.get("id", ""))
    if not source_id or document_record.get("source_id") != source_id:
        raise ProposalBuildError("Document must reference the supplied Source")
    for record in evidence_records:
        if record.get("document_id") != document_id:
            raise ProposalBuildError("all Evidence must reference the supplied Document")

    delivery_evidence_id = str(evidence["final-delivery"]["id"])
    manufacturer_evidence_id = str(evidence["manufacturer-context"]["id"])

    manufacturer_claim_seed = {
        "subject_id": resolved.boeing_id,
        "predicate_id": "manufacturer.manufactures.equipment",
        "object_id": resolved.f15sa_id,
        "point_in_time": published_date,
        "evidence_id": manufacturer_evidence_id,
    }
    manufacturer_claim_id = f"SDA-CLAIM-{_stable_suffix(manufacturer_claim_seed)}"
    manufacturer_claim = {
        "id": manufacturer_claim_id,
        "subject_id": resolved.boeing_id,
        "predicate_id": "manufacturer.manufactures.equipment",
        "value": {"kind": "entity", "entity_id": resolved.f15sa_id},
        "scope": {"entity_ids": [resolved.f15sa_id], "quantity_type": None, "note": None},
        "validity": {
            "point_in_time": {"value": published_date, "precision": "day"}
        },
        "confidence": "high",
        "evidence_links": [
            {"evidence_id": manufacturer_evidence_id, "role": "supports"}
        ],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": None,
        "created_at": created_at,
    }

    event_seed = {
        "event_type": "delivery",
        "date": delivery_date,
        "equipment": resolved.f15sa_id,
        "recipient": resolved.rsaf_id,
        "manufacturer": resolved.boeing_id,
        "evidence": [delivery_evidence_id, manufacturer_evidence_id],
    }
    event_id = f"SDA-EVENT-{delivery_date}-{_stable_suffix(event_seed, 16)}"
    delivery_event = {
        "id": event_id,
        "event_type": "delivery",
        "names": {"en": "Final F-15SA delivery reported by official source"},
        "occurred_at": {"value": delivery_date, "precision": "day"},
        "ended_at": None,
        "participants": [
            {"entity_id": resolved.rsaf_id, "role": "recipient"},
            {"entity_id": resolved.boeing_id, "role": "manufacturer"},
        ],
        "related_entity_ids": [resolved.f15sa_id],
        "related_claim_ids": [manufacturer_claim_id],
        "confidence": "high",
        "evidence_links": [
            {"evidence_id": delivery_evidence_id, "role": "supports"},
            {"evidence_id": manufacturer_evidence_id, "role": "contextualizes"},
        ],
        "notes": (
            "Candidate event represents the dated final-delivery statement only; "
            "it does not imply current inventory, location, readiness, serviceability, "
            "or a timeless operator relationship."
        ),
        "created_at": created_at,
    }

    mutations: list[dict[str, Any]] = [
        {
            "id": f"SDA-MUT-SOURCE-{_stable_suffix(source_record)}",
            "action": "create",
            "resource_type": "source",
            "payload": dict(source_record),
        },
        {
            "id": f"SDA-MUT-DOCUMENT-{_stable_suffix(document_record)}",
            "action": "create",
            "resource_type": "document",
            "payload": dict(document_record),
        },
    ]
    for record in evidence_records:
        mutations.append(
            {
                "id": f"SDA-MUT-EVIDENCE-{_stable_suffix(record)}",
                "action": "create",
                "resource_type": "evidence",
                "payload": dict(record),
            }
        )
    mutations.extend(
        [
            {
                "id": f"SDA-MUT-CLAIM-{_stable_suffix(manufacturer_claim)}",
                "action": "create",
                "resource_type": "claim",
                "payload": manufacturer_claim,
            },
            {
                "id": f"SDA-MUT-EVENT-{_stable_suffix(delivery_event)}",
                "action": "create",
                "resource_type": "event",
                "payload": delivery_event,
            },
        ]
    )

    proposal_seed = {
        "source_document_ids": [document_id],
        "mutation_ids": [mutation["id"] for mutation in mutations],
    }
    return {
        "id": f"SDA-PROPOSAL-M1-F15SA-{_stable_suffix(proposal_seed)}",
        "created_at": created_at,
        "created_by": {
            "kind": "system",
            "id": "deterministic-f15sa-source-adapter",
            "provider": None,
            "model": None,
            "version": "m1-v0.1",
        },
        "source_document_ids": [document_id],
        "risk_class": "AMBER",
        "policy_outcome": "human_review_required",
        "policy_reasons": [
            "substantive manufacturer relationship",
            "dated delivery event",
            "first vertical-slice canonical admission",
        ],
        "rationale": (
            "Deterministic source adapter proposes source/document/evidence records, "
            "one manufacturer claim, and one dated delivery event from bounded official evidence."
        ),
        "supersedes_proposal_id": None,
        "mutations": mutations,
    }
