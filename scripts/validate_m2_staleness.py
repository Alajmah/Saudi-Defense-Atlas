#!/usr/bin/env python3
"""Validate M2 claim-staleness semantics and failure boundaries."""

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
from services.presentation.staleness import (  # noqa: E402
    StalenessError,
    build_staleness_report,
)


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


def claim(
    *,
    claim_id: str,
    predicate_id: str,
    value: dict[str, Any],
    verified_at: str | None,
    claim_state: str = "active",
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "subject_id": "SDA-EQUIP-F15SA",
        "predicate_id": predicate_id,
        "value": value,
        "scope": {"entity_ids": ["SDA-EQUIP-F15SA"], "quantity_type": None, "note": None},
        "validity": {},
        "confidence": "high",
        "evidence_links": [
            {"evidence_id": "SDA-EVID-M2-STALENESS-SYNTHETIC", "role": "supports"}
        ],
        "claim_state": claim_state,
        "supersedes_claim_ids": [],
        "verified_at": verified_at,
        "created_at": "2025-01-01T00:00:00Z",
    }


def main() -> int:
    failures: list[str] = []

    claims = [
        claim(
            claim_id="SDA-CLAIM-M2-STALE-FRESH",
            predicate_id="manufacturer.manufactures.equipment",
            value={"kind": "entity", "entity_id": "SDA-ORG-BOEING"},
            verified_at="2026-01-05T00:00:00Z",
        ),
        claim(
            claim_id="SDA-CLAIM-M2-STALE-DUE",
            predicate_id="inventory.quantity",
            value={
                "kind": "number",
                "value": 1,
                "unit": "aircraft",
                "precision": "synthetic",
                "lower_bound": None,
                "upper_bound": None,
            },
            verified_at="2025-01-01T00:00:00Z",
        ),
        claim(
            claim_id="SDA-CLAIM-M2-STALE-UNVERIFIED",
            predicate_id="equipment.service_state",
            value={"kind": "string", "value": "synthetic", "language": "en"},
            verified_at=None,
            claim_state="disputed",
        ),
        claim(
            claim_id="SDA-CLAIM-M2-STALE-WITHDRAWN",
            predicate_id="equipment.service_state",
            value={"kind": "string", "value": "withdrawn", "language": "en"},
            verified_at="2020-01-01T00:00:00Z",
            claim_state="withdrawn",
        ),
    ]

    for item in claims:
        validate_instance("claim.schema.json", item, failures)

    report = build_staleness_report(
        claims=claims,
        as_of="2026-01-10T00:00:00Z",
        default_review_days=365,
        predicate_review_days={
            "inventory.quantity": 30,
            "equipment.service_state": 7,
        },
    )
    validate_instance("staleness-report.schema.json", report, failures)

    expect(
        report["summary"] == {"total": 3, "fresh": 1, "due": 1, "unverified": 1},
        "staleness summary changed",
        failures,
    )
    by_id = {item["claim_id"]: item for item in report["items"]}

    fresh = by_id["SDA-CLAIM-M2-STALE-FRESH"]
    expect(fresh["status"] == "fresh", "recent Claim must remain fresh", failures)
    expect(fresh["age_days"] == 5, "fresh Claim age changed", failures)
    expect(
        fresh["review_after_days"] == 365,
        "default review policy was not applied",
        failures,
    )

    due = by_id["SDA-CLAIM-M2-STALE-DUE"]
    expect(due["status"] == "due", "old volatile Claim must be due", failures)
    expect(
        due["review_after_days"] == 30,
        "predicate-specific review policy was not applied",
        failures,
    )
    expect(
        "not automatically false" in due["reason"],
        "due status must not imply falsity",
        failures,
    )

    unverified = by_id["SDA-CLAIM-M2-STALE-UNVERIFIED"]
    expect(
        unverified["status"] == "unverified",
        "missing verified_at must remain explicitly unverified",
        failures,
    )
    expect(unverified["age_days"] is None, "unverified Claim must not invent age", failures)
    expect(
        unverified["claim_state"] == "disputed",
        "disputed state must remain independent of staleness status",
        failures,
    )
    expect(
        "SDA-CLAIM-M2-STALE-WITHDRAWN" not in by_id,
        "withdrawn Claim must not enter current staleness workload",
        failures,
    )

    reversed_report = build_staleness_report(
        claims=list(reversed(claims)),
        as_of="2026-01-10T00:00:00Z",
        default_review_days=365,
        predicate_review_days={
            "equipment.service_state": 7,
            "inventory.quantity": 30,
        },
    )
    expect(report == reversed_report, "staleness output must be input-order independent", failures)

    future = copy.deepcopy(claims)
    future[0]["verified_at"] = "2026-01-11T00:00:00Z"
    try:
        build_staleness_report(
            claims=future,
            as_of="2026-01-10T00:00:00Z",
            default_review_days=365,
        )
        failures.append("future verified_at was accepted")
    except StalenessError:
        pass

    duplicate = [claims[0], copy.deepcopy(claims[0])]
    try:
        build_staleness_report(
            claims=duplicate,
            as_of="2026-01-10T00:00:00Z",
            default_review_days=365,
        )
        failures.append("duplicate current Claim ID was accepted")
    except StalenessError:
        pass

    try:
        build_staleness_report(
            claims=claims,
            as_of="2026-01-10T00:00:00Z",
            default_review_days=0,
        )
        failures.append("zero-day review policy was accepted")
    except StalenessError:
        pass

    if failures:
        print("M2 staleness validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated policy-driven M2 staleness: fresh/due/unverified states, "
        "predicate review windows, disputed-state independence, withdrawn exclusion, "
        "order independence, and no automatic truth/falsity mutation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
