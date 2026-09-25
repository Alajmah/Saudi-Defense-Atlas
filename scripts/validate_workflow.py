#!/usr/bin/env python3
"""Validate cross-record canonical mutation governance fixtures.

JSON Schema validates individual records. This script validates invariants that require
following references across ChangeProposal, ReviewDecision, and Revision records.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_FILE = ROOT / "tests" / "fixtures" / "workflow-fixtures.json"


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def validate_case(case: dict) -> list[str]:
    errors: list[str] = []
    proposal = case["proposal"]
    decision = case.get("decision")
    revision = case.get("revision")

    risk = proposal["risk_class"]
    outcome = proposal["policy_outcome"]

    if risk == "RED":
        if outcome != "blocked":
            errors.append("RED proposal must be blocked")
        if decision is not None and decision.get("decision") == "approve":
            errors.append("RED proposal cannot be approved")
        if revision is not None:
            errors.append("RED proposal cannot create a canonical revision")

    if outcome == "blocked" and revision is not None:
        errors.append("blocked proposal cannot create a canonical revision")

    if decision is not None:
        if decision["proposal_id"] != proposal["id"]:
            errors.append("decision must reference the exact proposal")

        actor_kind = decision["decided_by"]["kind"]
        action = decision["decision"]

        if action == "approve" and actor_kind == "system":
            if risk != "GREEN" or outcome != "auto_admit_allowed":
                errors.append("system approval is allowed only for GREEN auto-admit proposals")

        if risk == "AMBER" and action == "approve" and actor_kind != "human":
            errors.append("AMBER approval requires a human reviewer")

        if action in {"reject", "return_for_revision"} and revision is not None:
            errors.append(f"{action} decision cannot create a canonical revision")

    if revision is not None:
        if decision is None:
            errors.append("canonical revision requires a review decision")
        else:
            if decision["decision"] != "approve":
                errors.append("canonical revision requires an approve decision")
            if revision["decision_id"] != decision["id"]:
                errors.append("revision decision_id must reference the approving decision")
            if revision["proposal_id"] != proposal["id"]:
                errors.append("revision proposal_id must reference the reviewed proposal")

    return errors


def main() -> int:
    fixtures = load_json(FIXTURE_FILE)
    failures: list[str] = []

    for expected_valid, group_name in ((True, "valid"), (False, "invalid")):
        for case in fixtures.get(group_name, []):
            errors = validate_case(case)
            if expected_valid and errors:
                failures.append(f"{case['name']}: expected valid; {'; '.join(errors)}")
            elif not expected_valid and not errors:
                failures.append(f"{case['name']}: expected invalid but all workflow checks passed")

    if failures:
        print("Workflow validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Validated all proposal/review/revision workflow fixture expectations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
