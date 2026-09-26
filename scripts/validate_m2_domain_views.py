#!/usr/bin/env python3
"""Validate typed M2 ProcurementProgramView and ExerciseView contracts."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m2_relationship_graph import graph_records  # noqa: E402
from scripts.validate_schemas import build_registry  # noqa: E402
from services.presentation.domain_views import (  # noqa: E402
    build_exercise_view,
    build_procurement_program_view,
)
from services.presentation.projection_support import ProjectionError  # noqa: E402
from services.presentation.staleness import build_staleness_report  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(schema_name: str, instance: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(
            f"{schema_name} failed: "
            + "; ".join(error.message for error in errors)
        )


def records_with_procurement_facts() -> dict[str, list[dict[str, Any]]]:
    records = copy.deepcopy(graph_records())
    evidence_id = "SDA-EVID-M2-SYNTHETIC-PROCUREMENT"
    program_id = "SDA-PROC-M2-SYNTHETIC"

    lifecycle = {
        "id": "SDA-CLAIM-M2-PROCUREMENT-LIFECYCLE-CONTRACTED",
        "subject_id": program_id,
        "predicate_id": "procurement_program.lifecycle_state",
        "value": {"kind": "string", "value": "contracted", "language": "en"},
        "scope": {"entity_ids": [program_id], "quantity_type": None, "note": "Synthetic fixture."},
        "validity": {"point_in_time": {"value": "2026-01-08", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": evidence_id, "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }
    quantity = {
        "id": "SDA-CLAIM-M2-PROCUREMENT-QUANTITY",
        "subject_id": program_id,
        "predicate_id": "procurement.quantity",
        "value": {
            "kind": "number",
            "value": 12,
            "unit": "synthetic_units",
            "precision": "exact_fixture",
            "lower_bound": None,
            "upper_bound": None,
        },
        "scope": {
            "entity_ids": ["SDA-EQUIP-F15SA"],
            "quantity_type": "contracted",
            "note": "Synthetic fixture only.",
        },
        "validity": {"point_in_time": {"value": "2026-01-08", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": evidence_id, "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }
    records["claims"].extend([lifecycle, quantity])
    return records


def main() -> int:
    failures: list[str] = []
    records = records_with_procurement_facts()

    for schema_name, key in (
        ("entity.schema.json", "entities"),
        ("claim.schema.json", "claims"),
        ("event.schema.json", "events"),
        ("evidence.schema.json", "evidence"),
        ("document.schema.json", "documents"),
        ("source.schema.json", "sources"),
    ):
        for instance in records[key]:
            validate_instance(schema_name, instance, failures)

    staleness = build_staleness_report(
        claims=records["claims"],
        as_of="2026-01-12T00:00:00Z",
        default_review_days=365,
        predicate_review_days={
            "procurement_program.lifecycle_state": 30,
            "procurement.quantity": 30,
        },
    )
    validate_instance("staleness-report.schema.json", staleness, failures)

    procurement = build_procurement_program_view(
        entity_id="SDA-PROC-M2-SYNTHETIC",
        **records,
        staleness_report=staleness,
        projected_at="2026-01-12T00:01:00Z",
        revision_ids=["SDA-REVISION-M2-DOMAIN-VIEW-TEST"],
    )
    validate_instance("procurement-program-view.schema.json", procurement, failures)

    expect(
        procurement["lifecycle_state"] == {
            "state": "known",
            "claim_ids": ["SDA-CLAIM-M2-PROCUREMENT-LIFECYCLE-CONTRACTED"],
            "values": ["contracted"],
            "reason": None,
        },
        "procurement lifecycle state changed",
        failures,
    )
    procurement_fact_predicates = {fact["predicate_id"] for fact in procurement["facts"]}
    expect(
        procurement_fact_predicates
        == {"procurement_program.lifecycle_state", "procurement.quantity"},
        "procurement scalar facts changed",
        failures,
    )
    expect(
        any(item["event_type"] == "contract_award" for item in procurement["graph"]["timeline"]),
        "procurement timeline lost contract award",
        failures,
    )
    expect(
        {item["claim_id"] for item in procurement["staleness"]}
        >= {
            "SDA-CLAIM-M2-PROCUREMENT-LIFECYCLE-CONTRACTED",
            "SDA-CLAIM-M2-PROCUREMENT-QUANTITY",
            "SDA-CLAIM-M2-PROCUREMENT-ACQUIRES-F15SA",
        },
        "procurement view lost relevant staleness records",
        failures,
    )

    exercise = build_exercise_view(
        entity_id="SDA-EXERCISE-M2-SYNTHETIC",
        **records,
        staleness_report=staleness,
        projected_at="2026-01-12T00:01:00Z",
        revision_ids=["SDA-REVISION-M2-DOMAIN-VIEW-TEST"],
    )
    validate_instance("exercise-view.schema.json", exercise, failures)
    exercise_relations = {edge["relation"] for edge in exercise["graph"]["edges"]}
    expect(
        "exercise.uses.equipment_variant" in exercise_relations,
        "exercise view lost equipment relationship",
        failures,
    )
    expect(
        "exercise.participant.organization" in exercise_relations,
        "exercise view lost participant relationship",
        failures,
    )
    exercise_events = [
        item
        for item in exercise["graph"]["timeline"]
        if item["event_type"] == "exercise"
    ]
    expect(len(exercise_events) == 1, "exercise view must retain one exercise Event", failures)
    if exercise_events:
        expect(
            exercise_events[0]["ended_at"] == {"value": "2026-01-10", "precision": "day"},
            "exercise view lost Event end date",
            failures,
        )

    disputed_records = copy.deepcopy(records)
    disputed_lifecycle = next(
        claim
        for claim in disputed_records["claims"]
        if claim["id"] == "SDA-CLAIM-M2-PROCUREMENT-LIFECYCLE-CONTRACTED"
    )
    competing = copy.deepcopy(disputed_lifecycle)
    competing["id"] = "SDA-CLAIM-M2-PROCUREMENT-LIFECYCLE-DELIVERY"
    competing["value"] = {"kind": "string", "value": "delivery", "language": "en"}
    competing["claim_state"] = "disputed"
    disputed_records["claims"].append(competing)
    disputed_staleness = build_staleness_report(
        claims=disputed_records["claims"],
        as_of="2026-01-12T00:00:00Z",
        default_review_days=365,
    )
    disputed_view = build_procurement_program_view(
        entity_id="SDA-PROC-M2-SYNTHETIC",
        **disputed_records,
        staleness_report=disputed_staleness,
        projected_at="2026-01-12T00:01:00Z",
    )
    expect(
        disputed_view["lifecycle_state"]["state"] == "disputed",
        "competing lifecycle Claims must not be flattened to one state",
        failures,
    )
    expect(
        disputed_view["lifecycle_state"]["values"] == ["contracted", "delivery"],
        "competing lifecycle values must remain visible",
        failures,
    )

    incomplete_staleness = copy.deepcopy(staleness)
    incomplete_staleness["items"] = [
        item
        for item in incomplete_staleness["items"]
        if item["claim_id"] != "SDA-CLAIM-M2-PROCUREMENT-QUANTITY"
    ]
    try:
        build_procurement_program_view(
            entity_id="SDA-PROC-M2-SYNTHETIC",
            **records,
            staleness_report=incomplete_staleness,
            projected_at="2026-01-12T00:01:00Z",
        )
        failures.append("procurement view accepted missing staleness for current material Claim")
    except ProjectionError:
        pass

    serialized = str(procurement) + str(exercise)
    expect("Q999" not in serialized, "domain views must not leak backend Q IDs", failures)
    expect(
        "backend_identifiers" not in serialized,
        "domain views must not expose backend identifier fields",
        failures,
    )

    if failures:
        print("M2 domain-view validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M2 procurement/exercise views: explicit lifecycle uncertainty, scalar "
        "procurement facts, bounded cited graphs, exercise intervals, joined staleness, "
        "and no backend-ID leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
