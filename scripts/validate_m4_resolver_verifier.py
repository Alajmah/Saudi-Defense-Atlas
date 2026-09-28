#!/usr/bin/env python3
"""Validate deterministic M4 resolver/verifier and review-only proposal preparation."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.intelligence.resolver_verifier import (  # noqa: E402
    ResolverVerifierError,
    build_resolution_verification,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate(schema_name: str, value: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(value))
    if errors:
        failures.append(
            f"{schema_name}: " + "; ".join(error.message for error in errors)
        )


def candidate_entity(cid: str, entity_type: str, name: str, evid: str) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "entity_type": entity_type,
        "subtype": None,
        "names": {"en": name},
        "aliases": [],
        "evidence_candidate_ids": [evid],
    }


def candidate_ref(cid: str) -> dict[str, str]:
    return {"kind": "candidate_entity", "candidate_id": cid}


def extraction_run() -> dict[str, Any]:
    evidence = [
        {
            "candidate_id": f"CAND-EVID-{index}",
            "document_id": "SDA-DOC-M4-RV",
            "locator": {"paragraph": index},
            "excerpt_sha256": None,
            "capture_assessment": "explicit_text",
        }
        for index in range(1, 7)
    ]
    entities = [
        candidate_entity("CAND-ENT-EQUIP", "equipment_variant", "Falcon X", "CAND-EVID-1"),
        candidate_entity("CAND-ENT-ORG", "organization", "Test Air Force", "CAND-EVID-1"),
        candidate_entity("CAND-ENT-MAKER", "organization", "Test Aerospace", "CAND-EVID-2"),
        candidate_entity("CAND-ENT-UNKNOWN", "organization", "Unknown Partner", "CAND-EVID-5"),
    ]
    claims = [
        {
            "candidate_id": "CAND-CLAIM-NEW",
            "subject": candidate_ref("CAND-ENT-MAKER"),
            "predicate_id": "manufacturer.manufactures.equipment",
            "value": candidate_ref("CAND-ENT-EQUIP"),
            "evidence_candidate_ids": ["CAND-EVID-2"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-DUP",
            "subject": candidate_ref("CAND-ENT-ORG"),
            "predicate_id": "organization.operates.equipment_variant",
            "value": candidate_ref("CAND-ENT-EQUIP"),
            "evidence_candidate_ids": ["CAND-EVID-3"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-CONFLICT",
            "subject": candidate_ref("CAND-ENT-EQUIP"),
            "predicate_id": "inventory.quantity",
            "value": {"kind": "number", "value": 10, "unit": "aircraft", "precision": None, "lower_bound": None, "upper_bound": None},
            "evidence_candidate_ids": ["CAND-EVID-4"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-BLOCKED",
            "subject": candidate_ref("CAND-ENT-UNKNOWN"),
            "predicate_id": "organization.operates.equipment_variant",
            "value": candidate_ref("CAND-ENT-EQUIP"),
            "evidence_candidate_ids": ["CAND-EVID-5"],
            "extraction_assessment": "ambiguous_text",
            "rationale": None,
        },
    ]
    events = [
        {
            "candidate_id": "CAND-EVENT-DUP",
            "event_type": "delivery",
            "occurred_at": {"value": "2026-01-01", "precision": "day"},
            "ended_at": None,
            "participants": [
                {"entity": candidate_ref("CAND-ENT-ORG"), "role": "recipient"},
                {"entity": candidate_ref("CAND-ENT-MAKER"), "role": "manufacturer"},
            ],
            "related_entities": [candidate_ref("CAND-ENT-EQUIP")],
            "evidence_candidate_ids": ["CAND-EVID-3"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-EVENT-NEW",
            "event_type": "training",
            "occurred_at": {"value": "2026-02", "precision": "month"},
            "ended_at": None,
            "participants": [{"entity": candidate_ref("CAND-ENT-ORG"), "role": "participant"}],
            "related_entities": [candidate_ref("CAND-ENT-EQUIP")],
            "evidence_candidate_ids": ["CAND-EVID-6"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
    ]
    return {
        "id": "SDA-AIEX-M4-RV-TEST",
        "queue_item_id": "SDA-QUEUE-M4-RV-TEST",
        "source_document_ids": ["SDA-DOC-M4-RV"],
        "started_at": "2026-01-02T00:00:00Z",
        "completed_at": "2026-01-02T00:01:00Z",
        "model_trace": {"provider": "fixture", "model": "fixture", "model_version": "1", "adapter_version": "1"},
        "prompt_trace": {"template_id": "fixture", "template_version": "1", "template_sha256": "a" * 64},
        "input_sha256": "b" * 64,
        "raw_output_sha256": "c" * 64,
        "authority": {"mode": "candidate_only", "canonical_mutation_authority": False, "publication_authority": False},
        "validation": {"status": "accepted_for_candidate_review", "errors": []},
        "evaluation_trace": {"validator_version": "fixture", "checks": [{"check_id": "fixture", "status": "pass", "detail": None}]},
        "candidates": {"evidence": evidence, "entities": entities, "claims": claims, "events": events},
    }


def canonical_entities() -> list[dict[str, Any]]:
    def entity(entity_id: str, entity_type: str, name: str, aliases: list[str] | None = None) -> dict[str, Any]:
        return {
            "id": entity_id,
            "entity_type": entity_type,
            "names": {"en": name},
            "aliases": [{"value": item, "language": "en", "kind": "common"} for item in (aliases or [])],
            "record_status": "active",
        }
    return [
        entity("SDA-EQUIP-FALCON-X", "equipment_variant", "Falcon X"),
        entity("SDA-ORG-TEST-AF", "organization", "Test Air Force"),
        entity("SDA-ORG-TEST-AERO", "organization", "Test Aerospace"),
    ]


def canonical_claims() -> list[dict[str, Any]]:
    return [
        {
            "id": "SDA-CLAIM-EXISTING-OP",
            "subject_id": "SDA-ORG-TEST-AF",
            "predicate_id": "organization.operates.equipment_variant",
            "value": {"kind": "entity", "entity_id": "SDA-EQUIP-FALCON-X"},
            "claim_state": "active",
        },
        {
            "id": "SDA-CLAIM-EXISTING-QTY",
            "subject_id": "SDA-EQUIP-FALCON-X",
            "predicate_id": "inventory.quantity",
            "value": {"kind": "number", "value": 8, "unit": "aircraft", "precision": None, "lower_bound": None, "upper_bound": None},
            "claim_state": "active",
        },
    ]


def canonical_events() -> list[dict[str, Any]]:
    return [
        {
            "id": "SDA-EVENT-EXISTING-DELIVERY",
            "event_type": "delivery",
            "occurred_at": {"value": "2026-01-01", "precision": "day"},
            "participants": [
                {"entity_id": "SDA-ORG-TEST-AF", "role": "recipient"},
                {"entity_id": "SDA-ORG-TEST-AERO", "role": "manufacturer"},
            ],
            "related_entity_ids": ["SDA-EQUIP-FALCON-X"],
        }
    ]


def main() -> int:
    failures: list[str] = []
    extraction = extraction_run()
    validate("ai-extraction-run.schema.json", extraction, failures)

    run, proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=canonical_entities(),
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    validate("ai-resolution-verification-run.schema.json", run, failures)
    expect(proposal is not None, "expected AMBER proposal", failures)
    if proposal is not None:
        validate("change-proposal.schema.json", proposal, failures)
        expect(proposal["risk_class"] == "AMBER", "proposal risk must be AMBER", failures)
        expect(proposal["policy_outcome"] == "human_review_required", "proposal must require human review", failures)
        expect(all(item["action"] == "create" for item in proposal["mutations"]), "resolver emitted non-create mutation", failures)
        claim_payloads = [item["payload"] for item in proposal["mutations"] if item["resource_type"] == "claim"]
        event_payloads = [item["payload"] for item in proposal["mutations"] if item["resource_type"] == "event"]
        expect(len(claim_payloads) == 2, "duplicate/blocked claim leaked into proposal", failures)
        expect(any(item["claim_state"] == "disputed" for item in claim_payloads), "conflict was not preserved as disputed", failures)
        expect(all(item["confidence"] == "unverified" for item in claim_payloads), "AI claim promoted confidence", failures)
        expect(len(event_payloads) == 1 and event_payloads[0]["event_type"] == "training", "duplicate event leaked into proposal", failures)
        expect(event_payloads[0]["confidence"] == "unverified", "AI event promoted confidence", failures)

    resolutions = {item["candidate_entity_id"]: item for item in run["entity_resolutions"]}
    expect(resolutions["CAND-ENT-UNKNOWN"]["outcome"] == "unresolved", "unknown entity was auto-resolved", failures)
    claim_states = {item["candidate_claim_id"]: item for item in run["claim_assessments"]}
    expect(claim_states["CAND-CLAIM-DUP"]["outcome"] == "duplicate", "duplicate claim not detected", failures)
    expect(claim_states["CAND-CLAIM-CONFLICT"]["outcome"] == "conflict", "claim conflict not detected", failures)
    expect(claim_states["CAND-CLAIM-BLOCKED"]["outcome"] == "blocked_unresolved", "unresolved claim not blocked", failures)
    event_states = {item["candidate_event_id"]: item for item in run["event_assessments"]}
    expect(event_states["CAND-EVENT-DUP"]["outcome"] == "duplicate", "duplicate event not detected", failures)

    # Two compatible canonical entities sharing an exact alias must remain ambiguous.
    ambiguous_entities = canonical_entities() + [
        {
            "id": "SDA-ORG-TEST-AERO-2",
            "entity_type": "organization",
            "names": {"en": "Different Legal Name"},
            "aliases": [{"value": "Test Aerospace", "language": "en", "kind": "common"}],
            "record_status": "active",
        }
    ]
    ambiguous_run, ambiguous_proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=ambiguous_entities,
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    ambiguous = {item["candidate_entity_id"]: item for item in ambiguous_run["entity_resolutions"]}
    expect(ambiguous["CAND-ENT-MAKER"]["outcome"] == "ambiguous", "ambiguous exact match was auto-selected", failures)
    if ambiguous_proposal is not None:
        proposal_claims = [item["payload"] for item in ambiguous_proposal["mutations"] if item["resource_type"] == "claim"]
        expect(all(item["predicate_id"] != "manufacturer.manufactures.equipment" for item in proposal_claims), "ambiguous entity leaked into proposal claim", failures)

    rejected = copy.deepcopy(extraction)
    rejected["validation"] = {"status": "rejected", "errors": ["fixture"]}
    try:
        build_resolution_verification(
            extraction_run=rejected,
            canonical_entities=canonical_entities(),
            canonical_claims=canonical_claims(),
            canonical_events=canonical_events(),
        )
    except ResolverVerifierError:
        pass
    else:
        failures.append("rejected extraction run crossed resolver boundary")

    if failures:
        print("M4 resolver/verifier validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 resolver/verifier boundary: exact deterministic entity resolution, ambiguity preservation, "
        "duplicate/conflict detection, unresolved blocking, unverified candidate materialization, and AMBER human-review-only ChangeProposal preparation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
