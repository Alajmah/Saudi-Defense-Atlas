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


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except ResolverVerifierError:
        return
    failures.append(f"{label} did not fail closed")


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


def candidate_entity(
    cid: str,
    entity_type: str,
    name: str,
    evid: str,
    *,
    aliases: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "candidate_id": cid,
        "entity_type": entity_type,
        "subtype": None,
        "names": {"en": name},
        "aliases": aliases or [],
        "evidence_candidate_ids": [evid],
    }


def candidate_ref(cid: str) -> dict[str, str]:
    return {"kind": "candidate_entity", "candidate_id": cid}


def point(date: str) -> dict[str, Any]:
    return {"point_in_time": {"value": date, "precision": "day"}}


def extraction_run() -> dict[str, Any]:
    evidence = [
        {
            "candidate_id": f"CAND-EVID-{index}",
            "document_id": "SDA-DOC-M4-RV",
            "locator": {"paragraph": index},
            "excerpt_sha256": None,
            "capture_assessment": "explicit_text",
        }
        for index in range(1, 13)
    ]
    entities = [
        candidate_entity("CAND-ENT-EQUIP", "equipment_variant", "Falcon X", "CAND-EVID-1"),
        candidate_entity("CAND-ENT-FAMILY", "equipment", "Falcon", "CAND-EVID-2"),
        candidate_entity("CAND-ENT-ORG", "organization", "Test Air Force", "CAND-EVID-3"),
        candidate_entity("CAND-ENT-MAKER", "organization", "Test Aerospace", "CAND-EVID-4"),
        candidate_entity("CAND-ENT-FAC", "facility", "Public Test Facility", "CAND-EVID-5"),
        candidate_entity("CAND-ENT-UNKNOWN", "organization", "Unknown Partner", "CAND-EVID-6"),
        # The canonical record below exposes this text only as a loose search alias;
        # it must not become canonical entity-resolution authority.
        candidate_entity("CAND-ENT-LOOSE", "organization", "Loose Search Term", "CAND-EVID-7"),
    ]
    claims = [
        {
            "candidate_id": "CAND-CLAIM-NEW",
            "subject": candidate_ref("CAND-ENT-EQUIP"),
            "predicate_id": "equipment_variant.variant_of.equipment",
            "value": candidate_ref("CAND-ENT-FAMILY"),
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
            "predicate_id": "equipment.service_state",
            "value": {"kind": "string", "value": "operational", "language": None},
            "validity": point("2026-01-01"),
            "evidence_candidate_ids": ["CAND-EVID-4"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-HISTORY",
            "subject": candidate_ref("CAND-ENT-EQUIP"),
            "predicate_id": "equipment.service_state",
            "value": {"kind": "string", "value": "operational", "language": None},
            "validity": point("2025-01-01"),
            "evidence_candidate_ids": ["CAND-EVID-8"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-QTY",
            "subject": candidate_ref("CAND-ENT-EQUIP"),
            "predicate_id": "inventory.quantity",
            "value": {
                "kind": "number",
                "value": 10,
                "unit": "aircraft",
                "precision": None,
                "lower_bound": None,
                "upper_bound": None,
            },
            "evidence_candidate_ids": ["CAND-EVID-9"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-COORD",
            "subject": candidate_ref("CAND-ENT-FAC"),
            "predicate_id": "facility.public_latitude",
            "value": {
                "kind": "number",
                "value": 24.7136,
                "unit": "degrees",
                "precision": "source",
                "lower_bound": None,
                "upper_bound": None,
            },
            "evidence_candidate_ids": ["CAND-EVID-10"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-AMBIG",
            "subject": candidate_ref("CAND-ENT-ORG"),
            "predicate_id": "organization.operates.equipment_variant",
            "value": candidate_ref("CAND-ENT-EQUIP"),
            "evidence_candidate_ids": ["CAND-EVID-11"],
            "extraction_assessment": "ambiguous_text",
            "rationale": None,
        },
        {
            "candidate_id": "CAND-CLAIM-UNRESOLVED",
            "subject": candidate_ref("CAND-ENT-UNKNOWN"),
            "predicate_id": "organization.operates.equipment_variant",
            "value": candidate_ref("CAND-ENT-EQUIP"),
            "evidence_candidate_ids": ["CAND-EVID-6"],
            "extraction_assessment": "explicit_text",
            "rationale": None,
        },
    ]
    events = [
        {
            "candidate_id": "CAND-EVENT-POSSIBLE-DUP",
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
            "evidence_candidate_ids": ["CAND-EVID-12"],
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
        "model_trace": {
            "provider": "fixture",
            "model": "fixture",
            "model_version": "1",
            "adapter_version": "1",
        },
        "prompt_trace": {
            "template_id": "fixture",
            "template_version": "1",
            "template_sha256": "a" * 64,
        },
        "input_sha256": "b" * 64,
        "raw_output_sha256": "c" * 64,
        "authority": {
            "mode": "candidate_only",
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "validation": {"status": "accepted_for_candidate_review", "errors": []},
        "evaluation_trace": {
            "validator_version": "fixture",
            "checks": [{"check_id": "fixture", "status": "pass", "detail": None}],
        },
        "candidates": {
            "evidence": evidence,
            "entities": entities,
            "claims": claims,
            "events": events,
        },
    }


def canonical_entities() -> list[dict[str, Any]]:
    def entity(
        entity_id: str,
        entity_type: str,
        name: str,
        *,
        aliases: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        return {
            "id": entity_id,
            "entity_type": entity_type,
            "names": {"en": name},
            "aliases": aliases or [],
            "record_status": "active",
        }

    return [
        entity("SDA-EQUIP-FALCON-X", "equipment_variant", "Falcon X"),
        entity("SDA-EQUIP-FALCON", "equipment", "Falcon"),
        entity("SDA-ORG-TEST-AF", "organization", "Test Air Force"),
        entity("SDA-ORG-TEST-AERO", "organization", "Test Aerospace"),
        entity("SDA-FAC-PUBLIC-TEST", "facility", "Public Test Facility"),
        entity(
            "SDA-ORG-LOOSE-ALIAS",
            "organization",
            "Different Canonical Name",
            aliases=[
                {
                    "value": "Loose Search Term",
                    "language": "en",
                    "kind": "search",
                }
            ],
        ),
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
            "id": "SDA-CLAIM-EXISTING-STATE",
            "subject_id": "SDA-EQUIP-FALCON-X",
            "predicate_id": "equipment.service_state",
            "value": {"kind": "string", "value": "retired", "language": None},
            "validity": point("2026-01-01"),
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
    expect(run["authority"] == {
        "mode": "proposal_preparation_only",
        "approval_authority": False,
        "canonical_mutation_authority": False,
        "publication_authority": False,
    }, "resolver authority widened", failures)

    expect(proposal is not None, "expected AMBER proposal", failures)
    if proposal is not None:
        validate("change-proposal.schema.json", proposal, failures)
        expect(proposal["risk_class"] == "AMBER", "proposal risk must be AMBER", failures)
        expect(
            proposal["policy_outcome"] == "human_review_required",
            "proposal must require human review",
            failures,
        )
        expect(
            all(item["action"] == "create" for item in proposal["mutations"]),
            "resolver emitted non-create mutation",
            failures,
        )
        claim_payloads = [
            item["payload"]
            for item in proposal["mutations"]
            if item["resource_type"] == "claim"
        ]
        event_payloads = [
            item["payload"]
            for item in proposal["mutations"]
            if item["resource_type"] == "event"
        ]
        # new variant relationship + same-time conflict + historical point-in-time fact
        expect(len(claim_payloads) == 3, "blocked/duplicate Claim leaked or valid Claim disappeared", failures)
        expect(
            sum(item["claim_state"] == "disputed" for item in claim_payloads) == 1,
            "same-time conflict was not preserved exactly once as disputed",
            failures,
        )
        expect(
            all(item["confidence"] == "unverified" for item in claim_payloads),
            "AI Claim promoted confidence",
            failures,
        )
        expect(
            all(item["predicate_id"] not in {"inventory.quantity", "facility.public_latitude"} for item in claim_payloads),
            "quantity or precise geography leaked into proposal",
            failures,
        )
        expect(
            len(event_payloads) == 1 and event_payloads[0]["event_type"] == "training",
            "possible-duplicate Event leaked into proposal",
            failures,
        )
        expect(
            event_payloads[0]["confidence"] == "unverified",
            "AI Event promoted confidence",
            failures,
        )
        evidence_payloads = [
            item["payload"]
            for item in proposal["mutations"]
            if item["resource_type"] == "evidence"
        ]
        expect(
            all(item["document_id"] == "SDA-DOC-M4-RV" for item in evidence_payloads),
            "materialized Evidence escaped extraction Document provenance",
            failures,
        )

    resolutions = {item["candidate_entity_id"]: item for item in run["entity_resolutions"]}
    expect(
        resolutions["CAND-ENT-UNKNOWN"]["outcome"] == "unresolved",
        "unknown entity was auto-resolved",
        failures,
    )
    expect(
        resolutions["CAND-ENT-LOOSE"]["outcome"] == "unresolved",
        "search-only alias became canonical resolution authority",
        failures,
    )

    claim_states = {item["candidate_claim_id"]: item for item in run["claim_assessments"]}
    expect(claim_states["CAND-CLAIM-NEW"]["outcome"] == "new", "valid new Claim not admitted to review", failures)
    expect(claim_states["CAND-CLAIM-DUP"]["outcome"] == "duplicate", "duplicate Claim not detected", failures)
    expect(claim_states["CAND-CLAIM-CONFLICT"]["outcome"] == "conflict", "same-time Claim conflict not detected", failures)
    expect(claim_states["CAND-CLAIM-HISTORY"]["outcome"] == "new", "historical Claim was collapsed into conflict", failures)
    expect(claim_states["CAND-CLAIM-QTY"]["outcome"] == "blocked_ambiguous", "unscoped quantity entered proposal path", failures)
    expect(claim_states["CAND-CLAIM-COORD"]["outcome"] == "blocked_policy", "AI precise coordinate entered proposal path", failures)
    expect(claim_states["CAND-CLAIM-AMBIG"]["outcome"] == "blocked_ambiguous", "ambiguous extraction entered proposal path", failures)
    expect(claim_states["CAND-CLAIM-UNRESOLVED"]["outcome"] == "blocked_unresolved", "unresolved Claim not blocked", failures)

    event_states = {item["candidate_event_id"]: item for item in run["event_assessments"]}
    expect(
        event_states["CAND-EVENT-POSSIBLE-DUP"]["outcome"] == "possible_duplicate",
        "Event signature match was treated as certain duplicate",
        failures,
    )
    expect(event_states["CAND-EVENT-NEW"]["outcome"] == "new", "new Event not retained for review", failures)

    # Two compatible canonical entities sharing an exact authoritative alias remain ambiguous.
    ambiguous_entities = canonical_entities() + [
        {
            "id": "SDA-ORG-TEST-AERO-2",
            "entity_type": "organization",
            "names": {"en": "Different Legal Name"},
            "aliases": [
                {"value": "Test Aerospace", "language": "en", "kind": "common"}
            ],
            "record_status": "active",
        }
    ]
    ambiguous_run, ambiguous_proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=ambiguous_entities,
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    ambiguous = {
        item["candidate_entity_id"]: item
        for item in ambiguous_run["entity_resolutions"]
    }
    expect(
        ambiguous["CAND-ENT-MAKER"]["outcome"] == "ambiguous",
        "ambiguous exact match was auto-selected",
        failures,
    )
    if ambiguous_proposal is not None:
        expect(
            all(
                not (
                    item["resource_type"] == "event"
                    and item["payload"].get("event_type") == "delivery"
                )
                for item in ambiguous_proposal["mutations"]
            ),
            "ambiguous entity leaked into Event proposal",
            failures,
        )

    # Extraction provenance must be revalidated here, not merely trusted from upstream.
    escaped_evidence = copy.deepcopy(extraction)
    escaped_evidence["candidates"]["evidence"][0]["document_id"] = "SDA-DOC-OUTSIDE"
    expect_raises(
        "out-of-scope candidate Evidence",
        lambda: build_resolution_verification(
            extraction_run=escaped_evidence,
            canonical_entities=canonical_entities(),
            canonical_claims=canonical_claims(),
            canonical_events=canonical_events(),
        ),
        failures,
    )

    # A structurally valid ontology predicate must still respect its semantic domain/range.
    bad_shape = copy.deepcopy(extraction)
    bad_shape["candidates"]["claims"][0]["subject"] = candidate_ref("CAND-ENT-ORG")
    expect_raises(
        "predicate subject/value type mismatch",
        lambda: build_resolution_verification(
            extraction_run=bad_shape,
            canonical_entities=canonical_entities(),
            canonical_claims=canonical_claims(),
            canonical_events=canonical_events(),
        ),
        failures,
    )

    rejected = copy.deepcopy(extraction)
    rejected["validation"] = {"status": "rejected", "errors": ["fixture"]}
    expect_raises(
        "rejected extraction run",
        lambda: build_resolution_verification(
            extraction_run=rejected,
            canonical_entities=canonical_entities(),
            canonical_claims=canonical_claims(),
            canonical_events=canonical_events(),
        ),
        failures,
    )

    if failures:
        print("M4 resolver/verifier validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 resolver/verifier boundary: authoritative exact identity only, ambiguity preservation, "
        "temporal-aware Claim comparison, possible-duplicate Event isolation, quantity/geography policy blocks, "
        "Document provenance closure, unverified candidate materialization, and AMBER human-review-only proposals."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
