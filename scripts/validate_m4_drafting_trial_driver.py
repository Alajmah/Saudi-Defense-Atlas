#!/usr/bin/env python3
"""Validate the M4 live drafting trial driver without network calls.

Tests the actual report builder, the orchestration path (with both a
succeeding and a failing fake invoker), every pre-invocation gate (route
ambiguity, entitlement, git-state, overwrite refusal), the hash-chain
consistency check, the invocation-attempt provenance, the editorial
placeholder, the qualification flags, the sidecar, and deterministic
serialization.
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_m4_drafting_trial import (  # noqa: E402
    DEFAULT_FIXTURE,
    DEFAULT_TERMINOLOGY,
    REPORT_VERSION,
    TrialGateError,
    build_drafting_context_from_fixture,
    build_trial_report,
    check_attestation_route_binding,
    check_entitlement,
    check_git_state,
    check_route_args,
    execute_draft_invocation,
    load_fixture,
    write_report_with_sidecar,
)
from services.intelligence.bilingual_drafting import (  # noqa: E402
    DraftModelTrace,
    build_bilingual_draft_run,
    load_terminology,
    prepare_draft_input,
)

TERMINOLOGY_PATH = ROOT / "data" / "terminology" / "bilingual-terminology-v0.1.json"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_gate_error(label: str, fn, failures: list[str]) -> None:
    try:
        fn()
    except TrialGateError:
        return
    failures.append(f"{label} did not fail closed")


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def good_output() -> dict[str, Any]:
    return {
        "units": [
            {
                "unit_id": "UNIT-QTY",
                "claim_ids": ["SDA-CLAIM-CEDAR-QTY"],
                "evidence_ids": ["SDA-EVID-CEDAR-1"],
                "prose": {
                    "en": "Project Cedar carries a contracted quantity of 12 aircraft as of 2024-03-15.",
                    "ar": "يشمل مشروع الأرز كمية متعاقدة قدرها 12 طائرة بتاريخ 2024-03-15.",
                },
            },
            {
                "unit_id": "UNIT-MANUFACTURER",
                "claim_ids": ["SDA-CLAIM-FALCONX-MANUFACTURER"],
                "evidence_ids": ["SDA-EVID-FALCONX-1"],
                "prose": {
                    "en": "Atlas Aerospace manufactures the Falcon-X aircraft.",
                    "ar": "تُصنّع شركة أطلس للصناعات الجوية طائرة فالكون-إكس.",
                },
            },
        ],
        "undrafted_claim_ids": [],
        "rendered_unknown_ids": ["UNK-FALCONX-OPERATOR"],
        "omitted_unknown_ids": [],
    }


def setup():
    fixture = load_fixture(DEFAULT_FIXTURE)
    terminology_payload = json.loads(TERMINOLOGY_PATH.read_text(encoding="utf-8"))
    terminology = load_terminology(terminology_payload)
    context = build_drafting_context_from_fixture(fixture, terminology, "2026-10-03T00:00:00Z")
    rendered, _ = prepare_draft_input(context, terminology)
    trace = DraftModelTrace(
        provider="zai-openai-compatible-api", model="glm-5.3", model_version="provider-managed-unknown"
    )
    return fixture, terminology_payload, terminology, context, rendered, trace


def build_report(
    terminology_payload, context, rendered, raw, draft_run, error, attempted, count
):
    return build_trial_report(
        fixture=load_fixture(DEFAULT_FIXTURE),
        terminology_payload=terminology_payload,
        context=context,
        rendered_prompt=rendered,
        raw_model_output=raw,
        draft_run=draft_run,
        execution_error=error,
        invocation_attempted=attempted,
        invocation_count=count,
        requested_model="glm-5.3",
        base_url="https://api.z.ai/api/coding/paas/v4",
        base_url_source="endpoint:coding-plan",
        endpoint_arg="coding-plan",
        entitlement_attestation="coding-plan drafting attestation",
        reviewed_head="a" * 40,
        git_head="a" * 40,
        git_ref="refs/heads/main",
        worktree_clean=True,
        fixture_path=DEFAULT_FIXTURE,
        terminology_path=DEFAULT_TERMINOLOGY,
        elapsed_seconds=1.234,
    )


def main() -> int:
    failures: list[str] = []
    fixture, terminology_payload, terminology, context, rendered, trace = setup()
    raw_good = json.dumps(good_output(), ensure_ascii=False)

    # --- DTD-03R: pre-invocation gate regressions ---
    # Route ambiguity
    expect_gate_error(
        "base-url + zai-endpoint",
        lambda: check_route_args("https://a", "coding-plan", ""),
        failures,
    )
    expect_gate_error(
        "zai-endpoint + env",
        lambda: check_route_args(None, "coding-plan", "https://env"),
        failures,
    )
    expect_gate_error(
        "base-url + env",
        lambda: check_route_args("https://a", None, "https://env"),
        failures,
    )
    expect_gate_error(
        "all three",
        lambda: check_route_args("https://a", "coding-plan", "https://env"),
        failures,
    )
    # Exactly one is fine
    try:
        check_route_args(None, "coding-plan", "")
        check_route_args("https://api.z.ai/api/coding/paas/v4", None, "")
        check_route_args(None, None, "https://api.z.ai/api/coding/paas/v4")
    except TrialGateError:
        failures.append("single-route check_route_args failed on a valid combination")

    # Entitlement
    expect_gate_error("empty attestation", lambda: check_entitlement(""), failures)
    expect_gate_error("blank attestation", lambda: check_entitlement("   "), failures)
    try:
        check_entitlement("  non-empty  ")
    except TrialGateError:
        failures.append("valid attestation was rejected")

    # Git state
    expect_gate_error(
        "empty HEAD",
        lambda: check_git_state("", True, "a" * 40),
        failures,
    )
    expect_gate_error(
        "dirty worktree",
        lambda: check_git_state("a" * 40, False, "a" * 40),
        failures,
    )
    expect_gate_error(
        "unknown worktree",
        lambda: check_git_state("a" * 40, None, "a" * 40),
        failures,
    )
    expect_gate_error(
        "HEAD != reviewed head",
        lambda: check_git_state("b" * 40, True, "a" * 40),
        failures,
    )
    try:
        check_git_state("a" * 40, True, "a" * 40)
    except TrialGateError:
        failures.append("valid git state was rejected")

    # Attestation-route binding
    expect_gate_error(
        "coding URL without coding attestation",
        lambda: check_attestation_route_binding(
            "some attestation", "https://api.z.ai/api/coding/paas/v4"
        ),
        failures,
    )
    try:
        check_attestation_route_binding(
            "coding-plan attestation", "https://api.z.ai/api/coding/paas/v4"
        )
        check_attestation_route_binding(
            "prepaid attestation", "https://api.z.ai/api/paas/v4"
        )
    except TrialGateError:
        failures.append("route-bound attestation was rejected")

    # --- DTD-04R: orchestration path with failing invoker ---
    def failing_invoke(prompt: str) -> str:
        raise RuntimeError("Z.ai API returned HTTP 500: internal error")

    fail_run, fail_error, fail_raw, fail_elapsed = execute_draft_invocation(
        context=context,
        terminology=terminology,
        model_trace=trace,
        invoke_fn=failing_invoke,
    )
    expect(fail_run is None, "failing invoker produced a draft run", failures)
    expect(fail_error is not None, "failing invoker did not produce an error", failures)
    expect(fail_raw is None, "failing invoker produced raw output", failures)

    # --- Success path through the orchestration ---
    def fake_invoke(prompt: str) -> str:
        return raw_good

    ok_run, ok_error, ok_raw, ok_elapsed = execute_draft_invocation(
        context=context,
        terminology=terminology,
        model_trace=trace,
        invoke_fn=fake_invoke,
    )
    expect(ok_error is None, f"succeeding invoker errored: {ok_error}", failures)
    expect(ok_raw == raw_good, "raw output was not captured verbatim", failures)
    expect(
        ok_run is not None and ok_run["validation"]["status"] == "accepted_for_editorial_review",
        f"draft run not accepted: {ok_run and ok_run['validation']['errors'][:2]}",
        failures,
    )

    # --- Build the report through the actual builder ---
    report = build_report(
        terminology_payload, context, rendered, ok_raw, ok_run, None, True, 1
    )
    expect(report["report_version"] == REPORT_VERSION, "report version drifted", failures)
    expect(
        report["entitlement"]["attestation"] == "coding-plan drafting attestation"
        and report["entitlement"]["standing_extraction_entitlement_covers_drafting"] is False
        and report["entitlement"]["resolved_base_url"] == "https://api.z.ai/api/coding/paas/v4",
        "entitlement block wrong",
        failures,
    )
    expect(report["reviewed_head"] == "a" * 40, "reviewed head not recorded", failures)
    expect(
        report["terminology"]["registry_version"],
        "registry version missing",
        failures,
    )
    expect(
        report["evidence"]["rendered_model_input"] == rendered
        and report["evidence"]["raw_model_output"] == raw_good,
        "frozen evidence bytes wrong",
        failures,
    )
    expect(
        report["invocation"]["attempted"] is True and report["invocation"]["count"] == 1,
        "invocation provenance wrong",
        failures,
    )
    ed = report["editorial_assessment"]
    expect(
        ed["status"] == "pending_human_review" and ed["mechanical_score"] is None,
        "editorial placeholder wrong",
        failures,
    )
    q = report["qualification"]
    expect(
        q["structural_mechanical_acceptance"] is True and q["editorial_quality_qualified"] is False,
        "qualification flags wrong",
        failures,
    )

    # --- Failure report through the actual builder ---
    failure_report = build_report(
        terminology_payload, context, rendered, None, None, "Z.ai API returned HTTP 500: internal error", True, 1
    )
    expect(
        failure_report["invocation"]["attempted"] is True
        and failure_report["invocation"]["count"] == 1,
        "failure report invocation provenance wrong",
        failures,
    )
    expect(
        failure_report["execution_error"] is not None
        and failure_report["structural_result"] is None
        and failure_report["evidence"]["rendered_model_input"] == rendered,
        "failure report fields wrong",
        failures,
    )
    expect(
        failure_report["qualification"]["structural_mechanical_acceptance"] is False,
        "failure report claims acceptance",
        failures,
    )

    # --- DTD-02R: hash-chain consistency ---
    tampered = dict(ok_run)
    tampered["raw_output_sha256"] = "0" * 64
    try:
        build_report(terminology_payload, context, rendered, ok_raw, tampered, None, True, 1)
        failures.append("tampered draft-run hash chain was not detected")
    except RuntimeError:
        pass

    # --- DTD-02R: immutable artifact writer ---
    with tempfile.TemporaryDirectory() as tmpdir:
        out_a = Path(tmpdir) / "a" / "report.json"
        sha_a = write_report_with_sidecar(out_a, report)
        # Writing the same report to a different path yields the same bytes.
        out_b = Path(tmpdir) / "b" / "report.json"
        sha_b = write_report_with_sidecar(out_b, report)
        expect(sha_a == sha_b, "serialization is not deterministic", failures)
        # Overwriting is refused.
        expect_gate_error(
            "overwrite existing report",
            lambda: write_report_with_sidecar(out_a, report),
            failures,
        )
        # Sidecar overwrite is refused independently.
        out_c = Path(tmpdir) / "c" / "report.json"
        out_c.parent.mkdir(parents=True)
        out_c.with_name(out_c.name + ".sha256").write_text("existing")
        expect_gate_error(
            "overwrite existing sidecar",
            lambda: write_report_with_sidecar(out_c, report),
            failures,
        )
        # Round-trip: the reparsed report retains the frozen bytes.
        reparsed = json.loads(out_a.read_text(encoding="utf-8"))
        expect(
            reparsed["evidence"]["raw_model_output"] == raw_good,
            "serialization round-trip lost raw output",
            failures,
        )

    if failures:
        print("M4 drafting trial driver validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated the M4 live drafting trial driver: all pre-invocation gates (route "
        "ambiguity in every combination, entitlement, attestation-route binding, git state "
        "with reviewed-head match, overwrite refusal for report and sidecar) fail closed "
        "deterministically; the orchestration path runs a failing invoker to a bounded "
        "failure report with invocation_attempted/count provenance; the report builder "
        "freezes exact rendered input and raw output bytes with matching hashes, records "
        "registry version alongside digests, carries a reviewed-head pin, separates the "
        "editorial placeholder, and detects tampered draft-run hash chains; serialization "
        "is deterministic and sidecars are immutable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
