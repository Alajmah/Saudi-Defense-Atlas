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
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ADAPTER_VERSION,
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


def copilot_invoker(command: str, model: str, timeout_seconds: int):
    def invoke(prompt: str) -> str:
        result = subprocess.run(
            [
                command,
                "-p",
                prompt,
                "-s",
                "--stream=off",
                "--no-ask-user",
                "--no-custom-instructions",
                "--disable-builtin-mcps",
                "--deny-tool=read,write,shell,url,memory",
                f"--model={model}",
            ],
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
        return result.stdout.strip()

    return invoke


def normalize_name(value: str) -> str:
    return " ".join(value.casefold().split())


def observed_entity_names(run: dict[str, Any]) -> set[str]:
    result: set[str] = set()
    for entity in run.get("candidates", {}).get("entities", []):
        names = entity.get("names", {}) if isinstance(entity, dict) else {}
        if not isinstance(names, dict):
            continue
        for value in names.values():
            if isinstance(value, str) and value.strip():
                result.add(normalize_name(value))
    return result


def evaluate_case(case: dict[str, Any], *, invoked: bool, blocked: bool, run: dict[str, Any] | None) -> dict[str, Any]:
    gold = case["gold"]
    expected_status = gold["expected_status"]
    checks: list[dict[str, Any]] = []

    if expected_status == "blocked_before_invocation":
        checks.append({"id": "blocked-before-invocation", "pass": blocked and not invoked and run is None})
        return {"pass": all(check["pass"] for check in checks), "checks": checks}

    if run is None:
        return {"pass": False, "checks": [{"id": "run-present", "pass": False}]}

    observed_status = run["validation"]["status"]
    checks.append({"id": "status", "pass": observed_status == expected_status, "observed": observed_status, "expected": expected_status})

    if observed_status == "accepted_for_candidate_review":
        names = observed_entity_names(run)
        required_names = {normalize_name(value) for value in gold.get("required_entity_names", [])}
        predicates = {
            claim.get("predicate_id")
            for claim in run["candidates"].get("claims", [])
            if isinstance(claim, dict)
        }
        events = {
            event.get("event_type")
            for event in run["candidates"].get("events", [])
            if isinstance(event, dict)
        }
        required_predicates = set(gold.get("required_predicates", []))
        required_events = set(gold.get("required_event_types", []))
        checks.extend(
            [
                {"id": "required-entity-names", "pass": required_names.issubset(names), "missing": sorted(required_names - names)},
                {"id": "required-predicates", "pass": required_predicates.issubset(predicates), "missing": sorted(required_predicates - predicates)},
                {"id": "required-event-types", "pass": required_events.issubset(events), "missing": sorted(required_events - events)},
            ]
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

    if not any(os.environ.get(name) for name in ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")):
        raise SystemExit(
            "Copilot CLI credential missing; set COPILOT_GITHUB_TOKEN (preferred for this personal-repository trial), GH_TOKEN, or GITHUB_TOKEN"
        )

    version = cli_version(args.copilot_command)
    trace = ModelTrace(
        provider="github-copilot-cli",
        model=args.model,
        model_version=args.model,
        adapter_version=f"{ADAPTER_VERSION};copilot-cli={version}",
    )
    invoke = copilot_invoker(args.copilot_command, args.model, args.timeout_seconds)
    validator = build_schema_validator()

    results: list[dict[str, Any]] = []
    latencies: list[float] = []
    total_started = time.monotonic()
    invocation_count = 0
    accepted = 0
    rejected = 0
    blocked = 0
    integrity_failures = 0

    for case in cases:
        case_started = time.monotonic()
        try:
            outcome = execute_trial_case(case=case, model_trace=trace, invoke=invoke)
        except (RuntimeError, subprocess.SubprocessError) as exc:
            results.append(
                {
                    "case_id": case.get("id"),
                    "invoked": True,
                    "blocked_reason": None,
                    "execution_error": str(exc)[:512],
                    "quality": {"pass": False, "checks": [{"id": "execution", "pass": False}]},
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
        if run is not None:
            schema_failures = [error.message for error in validator.iter_errors(run)]
            if schema_failures:
                run = reject_schema_invalid_run(run, schema_failures)
                second_pass = [error.message for error in validator.iter_errors(run)]
                if second_pass:
                    integrity_failures += 1
                    schema_failures.extend(f"rejected-run-invalid: {error}" for error in second_pass)
            if run is not None:
                try:
                    validate_ai_extraction_run(queue_item=case["queue_item"], run=run)
                except AIExtractionBoundaryError as exc:
                    integrity_failures += 1
                    schema_failures.append(f"boundary: {exc}")

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
                "schema_or_boundary_failures": schema_failures,
                "quality": quality,
                "run": run,
            }
        )

    total_seconds = time.monotonic() - total_started
    quality_passes = sum(1 for result in results if result["quality"]["pass"])
    throughput = invocation_count / total_seconds if total_seconds > 0 else None

    report = {
        "report_version": "m4-model-extraction-live-trial-v0.1",
        "corpus_version": corpus_version,
        "provider": "github-copilot-cli",
        "model": args.model,
        "copilot_cli_version": version,
        "adapter_version": ADAPTER_VERSION,
        "case_count": len(cases),
        "invocation_count": invocation_count,
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
            "reason": "Copilot CLI trial runner does not expose a stable per-invocation monetary-cost field; no cost claim is made.",
        },
        "qualification": {
            "candidate_only_boundary_exercised": invocation_count > 0,
            "synthetic_corpus_only": True,
            "representative_batch_scale_qualified": False,
            "production_model_pipeline_qualified": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "results": results,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(
        json.dumps(
            {
                "case_count": report["case_count"],
                "invocation_count": invocation_count,
                "accepted": accepted,
                "rejected": rejected,
                "blocked": blocked,
                "integrity_failures": integrity_failures,
                "quality_pass_rate": report["quality_case_pass_rate"],
                "output": str(args.output),
            },
            sort_keys=True,
        )
    )
    return 1 if integrity_failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
