#!/usr/bin/env python3
"""Regression checks from the maintainer fallback second review after Codex quota exhaustion."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m4_model_extraction_trial import fake_output  # noqa: E402
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ADAPTER_VERSION,
    PROMPT_TEMPLATE_VERSION,
    ModelTrace,
    build_extraction_run_from_model_output,
    build_trial_prompt,
)

FIXTURE = ROOT / "tests" / "fixtures" / "m4-model-extraction-eval.json"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def load_cases() -> dict[str, dict[str, Any]]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    cases = payload.get("cases")
    if not isinstance(cases, list):
        raise RuntimeError("evaluation fixture cases must be an array")
    return {case["id"]: case for case in cases}


def build_run(case: dict[str, Any], raw_output: str) -> dict[str, Any]:
    prompt = build_trial_prompt(case)
    return build_extraction_run_from_model_output(
        case=case,
        model_trace=ModelTrace(
            provider="deterministic-fallback-review",
            model="fixture-model",
            model_version="v0",
        ),
        prompt=prompt,
        raw_output=raw_output,
        started_at="2026-09-29T11:00:00Z",
        completed_at="2026-09-29T11:00:01Z",
    )


def failed_check_ids(run: dict[str, Any]) -> set[str]:
    return {
        check.get("check_id")
        for check in run.get("evaluation_trace", {}).get("checks", [])
        if isinstance(check, dict)
        and check.get("status") == "fail"
        and isinstance(check.get("check_id"), str)
    }


def main() -> int:
    failures: list[str] = []
    cases = load_cases()

    # FR-01: a live model must receive the actual candidate record contract rather
    # than be expected to guess SDA's internal JSON shape.
    delivery_prompt = build_trial_prompt(cases["TRIAL-EN-DELIVERY"])
    required_prompt_fragments = (
        "OUTPUT RECORD CONTRACT FOR THIS BOUNDED TRIAL:",
        "Evidence record fields:",
        "Entity record fields:",
        "Claim record fields:",
        "Event record fields:",
        "evidence_candidate_ids",
        "extraction_assessment",
        "validity: omit unless SOURCE_TEXT explicitly states temporal scope for that Claim",
        "Do not add unsupported temporal scope",
        "A date attached to one event does not automatically",
    )
    for fragment in required_prompt_fragments:
        expect(
            fragment in delivery_prompt,
            f"live prompt lacks explicit output-contract fragment: {fragment}",
            failures,
        )
    expect(
        ADAPTER_VERSION == "m4-model-trial-v0.3",
        "adapter version was not bumped for the changed model contract",
        failures,
    )
    expect(
        PROMPT_TEMPLATE_VERSION == "v0.6",
        "prompt-template version was not bumped for the changed model contract",
        failures,
    )
    # The v0.3 contract revision adds the canonical role vocabulary, the
    # equipment/equipment_variant typing rule, the exact-quantity bounds
    # convention, document-level Evidence cardinality, and the
    # permissions-not-obligations abstention rule.
    for fragment in (
        "ALLOWED_EVENT_ROLES",
        "Type a specific named model or variant of an equipment family as equipment_variant",
        "leave lower_bound and",
    "upper_bound null",
        "When you emit any substantive Entity, Claim, or Event, emit exactly one document-level",
        "When you abstain entirely, return all four",
        "permissions, not requirements",
        "most specific role the source explicitly states",
        "head noun of the counted-class phrase",
    ):
        expect(
            fragment in delivery_prompt,
            f"live prompt lacks the v0.3 contract-revision fragment: {fragment}",
            failures,
        )

    # The prompt still carries the exact case-specific authority/provenance inputs.
    expect(
        cases["TRIAL-EN-DELIVERY"]["source_document_id"] in delivery_prompt,
        "prompt lost source Document identity",
        failures,
    )
    for predicate in cases["TRIAL-EN-DELIVERY"]["allowed_predicates"]:
        expect(predicate in delivery_prompt, "prompt lost Claim allowlist", failures)
    for event_type in cases["TRIAL-EN-DELIVERY"]["allowed_event_types"]:
        expect(event_type in delivery_prompt, "prompt lost Event allowlist", failures)

    # FR-02: duplicate JSON member names are parser-differential and therefore not
    # accepted as an auditable strict model envelope, at the root or nested levels.
    quantity_case = cases["TRIAL-EN-PROCUREMENT-QUANTITY"]
    top_level_duplicate = (
        '{"evidence":[],"evidence":[],"entities":[],"claims":[],"events":[]}'
    )
    top_run = build_run(quantity_case, top_level_duplicate)
    expect(
        top_run["validation"]["status"] == "rejected",
        "duplicate top-level JSON key was not rejected",
        failures,
    )
    expect(
        "strict-json-envelope" in failed_check_ids(top_run),
        "duplicate top-level JSON key did not fail strict-json-envelope",
        failures,
    )

    quantity_raw = fake_output(quantity_case)
    nested_duplicate = quantity_raw.replace(
        '"value":12,"unit"',
        '"value":12,"value":13,"unit"',
        1,
    )
    expect(nested_duplicate != quantity_raw, "nested duplicate test mutation did not apply", failures)
    nested_run = build_run(quantity_case, nested_duplicate)
    expect(
        nested_run["validation"]["status"] == "rejected",
        "duplicate nested JSON key was not rejected",
        failures,
    )
    expect(
        "strict-json-envelope" in failed_check_ids(nested_run),
        "duplicate nested JSON key did not fail strict-json-envelope",
        failures,
    )
    expect(
        not any(nested_run["candidates"].values()),
        "duplicate-key rejection leaked candidate records",
        failures,
    )

    # Normal deterministic output remains admissible after the parser hardening.
    good_run = build_run(quantity_case, quantity_raw)
    expect(
        good_run["validation"]["status"] == "accepted_for_candidate_review",
        "valid deterministic quantity output stopped passing the candidate boundary",
        failures,
    )

    if failures:
        print("M4 model-trial fallback second-review validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated fallback second-review regressions: the live prompt carries explicit "
        "Evidence/Entity/Claim/Event record shapes and unsupported-temporal-scope rules; "
        "adapter/prompt versions are bumped; duplicate JSON keys fail closed at root and nested "
        "levels; valid candidate output remains admissible."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
