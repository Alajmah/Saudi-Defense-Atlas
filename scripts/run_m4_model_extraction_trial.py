#!/usr/bin/env python3
"""Run the bounded M4 real-model extraction trial through GitHub Copilot CLI.

The runner uses only the synthetic evaluation corpus. It captures AIExtractionRun
artifacts and aggregate quality/latency evidence; it does not read or write the
canonical knowledge backend and does not publish anything.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.intelligence.ai_extraction_boundary import (  # noqa: E402
    AIExtractionBoundaryError,
    validate_ai_extraction_run,
)
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ADAPTER_VERSION,
    ModelExtractionTrialError,
    ModelTrace,
    execute_trial_case,
    reject_schema_invalid_run,
)

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "m4-model-extraction-eval.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--model", default="gpt-5.4")
    parser.add_argument("--copilot-command", default="copilot")
    parser.add_argument("--timeout-seconds", type=int, default=120)
    parser.add_argument("--max-cases", type=int, default=0, help="0 means all fixture cases")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def load_cases(path: Path) -> tuple[str, list[dict[str, Any]]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    version = payload.get("version")
    cases = payload.get("cases")
    if not isinstance(version, str) or not version:
        raise RuntimeError("evaluation fixture requires version")
    if not isinstance(cases, list) or not cases:
        raise RuntimeError("evaluation fixture requires non-empty cases")
    return version, cases


def build_schema_validator() -> Draft202012Validator:
    schemas, registry = build_registry()
    return Draft202012Validator(
        schemas["ai-extraction-run.schema.json"],
        registry=registry,
        format_checker=FormatChecker(),
    )


def cli_version(command: str) -> str:
    result = subprocess.run(
        [command, "--version"],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    rendered = (result.stdout or result.stderr).strip()
    if not rendered:
        raise RuntimeError("Copilot CLI returned empty version string")
    return rendered[:128]


def copilot_command_args(command: str, model: str, prompt: str) -> list[str]:
    """Return a prompt-mode command with no usable data-access/action tools."""

    return [
        command,
        "-p",
        prompt,
        "-s",
        "--stream=off",
        "--available-tools=ask_user",
        "--no-ask-user",
        "--deny-tool=read,write,shell,url,memory",
        "--disable-builtin-mcps",
        "--no-custom-instructions",
        "--no-remote",
        "--no-remote-export",
        "--no-experimental",
        "--no-auto-update",
        f"--model={model}",
    ]


def copilot_invoker(command: str, model: str, timeout_seconds: int) -> Callable[[str], str]:
    def invoke(prompt: str) -> str:
        result = subprocess.run(
            copilot_command_args(command, model, prompt),
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(
                f"Copilot CLI exited {result.returncode}: {stderr[:300] or 'no stderr'}"
            )
        return result.stdout

    return invoke


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def _entity_names_by_id(run: dict[str, Any]) -> dict[str, set[str]]:
    result: dict[str, set[str]] = {}
    for entity in run.get("candidates", {}).get("entities", []):
        if not isinstance(entity, dict):
            continue
        candidate_id = entity.get("candidate_id")
        names = entity.get("names")
        if not isinstance(candidate_id, str) or not isinstance(names, dict):
            continue
        result[candidate_id] = {
            normalize_name(value)
            for value in names.values()
            if isinstance(value, str) and value.strip()
        }
    return result


def _ref_has_name(ref: Any, expected_name: str, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(ref, dict) or ref.get("kind") != "candidate_entity":
        return False
    candidate_id = ref.get("candidate_id")
    return (
        isinstance(candidate_id, str)
        and normalize_name(expected_name) in names_by_id.get(candidate_id, set())
    )


def _localized_names_match(actual: Any, expected: Any) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if set(actual) != set(expected):
        return False
    return all(
        isinstance(actual.get(locale), str)
        and isinstance(value, str)
        and normalize_name(actual[locale]) == normalize_name(value)
        for locale, value in expected.items()
    )


def _evidence_matches(actual: Any, expected: Any, _: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    for key in ("document_id", "locator", "excerpt_sha256", "capture_assessment"):
        if actual.get(key) != expected.get(key):
            return False
    return True


def _entity_matches(actual: Any, expected: Any, _: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    return (
        actual.get("entity_type") == expected.get("entity_type")
        and actual.get("subtype") == expected.get("subtype")
        and _localized_names_match(actual.get("names"), expected.get("names"))
        and actual.get("aliases", []) == expected.get("aliases", [])
    )


def _value_matches(actual: Any, expected: Any, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    expected_kind = expected.get("kind")
    if actual.get("kind") != expected_kind:
        return False
    if expected_kind == "candidate_entity":
        entity_name = expected.get("entity_name")
        return isinstance(entity_name, str) and _ref_has_name(actual, entity_name, names_by_id)
    return actual == expected


def _claim_matches(actual: Any, expected: Any, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if actual.get("predicate_id") != expected.get("predicate_id"):
        return False
    subject_name = expected.get("subject_name")
    if not isinstance(subject_name, str) or not _ref_has_name(
        actual.get("subject"), subject_name, names_by_id
    ):
        return False
    if not _value_matches(actual.get("value"), expected.get("value"), names_by_id):
        return False

    if "validity" in expected:
        expected_validity = expected.get("validity")
        if expected_validity is None:
            if "validity" in actual:
                return False
        elif actual.get("validity") != expected_validity:
            return False

    if "extraction_assessment" in expected and (
        actual.get("extraction_assessment") != expected.get("extraction_assessment")
    ):
        return False
    return True


def _event_matches(actual: Any, expected: Any, names_by_id: dict[str, set[str]]) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    if actual.get("event_type") != expected.get("event_type"):
        return False
    if actual.get("occurred_at") != expected.get("occurred_at"):
        return False
    if "ended_at" in expected and actual.get("ended_at") != expected.get("ended_at"):
        return False
    if "extraction_assessment" in expected and (
        actual.get("extraction_assessment") != expected.get("extraction_assessment")
    ):
        return False

    actual_participants = actual.get("participants")
    expected_participants = expected.get("participants", [])
    if not isinstance(actual_participants, list) or not isinstance(expected_participants, list):
        return False
    if len(actual_participants) != len(expected_participants):
        return False
    unmatched = list(range(len(actual_participants)))
    for wanted in expected_participants:
        if not isinstance(wanted, dict):
            return False
        wanted_name = wanted.get("entity_name")
        wanted_role = wanted.get("role")
        match_index = next(
            (
                index
                for index in unmatched
                if isinstance(actual_participants[index], dict)
                and actual_participants[index].get("role") == wanted_role
                and isinstance(wanted_name, str)
                and _ref_has_name(
                    actual_participants[index].get("entity"), wanted_name, names_by_id
                )
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched.remove(match_index)

    actual_related = actual.get("related_entities")
    expected_related = expected.get("related_entity_names", [])
    if not isinstance(actual_related, list) or not isinstance(expected_related, list):
        return False
    if len(actual_related) != len(expected_related):
        return False
    unmatched_related = list(range(len(actual_related)))
    for wanted_name in expected_related:
        match_index = next(
            (
                index
                for index in unmatched_related
                if isinstance(wanted_name, str)
                and _ref_has_name(actual_related[index], wanted_name, names_by_id)
            ),
            None,
        )
        if match_index is None:
            return False
        unmatched_related.remove(match_index)
    return True


def _all_expected_records_match(
    actual_records: Any,
    expected_records: Any,
    matcher: Callable[[Any, Any, dict[str, set[str]]], bool],
    names_by_id: dict[str, set[str]],
) -> tuple[bool, list[int]]:
    if not isinstance(actual_records, list) or not isinstance(expected_records, list):
        return False, []
    if len(actual_records) != len(expected_records):
        return False, list(range(len(expected_records)))
    unmatched_actual = list(range(len(actual_records)))
    missing_expected: list[int] = []
    for expected_index, expected in enumerate(expected_records):
        match_index = next(
            (
                index
                for index in unmatched_actual
                if matcher(actual_records[index], expected, names_by_id)
            ),
            None,
        )
        if match_index is None:
            missing_expected.append(expected_index)
        else:
            unmatched_actual.remove(match_index)
    return not missing_expected and not unmatched_actual, missing_expected


def evaluate_case(
    case: dict[str, Any],
    *,
    invoked: bool,
    blocked: bool,
    run: dict[str, Any] | None,
) -> dict[str, Any]:
    gold = case.get("gold")
    if not isinstance(gold, dict):
        return {"pass": False, "checks": [{"id": "gold-present", "pass": False}]}
    expected_status = gold.get("expected_status")
    checks: list[dict[str, Any]] = []

    if expected_status == "blocked_before_invocation":
        checks.append(
            {
                "id": "blocked-before-invocation",
                "pass": blocked and not invoked and run is None,
            }
        )
        return {"pass": all(check["pass"] for check in checks), "checks": checks}

    if run is None:
        return {"pass": False, "checks": [{"id": "run-present", "pass": False}]}

    observed_status = run.get("validation", {}).get("status")
    checks.append(
        {
            "id": "status",
            "pass": observed_status == expected_status,
            "observed": observed_status,
            "expected": expected_status,
        }
    )

    if expected_status == "rejected":
        expected_check = gold.get("expected_rejection_check")
        failed_checks = {
            check.get("check_id")
            for check in run.get("evaluation_trace", {}).get("checks", [])
            if isinstance(check, dict) and check.get("status") == "fail"
        }
        candidates = run.get("candidates")
        candidate_arrays_empty = (
            isinstance(candidates, dict)
            and all(
                candidates.get(name) == []
                for name in ("evidence", "entities", "claims", "events")
            )
        )
        checks.extend(
            [
                {
                    "id": "expected-rejection-check",
                    "pass": isinstance(expected_check, str) and expected_check in failed_checks,
                    "expected": expected_check,
                    "observed": sorted(
                        value for value in failed_checks if isinstance(value, str)
                    ),
                },
                {
                    "id": "rejected-candidates-empty",
                    "pass": candidate_arrays_empty,
                },
            ]
        )
        return {"pass": all(check["pass"] for check in checks), "checks": checks}

    if expected_status != "accepted_for_candidate_review" or observed_status != expected_status:
        return {"pass": False, "checks": checks}

    candidates = run.get("candidates")
    if not isinstance(candidates, dict):
        checks.append({"id": "candidate-object", "pass": False})
        return {"pass": False, "checks": checks}

    names_by_id = _entity_names_by_id(run)
    expected_specs = {
        "evidence": (gold.get("expected_evidence"), _evidence_matches),
        "entities": (gold.get("expected_entities"), _entity_matches),
        "claims": (gold.get("expected_claims"), _claim_matches),
        "events": (gold.get("expected_events"), _event_matches),
    }
    for name, (expected_records, matcher) in expected_specs.items():
        actual_records = candidates.get(name)
        matched, missing = _all_expected_records_match(
            actual_records,
            expected_records,
            matcher,
            names_by_id,
        )
        checks.append(
            {
                "id": f"{name}-semantics",
                "pass": matched,
                "missing_expected_indexes": missing,
                "observed_count": len(actual_records) if isinstance(actual_records, list) else None,
                "expected_count": len(expected_records) if isinstance(expected_records, list) else None,
            }
        )

    return {"pass": all(check["pass"] for check in checks), "checks": checks}


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * fraction)))
    return ordered[index]


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    if args.max_cases < 0:
        raise SystemExit("--max-cases must be >= 0")

    corpus_version, cases = load_cases(args.fixture)
    if args.max_cases:
        cases = cases[: args.max_cases]

    if not any(
        os.environ.get(name)
        for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")
    ):
        raise SystemExit(
            "Copilot CLI credential missing; set COPILOT_GITHUB_TOKEN "
            "(preferred for this personal-repository trial), GH_TOKEN, or GITHUB_TOKEN"
        )

    version = cli_version(args.copilot_command)
    trace = ModelTrace(
        provider="github-copilot-cli",
        model=args.model,
        model_version="provider-managed-unknown",
        adapter_version=ADAPTER_VERSION,
    )
    try:
        trace.as_dict()
    except ModelExtractionTrialError as exc:
        raise SystemExit(f"invalid model trace: {exc}") from exc

    invoke = copilot_invoker(args.copilot_command, args.model, args.timeout_seconds)
    validator = build_schema_validator()

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    total_started = time.monotonic()
    invocation_count = 0
    validated_run_count = 0
    accepted = 0
    rejected = 0
    blocked = 0
    integrity_failures = 0

    for case in cases:
        case_started = time.monotonic()
        try:
            outcome = execute_trial_case(case=case, model_trace=trace, invoke=invoke)
        except (ModelExtractionTrialError, RuntimeError, subprocess.SubprocessError) as exc:
            results.append(
                {
                    "case_id": case.get("id"),
                    "invoked": True,
                    "blocked_reason": None,
                    "execution_error": str(exc)[:512],
                    "quality": {
                        "pass": False,
                        "checks": [{"id": "execution", "pass": False}],
                    },
                    "run": None,
                }
            )
            invocation_count += 1
            integrity_failures += 1
            continue

        latency = time.monotonic() - case_started
        if outcome.invoked:
            invocation_count += 1
            latencies.append(latency)
        else:
            blocked += 1

        run = outcome.run
        schema_failures: list[str] = []
        run_integrity_valid = False
        if run is not None:
            schema_failures = [error.message for error in validator.iter_errors(run)]
            if schema_failures:
                run = reject_schema_invalid_run(run, schema_failures)

            second_pass = [error.message for error in validator.iter_errors(run)]
            if second_pass:
                integrity_failures += 1
                schema_failures.extend(
                    f"rejected-run-invalid: {error}" for error in second_pass
                )
            else:
                try:
                    validate_ai_extraction_run(queue_item=case["queue_item"], run=run)
                except AIExtractionBoundaryError as exc:
                    integrity_failures += 1
                    schema_failures.append(f"boundary: {exc}")
                else:
                    run_integrity_valid = True
                    validated_run_count += 1

            if run_integrity_valid:
                if run["validation"]["status"] == "accepted_for_candidate_review":
                    accepted += 1
                else:
                    rejected += 1

        quality = evaluate_case(
            case,
            invoked=outcome.invoked,
            blocked=not outcome.invoked,
            run=run,
        )
        results.append(
            {
                "case_id": case["id"],
                "invoked": outcome.invoked,
                "blocked_reason": outcome.blocked_reason,
                "latency_seconds": round(latency, 6),
                "run_integrity_valid": run_integrity_valid,
                "schema_or_boundary_failures": schema_failures,
                "quality": quality,
                "run": run,
            }
        )

    total_seconds = time.monotonic() - total_started
    quality_passes = sum(1 for result in results if result["quality"]["pass"])
    throughput = invocation_count / total_seconds if total_seconds > 0 else None

    report = {
        "report_version": "m4-model-extraction-live-trial-v0.3",
        "corpus_version": corpus_version,
        "provider": "github-copilot-cli",
        "requested_model": args.model,
        "provider_checkpoint_version": None,
        "copilot_cli_version": version,
        "adapter_version": ADAPTER_VERSION,
        "case_count": len(cases),
        "invocation_count": invocation_count,
        "validated_run_count": validated_run_count,
        "accepted_run_count": accepted,
        "rejected_run_count": rejected,
        "blocked_before_invocation_count": blocked,
        "integrity_failure_count": integrity_failures,
        "quality_case_pass_count": quality_passes,
        "quality_case_pass_rate": quality_passes / len(results) if results else None,
        "latency_seconds": {
            "median": statistics.median(latencies) if latencies else None,
            "p95_observed": percentile(latencies, 0.95),
            "max": max(latencies) if latencies else None,
        },
        "observed_throughput_invocations_per_second": throughput,
        "cost": {
            "measured": False,
            "value": None,
            "reason": (
                "Copilot CLI trial runner does not expose a stable per-invocation "
                "monetary-cost field; no cost claim is made."
            ),
        },
        "qualification": {
            "candidate_only_boundary_exercised": validated_run_count > 0,
            "trial_integrity_clean": integrity_failures == 0,
            "quality_expectations_all_pass": bool(results)
            and quality_passes == len(results),
            "synthetic_corpus_only": True,
            "representative_batch_scale_qualified": False,
            "production_model_pipeline_qualified": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "invocation_count": invocation_count,
                "validated_runs": validated_run_count,
                "accepted": accepted,
                "rejected": rejected,
                "blocked": blocked,
                "integrity_failures": integrity_failures,
                "quality_pass_rate": report["quality_case_pass_rate"],
                "output": str(args.output),
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 1 if integrity_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
