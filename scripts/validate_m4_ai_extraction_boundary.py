#!/usr/bin/env python3
"""Validate the M4 typed AI extraction trace/candidate boundary."""

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
from services.intelligence.ai_extraction_boundary import (  # noqa: E402
    AIExtractionBoundaryError,
    validate_ai_extraction_run,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_boundary_error(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except AIExtractionBoundaryError:
        return
    failures.append(f"{label} did not fail closed")


def schema_errors(instance: dict[str, Any]) -> list[str]:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas["ai-extraction-run.schema.json"],
        registry=registry,
        format_checker=FormatChecker(),
    )
    return [error.message for error in validator.iter_errors(instance)]


def queue_item() -> dict[str, Any]:
    return {
        "id": "SDA-QUEUE-AI-TEST",
        "observation_ids": ["SDA-MON-AI-TEST"],
        "source_ids": ["SDA-SOURCE-AI-TEST"],
        "document_ids": ["SDA-DOC-AI-TEST"],
        "dedupe_key": f"sha256:{'a' * 64}",
        "lane": "candidate_extraction",
        "state": "claimed",
        "priority": "high",
        "reason_codes": ["lane:candidate_extraction", "policy:M4-ROUTING-v0.1"],
        "ai_extraction_allowed": True,
        "canonical_mutation_authority": False,
        "created_at": "2026-09-28T01:00:00Z",
    }


def accepted_run() -> dict[str, Any]:
    return {
        "id": "SDA-AIRUN-TEST-001",
        "queue_item_id": "SDA-QUEUE-AI-TEST",
        "source_document_ids": ["SDA-DOC-AI-TEST"],
        "started_at": "2026-09-28T01:01:00Z",
        "completed_at": "2026-09-28T01:01:05Z",
        "model_trace": {
            "provider": "test-provider",
            "model": "test-model",
            "model_version": "2026-09-01",
            "adapter_version": "m4-v0.1",
        },
        "prompt_trace": {
            "template_id": "defense-extractor",
            "template_version": "v0.1",
            "template_sha256": "b" * 64,
        },
        "input_sha256": "c" * 64,
        "raw_output_sha256": "d" * 64,
        "authority": {
            "mode": "candidate_only",
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "validation": {
            "status": "accepted_for_candidate_review",
            "errors": [],
        },
        "evaluation_trace": {
            "validator_version": "m4-ai-boundary-v0.1",
            "checks": [
                {"check_id": "schema", "status": "pass", "detail": None},
                {"check_id": "references", "status": "pass", "detail": None},
            ],
        },
        "candidates": {
            "evidence": [
                {
                    "candidate_id": "CAND-EVID-1",
                    "document_id": "SDA-DOC-AI-TEST",
                    "locator": {"paragraph": 3},
                    "excerpt_sha256": "e" * 64,
                    "capture_assessment": "explicit_text",
                }
            ],
            "entities": [
                {
                    "candidate_id": "CAND-BOEING",
                    "entity_type": "organization",
                    "subtype": "manufacturer",
                    "names": {"en": "Boeing"},
                    "aliases": [],
                    "evidence_candidate_ids": ["CAND-EVID-1"],
                },
                {
                    "candidate_id": "CAND-F15SA",
                    "entity_type": "equipment_variant",
                    "subtype": "fighter",
                    "names": {"en": "F-15SA"},
                    "aliases": [{"value": "F15SA", "language": "en", "kind": "designation"}],
                    "evidence_candidate_ids": ["CAND-EVID-1"],
                },
                {
                    "candidate_id": "CAND-RSAF",
                    "entity_type": "organization",
                    "subtype": "air_force",
                    "names": {"en": "Royal Saudi Air Force"},
                    "aliases": [],
                    "evidence_candidate_ids": ["CAND-EVID-1"],
                },
            ],
            "claims": [
                {
                    "candidate_id": "CAND-CLAIM-1",
                    "subject": {"kind": "candidate_entity", "candidate_id": "CAND-BOEING"},
                    "predicate_id": "manufacturer.manufactures.equipment",
                    "value": {"kind": "candidate_entity", "candidate_id": "CAND-F15SA"},
                    "validity": {"point_in_time": {"value": "2020-12-11", "precision": "day"}},
                    "evidence_candidate_ids": ["CAND-EVID-1"],
                    "extraction_assessment": "explicit_text",
                    "rationale": "Manufacturer relation stated in the cited source span.",
                }
            ],
            "events": [
                {
                    "candidate_id": "CAND-EVENT-1",
                    "event_type": "delivery",
                    "occurred_at": {"value": "2020-12-10", "precision": "day"},
                    "ended_at": None,
                    "participants": [
                        {"entity": {"kind": "candidate_entity", "candidate_id": "CAND-RSAF"}, "role": "recipient"},
                        {"entity": {"kind": "candidate_entity", "candidate_id": "CAND-BOEING"}, "role": "manufacturer"},
                    ],
                    "related_entities": [
                        {"kind": "candidate_entity", "candidate_id": "CAND-F15SA"}
                    ],
                    "evidence_candidate_ids": ["CAND-EVID-1"],
                    "extraction_assessment": "explicit_text",
                    "rationale": "Dated delivery statement in cited source span.",
                }
            ],
        },
    }


def main() -> int:
    failures: list[str] = []
    queue = queue_item()
    run = accepted_run()

    expect(not schema_errors(run), "accepted extraction fixture is not schema-valid", failures)
    try:
        validate_ai_extraction_run(queue_item=queue, run=run)
    except AIExtractionBoundaryError as exc:
        failures.append(f"accepted extraction fixture failed boundary validation: {exc}")

    not_claimed = copy.deepcopy(queue)
    not_claimed["state"] = "queued"
    expect_boundary_error(
        "unclaimed queue extraction",
        lambda: validate_ai_extraction_run(queue_item=not_claimed, run=run),
        failures,
    )

    discovery = copy.deepcopy(queue)
    discovery["lane"] = "discovery_review"
    discovery["ai_extraction_allowed"] = False
    expect_boundary_error(
        "discovery-only extraction",
        lambda: validate_ai_extraction_run(queue_item=discovery, run=run),
        failures,
    )

    outside_document = copy.deepcopy(run)
    outside_document["source_document_ids"] = ["SDA-DOC-OUTSIDE"]
    outside_document["candidates"]["evidence"][0]["document_id"] = "SDA-DOC-OUTSIDE"
    expect_boundary_error(
        "out-of-queue document extraction",
        lambda: validate_ai_extraction_run(queue_item=queue, run=outside_document),
        failures,
    )

    unresolved_evidence = copy.deepcopy(run)
    unresolved_evidence["candidates"]["claims"][0]["evidence_candidate_ids"] = ["CAND-EVID-MISSING"]
    expect_boundary_error(
        "unresolved candidate Evidence",
        lambda: validate_ai_extraction_run(queue_item=queue, run=unresolved_evidence),
        failures,
    )

    duplicate_id = copy.deepcopy(run)
    duplicate_id["candidates"]["events"][0]["candidate_id"] = "CAND-CLAIM-1"
    expect_boundary_error(
        "duplicate cross-type candidate ID",
        lambda: validate_ai_extraction_run(queue_item=queue, run=duplicate_id),
        failures,
    )

    canonical_subject = copy.deepcopy(run)
    canonical_subject["candidates"]["claims"][0]["subject"] = {
        "kind": "canonical_entity",
        "entity_id": "SDA-ORG-BOEING",
    }
    expect(bool(schema_errors(canonical_subject)), "schema allowed model-produced canonical entity reference", failures)

    failed_check = copy.deepcopy(run)
    failed_check["evaluation_trace"]["checks"][1]["status"] = "fail"
    expect_boundary_error(
        "accepted run with failed evaluation",
        lambda: validate_ai_extraction_run(queue_item=queue, run=failed_check),
        failures,
    )

    rejected = copy.deepcopy(run)
    rejected["validation"] = {"status": "rejected", "errors": ["structured output failed validation"]}
    rejected["evaluation_trace"]["checks"][0]["status"] = "fail"
    rejected["candidates"] = {"evidence": [], "entities": [], "claims": [], "events": []}
    expect(not schema_errors(rejected), "rejected empty-candidate trace should remain auditable/schema-valid", failures)
    try:
        validate_ai_extraction_run(queue_item=queue, run=rejected)
    except AIExtractionBoundaryError as exc:
        failures.append(f"rejected trace failed audit validation: {exc}")

    rejected_leak = copy.deepcopy(rejected)
    rejected_leak["candidates"]["entities"] = copy.deepcopy(run["candidates"]["entities"])
    expect(bool(schema_errors(rejected_leak)), "rejected run schema allowed candidate leakage", failures)
    expect_boundary_error(
        "rejected candidate leakage",
        lambda: validate_ai_extraction_run(queue_item=queue, run=rejected_leak),
        failures,
    )

    if failures:
        print("M4 AI extraction boundary validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 typed AI extraction boundary: claimed candidate-extraction queue only; model/prompt/evaluation trace; "
        "candidate-only authority; local CAND-* identity before Resolver; document/evidence/reference closure; failed-output isolation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
