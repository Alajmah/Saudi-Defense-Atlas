#!/usr/bin/env python3
"""Regression checks for Codex findings on the bounded M4 model trial."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_m4_model_extraction_trial import evaluate_case  # noqa: E402
from scripts.validate_m4_model_extraction_trial import fake_output  # noqa: E402
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ModelTrace,
    build_extraction_run_from_model_output,
    build_trial_prompt,
)

FIXTURE = ROOT / "tests" / "fixtures" / "m4-model-extraction-eval.json"
WORKFLOW = ROOT / ".github" / "workflows" / "m4-model-extraction-trial.yml"


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
            provider="deterministic-reconciliation",
            model="fixture-model",
            model_version="v0",
        ),
        prompt=prompt,
        raw_output=raw_output,
        started_at="2026-09-29T10:20:00Z",
        completed_at="2026-09-29T10:20:01Z",
    )


def failed_check_ids(run: dict[str, Any]) -> set[str]:
    return {
        check.get("check_id")
        for check in run.get("evaluation_trace", {}).get("checks", [])
        if isinstance(check, dict)
        and check.get("status") == "fail"
        and isinstance(check.get("check_id"), str)
    }


def quality(case: dict[str, Any], run: dict[str, Any]) -> dict[str, Any]:
    return evaluate_case(case, invoked=True, blocked=False, run=run)


def main() -> int:
    failures: list[str] = []
    cases = load_cases()

    # Codex P1: workflow-dispatch values must never become Bash source text while
    # the dedicated Copilot token is in scope. Expressions are assigned to env
    # values by Actions, then quoted shell variables are passed to Python.
    workflow = WORKFLOW.read_text(encoding="utf-8")
    expect(
        'TRIAL_MODEL: ${{ inputs.model }}' in workflow,
        "workflow does not bind model input through environment",
        failures,
    )
    expect(
        'TRIAL_MAX_CASES: ${{ inputs.max_cases }}' in workflow,
        "workflow does not bind max_cases input through environment",
        failures,
    )
    expect(
        '--model "$TRIAL_MODEL"' in workflow,
        "workflow does not pass quoted TRIAL_MODEL",
        failures,
    )
    expect(
        '--max-cases "$TRIAL_MAX_CASES"' in workflow,
        "workflow does not pass quoted TRIAL_MAX_CASES",
        failures,
    )
    expect(
        '--model "${{ inputs.model }}"' not in workflow
        and '--max-cases "${{ inputs.max_cases }}"' not in workflow,
        "workflow interpolates dispatch input directly into Bash source",
        failures,
    )

    # Codex P2: strict JSON means rejecting Python's non-standard NaN/Infinity
    # constants and finite-overflow numeric tokens such as 1e999.
    quantity_case = cases["TRIAL-EN-PROCUREMENT-QUANTITY"]
    quantity_raw = fake_output(quantity_case)
    for token in ("NaN", "Infinity", "-Infinity", "1e999"):
        malicious_raw = quantity_raw.replace('"value":12', f'"value":{token}', 1)
        run = build_run(quantity_case, malicious_raw)
        expect(
            run["validation"]["status"] == "rejected",
            f"non-finite JSON token {token} was not rejected",
            failures,
        )
        expect(
            "strict-json-envelope" in failed_check_ids(run),
            f"non-finite JSON token {token} was not rejected by strict-json-envelope",
            failures,
        )
        expect(
            not any(run["candidates"].values()),
            f"non-finite JSON token {token} leaked candidates",
            failures,
        )

    # Codex P1: quality scoring must compare extracted semantics, not merely
    # predicate/event-type presence. A good deterministic fixture must pass.
    good_quantity = build_run(quantity_case, quantity_raw)
    expect(
        quality(quantity_case, good_quantity)["pass"] is True,
        "gold quantity extraction did not pass semantic scorer",
        failures,
    )

    wrong_value = copy.deepcopy(good_quantity)
    wrong_value["candidates"]["claims"][0]["value"]["value"] = 999
    expect(
        quality(quantity_case, wrong_value)["pass"] is False,
        "wrong quantity value passed semantic scorer",
        failures,
    )

    wrong_unit = copy.deepcopy(good_quantity)
    wrong_unit["candidates"]["claims"][0]["value"]["unit"] = "vehicles"
    expect(
        quality(quantity_case, wrong_unit)["pass"] is False,
        "wrong quantity unit passed semantic scorer",
        failures,
    )

    extra_claim = copy.deepcopy(good_quantity)
    hallucinated = copy.deepcopy(extra_claim["candidates"]["claims"][0])
    hallucinated["candidate_id"] = "CAND-CLAIM-QUANTITY-HALLUCINATED"
    extra_claim["candidates"]["claims"].append(hallucinated)
    expect(
        quality(quantity_case, extra_claim)["pass"] is False,
        "extra allowlisted quantity claim passed semantic scorer",
        failures,
    )

    delivery_case = cases["TRIAL-EN-DELIVERY"]
    good_delivery = build_run(delivery_case, fake_output(delivery_case))
    expect(
        quality(delivery_case, good_delivery)["pass"] is True,
        "gold delivery extraction did not pass semantic scorer",
        failures,
    )

    wrong_date = copy.deepcopy(good_delivery)
    wrong_date["candidates"]["events"][0]["occurred_at"] = {
        "value": "2021-12-10",
        "precision": "day",
    }
    expect(
        quality(delivery_case, wrong_date)["pass"] is False,
        "wrong event date passed semantic scorer",
        failures,
    )

    wrong_participant = copy.deepcopy(good_delivery)
    wrong_participant["candidates"]["events"][0]["participants"][0]["role"] = "manufacturer"
    expect(
        quality(delivery_case, wrong_participant)["pass"] is False,
        "wrong event participant relationship passed semantic scorer",
        failures,
    )

    # Codex P2: the insufficient-evidence gold case means a valid empty JSON
    # envelope rejected specifically for no substantive candidates. Malformed
    # JSON must not receive the same quality pass.
    insufficient_case = cases["TRIAL-INSUFFICIENT"]
    empty_run = build_run(insufficient_case, fake_output(insufficient_case))
    malformed_run = build_run(insufficient_case, "not-json")
    expect(
        quality(insufficient_case, empty_run)["pass"] is True,
        "structured empty extraction did not satisfy insufficient-evidence gold",
        failures,
    )
    expect(
        "no-substantive-candidates" in failed_check_ids(empty_run),
        "structured empty extraction lacks no-substantive-candidates reason",
        failures,
    )
    expect(
        quality(insufficient_case, malformed_run)["pass"] is False,
        "malformed JSON incorrectly passed insufficient-evidence quality check",
        failures,
    )
    expect(
        "strict-json-envelope" in failed_check_ids(malformed_run),
        "malformed JSON lacks strict-json-envelope rejection reason",
        failures,
    )

    if failures:
        print("M4 model-trial Codex reconciliation validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated Codex reconciliation regressions: workflow-dispatch inputs remain out of Bash source; "
        "non-finite JSON fails closed; claim values/units/counts and event dates/participants are scored; "
        "structured no-evidence rejection remains distinct from malformed JSON."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
