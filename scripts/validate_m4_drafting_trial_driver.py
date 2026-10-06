#!/usr/bin/env python3
"""Validate the M4 live drafting trial driver without network calls.

Tests the actual report builder, the orchestration path (with both a
succeeding and a failing fake invoker, proving the attempt count from the
orchestration itself against the invoker's own call record), every
pre-invocation gate (route ambiguity, entitlement, git-state, artifact
existence, overwrite refusal including exclusive creation under a lost
existence race), the complete hash-chain consistency check (raw output,
rendered input, embedded context block, context object, registry digest,
delivery block), the editorial placeholder, the qualification flags, the
sidecar, and deterministic serialization.
"""

from __future__ import annotations

import argparse
import copy
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
    check_artifacts_absent,
    check_attestation_route_binding,
    check_entitlement,
    check_git_state,
    check_route_args,
    execute_draft_invocation,
    load_fixture,
    run_trial,
    write_report_with_sidecar,
)
from services.intelligence.bilingual_drafting import (  # noqa: E402
    DraftModelTrace,
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

    # --- DCC-10: before_invoke fires only at the actual provider boundary ---
    preboundary_hooks: list[str] = []
    preboundary_calls: list[str] = []
    invalid_context = copy.deepcopy(context)
    invalid_context["claims"][0]["predicate_id"] = ""

    def preboundary_hook(prompt: str) -> None:
        preboundary_hooks.append(prompt)

    def preboundary_invoke(prompt: str) -> str:
        preboundary_calls.append(prompt)
        return raw_good

    bad_run, bad_error, bad_raw, _, bad_attempts = execute_draft_invocation(
        context=invalid_context,
        terminology=terminology,
        model_trace=trace,
        invoke_fn=preboundary_invoke,
        before_invoke=preboundary_hook,
    )
    expect(bad_run is None and bad_error is not None, "pre-invoker boundary failure was not captured", failures)
    expect(bad_raw is None and bad_attempts == 0, "pre-invoker failure consumed an attempt", failures)
    expect(not preboundary_hooks, "before_invoke fired before the actual provider boundary", failures)
    expect(not preboundary_calls, "pre-invoker boundary failure reached provider", failures)

    # --- DTD-04R: orchestration path with failing invoker ---
    failing_calls: list[str] = []

    def failing_invoke(prompt: str) -> str:
        failing_calls.append(prompt)
        raise RuntimeError("Z.ai API returned HTTP 500: internal error")

    failing_hooks: list[str] = []

    fail_run, fail_error, fail_raw, fail_elapsed, fail_attempts = (
        execute_draft_invocation(
            context=context,
            terminology=terminology,
            model_trace=trace,
            invoke_fn=failing_invoke,
            before_invoke=lambda prompt: failing_hooks.append(prompt),
        )
    )
    expect(fail_run is None, "failing invoker produced a draft run", failures)
    expect(fail_error is not None, "failing invoker did not produce an error", failures)
    expect(fail_raw is None, "failing invoker produced raw output", failures)
    # DTD-04RR: the attempt count comes from the orchestration itself and
    # must equal what the invoker actually observed — one call, no retry.
    expect(
        fail_attempts == len(failing_calls) == 1,
        f"failing invocation count {fail_attempts} != invoker-observed {len(failing_calls)}",
        failures,
    )
    expect(
        len(failing_hooks) == 1,
        f"failing invocation hook count {len(failing_hooks)} != 1",
        failures,
    )
    expect(
        failing_hooks == failing_calls,
        "failing invocation hook did not receive the exact provider prompt",
        failures,
    )

    # --- Success path through the orchestration ---
    ok_calls: list[str] = []

    def fake_invoke(prompt: str) -> str:
        ok_calls.append(prompt)
        return raw_good

    ok_hooks: list[str] = []
    ok_run, ok_error, ok_raw, ok_elapsed, ok_attempts = execute_draft_invocation(
        context=context,
        terminology=terminology,
        model_trace=trace,
        invoke_fn=fake_invoke,
        before_invoke=lambda prompt: ok_hooks.append(prompt),
    )
    expect(ok_error is None, f"succeeding invoker errored: {ok_error}", failures)
    expect(ok_raw == raw_good, "raw output was not captured verbatim", failures)
    expect(
        ok_attempts == len(ok_calls) == 1,
        f"success invocation count {ok_attempts} != invoker-observed {len(ok_calls)}",
        failures,
    )
    expect(
        len(ok_hooks) == 1,
        f"success invocation hook count {len(ok_hooks)} != 1",
        failures,
    )
    expect(
        ok_hooks == ok_calls,
        "success invocation hook did not receive the exact provider prompt",
        failures,
    )
    expect(
        ok_run is not None and ok_run["validation"]["status"] == "accepted_for_editorial_review",
        f"draft run not accepted: {ok_run and ok_run['validation']['errors'][:2]}",
        failures,
    )

    # --- Build the report through the actual builder, with the
    # orchestration-derived attempt provenance (not hard-coded values) ---
    report = build_report(
        terminology_payload, context, rendered, ok_raw, ok_run, None,
        ok_attempts > 0, ok_attempts,
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
        report["invocation"]["attempted"] is True
        and report["invocation"]["count"] == ok_attempts == 1,
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

    # --- Failure report through the actual builder (orchestration-derived) ---
    failure_report = build_report(
        terminology_payload, context, rendered, None, None,
        "Z.ai API returned HTTP 500: internal error", fail_attempts > 0, fail_attempts,
    )
    expect(
        failure_report["invocation"]["attempted"] is True
        and failure_report["invocation"]["count"] == fail_attempts == 1,
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

    # --- DTD-02RR-B: complete hash-chain consistency ---
    def tampered_run(**overrides) -> dict[str, Any]:
        clone = copy.deepcopy(ok_run)
        for key, value in overrides.items():
            if key == "prompt_trace":
                trace_clone = dict(clone["prompt_trace"])
                trace_clone.update(value)
                clone["prompt_trace"] = trace_clone
            else:
                clone[key] = value
        return clone

    for label, overrides in (
        ("raw_output_sha256", {"raw_output_sha256": "0" * 64}),
        (
            "input_context_sha256",
            {"input_context_sha256": "0" * 64},
        ),
        (
            "prompt_trace.terminology_registry_sha256",
            {"prompt_trace": {"terminology_registry_sha256": "0" * 64}},
        ),
        (
            "prompt_trace.terminology_delivery_sha256",
            {"prompt_trace": {"terminology_delivery_sha256": "0" * 64}},
        ),
        (
            "prompt_trace.rendered_input_sha256",
            {"prompt_trace": {"rendered_input_sha256": "0" * 64}},
        ),
    ):
        try:
            build_report(
                terminology_payload, context, rendered, ok_raw,
                tampered_run(**overrides), None, True, 1,
            )
            failures.append(f"tampered {label} was not detected")
        except RuntimeError:
            pass

    # A context mutated after invocation no longer matches the frozen chain.
    mutated_context = copy.deepcopy(context)
    mutated_context["claims"][0]["evidence_links"][0]["evidence_id"] = "SDA-EVID-TAMPERED"
    try:
        build_report(
            terminology_payload, mutated_context, rendered, ok_raw, ok_run, None, True, 1
        )
        failures.append("post-invocation context mutation was not detected")
    except RuntimeError:
        pass

    # --- DTD-02RR-A: artifact existence is a pre-invocation gate ---
    with tempfile.TemporaryDirectory() as tmpdir:
        absent_ok = Path(tmpdir) / "fresh" / "report.json"
        try:
            check_artifacts_absent(absent_ok)
        except TrialGateError:
            failures.append("check_artifacts_absent refused fresh paths")

        existing_report = Path(tmpdir) / "r" / "report.json"
        existing_report.parent.mkdir(parents=True)
        existing_report.write_text("occupied", encoding="utf-8")
        expect_gate_error(
            "check_artifacts_absent with existing report",
            lambda: check_artifacts_absent(existing_report),
            failures,
        )

        existing_sidecar = Path(tmpdir) / "s" / "report.json"
        existing_sidecar.parent.mkdir(parents=True)
        existing_sidecar.with_name(existing_sidecar.name + ".sha256").write_text(
            "occupied", encoding="utf-8"
        )
        expect_gate_error(
            "check_artifacts_absent with existing sidecar only",
            lambda: check_artifacts_absent(existing_sidecar),
            failures,
        )

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
        # Exclusive creation holds even if the existence check loses a race:
        # with exists() lying, "xb" creation of the occupied path still refuses.
        out_d = Path(tmpdir) / "d" / "report.json"
        out_d.parent.mkdir(parents=True)
        out_d.write_text("occupied", encoding="utf-8")
        original_exists = Path.exists
        Path.exists = lambda self: False  # type: ignore[assignment]
        try:
            expect_gate_error(
                "exclusive creation under lost existence race",
                lambda: write_report_with_sidecar(out_d, report),
                failures,
            )
        finally:
            Path.exists = original_exists  # type: ignore[assignment]
        expect(
            out_d.read_text(encoding="utf-8") == "occupied",
            "lost-race write clobbered the occupied artifact",
            failures,
        )
        # Round-trip: the reparsed report retains the frozen bytes.
        reparsed = json.loads(out_a.read_text(encoding="utf-8"))
        expect(
            reparsed["evidence"]["raw_model_output"] == raw_good,
            "serialization round-trip lost raw output",
            failures,
        )

    # --- DTD-02RRR: launch-level regression through the actual launch
    # sequence — a pre-existing report or sidecar (or any earlier gate
    # refusal) means zero credential reads, zero provider constructions,
    # and zero invoker calls.
    def make_launch_args(output: Path) -> argparse.Namespace:
        return argparse.Namespace(
            fixture=DEFAULT_FIXTURE,
            model="glm-5.3",
            zai_endpoint="coding-plan",
            base_url=None,
            reviewed_head="a" * 40,
            entitlement_attestation="coding-plan drafting attestation",
            timeout_seconds=30,
            output=output,
        )

    def spy_launch(output: Path, reviewed_head: str = "a" * 40):
        key_reads: list[int] = []
        constructions: list[dict] = []
        invoker_calls: list[str] = []

        def require_key() -> str:
            key_reads.append(1)
            return "spy-key"

        def factory(**kwargs):
            constructions.append(kwargs)

            def spy(prompt: str) -> str:
                invoker_calls.append(prompt)
                return raw_good

            return spy

        args = make_launch_args(output)
        args.reviewed_head = reviewed_head
        try:
            summary = run_trial(
                args=args,
                env_url="",
                git_head="a" * 40,
                git_ref="refs/heads/m4/live-drafting-driver",
                worktree_clean=True,
                require_api_key=require_key,
                invoke_factory=factory,
                created_at_fn=lambda: "2026-10-03T00:00:00Z",
            )
            outcome = "ran"
        except TrialGateError:
            summary = None
            outcome = "refused"
        return outcome, summary, key_reads, constructions, invoker_calls

    with tempfile.TemporaryDirectory() as tmpdir:
        # Pre-existing report: the launch refuses with zero provider activity.
        occupied_report = Path(tmpdir) / "occupied" / "report.json"
        occupied_report.parent.mkdir(parents=True)
        occupied_report.write_text("occupied", encoding="utf-8")
        outcome, _, key_reads, constructions, invoker_calls = spy_launch(
            occupied_report
        )
        expect(outcome == "refused", "launch with pre-existing report did not refuse", failures)
        expect(
            not key_reads and not constructions and not invoker_calls,
            "pre-existing report did not prevent credential read / provider "
            "construction / invoker calls",
            failures,
        )
        expect(
            occupied_report.read_text(encoding="utf-8") == "occupied",
            "refused launch clobbered the occupied report",
            failures,
        )

        # Pre-existing sidecar only: same zero-activity refusal.
        occupied_sidecar_dir = Path(tmpdir) / "sidecar-only"
        sidecar_target = occupied_sidecar_dir / "report.json"
        sidecar_target.parent.mkdir(parents=True)
        sidecar_target.with_name(sidecar_target.name + ".sha256").write_text(
            "occupied", encoding="utf-8"
        )
        outcome, _, key_reads, constructions, invoker_calls = spy_launch(
            sidecar_target
        )
        expect(outcome == "refused", "launch with pre-existing sidecar did not refuse", failures)
        expect(
            not key_reads and not constructions and not invoker_calls,
            "pre-existing sidecar did not prevent credential read / provider "
            "construction / invoker calls",
            failures,
        )

        # An earlier gate refusal (reviewed-head mismatch) is equally silent.
        fresh_gate = Path(tmpdir) / "gate" / "report.json"
        outcome, _, key_reads, constructions, invoker_calls = spy_launch(
            fresh_gate, reviewed_head="b" * 40
        )
        expect(outcome == "refused", "launch with mismatched reviewed head did not refuse", failures)
        expect(
            not key_reads and not constructions and not invoker_calls,
            "reviewed-head refusal still reached the provider",
            failures,
        )

        # Fresh paths: the launch runs end to end through the same sequence —
        # one credential read, one provider construction, one invoker call.
        fresh = Path(tmpdir) / "fresh" / "report.json"
        outcome, summary, key_reads, constructions, invoker_calls = spy_launch(fresh)
        expect(outcome == "ran", f"fresh launch refused: {summary}", failures)
        expect(len(key_reads) == 1, "fresh launch read the credential more than once", failures)
        expect(len(constructions) == 1, "fresh launch built the provider edge more than once", failures)
        expect(
            summary is not None
            and summary["invocation_count"] == 1 == len(invoker_calls)
            and summary["structural_status"] == "accepted_for_editorial_review",
            "fresh launch summary wrong",
            failures,
        )
        written = json.loads(fresh.read_text(encoding="utf-8"))
        expect(
            written["evidence"]["raw_model_output"] == raw_good
            and written["invocation"]["count"] == 1,
            "launch-written report lost frozen evidence or provenance",
            failures,
        )
        expect(
            fresh.with_name(fresh.name + ".sha256").exists(),
            "launch did not write the sidecar",
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
        "with reviewed-head match, artifact absence for report and sidecar, overwrite "
        "refusal including exclusive creation under a lost existence race) fail closed "
        "deterministically; the actual launch sequence (run_trial) is driven end to end "
        "with a spy provider — a pre-existing report, a pre-existing sidecar, or an "
        "earlier gate refusal each yield zero credential reads, zero provider "
        "constructions, and zero invoker calls, while a fresh launch runs once and "
        "writes report plus sidecar with frozen evidence; the orchestration path owns the "
        "attempt count and proves it against the invoker's own call record for both the "
        "failing and succeeding paths; the report builder freezes exact rendered input "
        "and raw output bytes and verifies the complete hash chain — raw output, rendered "
        "input, the embedded context block, the context object, the registry digest, and "
        "the delivery block — detecting every tampered digest and post-invocation "
        "context mutation; serialization is deterministic and artifacts are immutable."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
