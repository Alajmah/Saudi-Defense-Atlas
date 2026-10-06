#!/usr/bin/env python3
"""Deterministically validate the bounded M4 live drafting campaign controller.

No network calls are made. The validator drives the actual campaign controller
with fake provider factories and verifies: manifest/hash binding, fixed route +
reviewed head, one invocation per case/no retry, structural-rejection
continuation, execution-failure stop, crash recovery without duplicate
invocation, hash-chained ledger tamper detection, immutable per-case evidence,
aggregate qualification limits, and no canonical/publication authority.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_m4_drafting_campaign import (  # noqa: E402
    CAMPAIGN_CONTROLLER_VERSION,
    CAMPAIGN_MANIFEST_VERSION,
    CAMPAIGN_SUMMARY_VERSION,
    CampaignGateError,
    acquire_lock,
    append_event,
    load_ledger,
    load_manifest,
    release_lock,
    run_campaign,
    verify_case_report,
)
from scripts.run_m4_drafting_trial import (  # noqa: E402
    DEFAULT_FIXTURE,
    DEFAULT_TERMINOLOGY,
    DRAFTING_ADAPTER_VERSION,
    DRAFT_PROMPT_TEMPLATE_VERSION,
    REPORT_VERSION,
    run_trial,
)
from scripts.run_m4_model_extraction_trial import _file_sha256  # noqa: E402

REVIEWED_HEAD = "a" * 40
ENTITLEMENT_ID = "M4-DRAFT-CAMPAIGN-TEST-AUTH"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_gate(label: str, fn, failures: list[str]) -> None:
    try:
        fn()
    except CampaignGateError:
        return
    failures.append(f"{label} did not fail closed")


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


def repo_rel(path: Path) -> str:
    return path.resolve().relative_to(ROOT.resolve()).as_posix()


def write_manifest(
    path: Path,
    *,
    case_count: int = 2,
    max_invocations: int | None = None,
) -> dict[str, Any]:
    if max_invocations is None:
        max_invocations = case_count
    fixture_rel = repo_rel(DEFAULT_FIXTURE)
    payload = {
        "version": CAMPAIGN_MANIFEST_VERSION,
        "campaign_id": "M4-DRAFT-CAMPAIGN-TEST",
        "reviewed_head": REVIEWED_HEAD,
        "route": "coding-plan",
        "entitlement_id": ENTITLEMENT_ID,
        "model": "glm-5.3",
        "timeout_seconds": 30,
        "max_invocations": max_invocations,
        "driver_report_version": REPORT_VERSION,
        "drafting_adapter_version": DRAFTING_ADAPTER_VERSION,
        "prompt_template_version": DRAFT_PROMPT_TEMPLATE_VERSION,
        "terminology_file": repo_rel(DEFAULT_TERMINOLOGY),
        "terminology_file_sha256": _file_sha256(DEFAULT_TERMINOLOGY),
        "cases": [
            {
                "case_id": f"CASE-{i + 1:02d}",
                "fixture": fixture_rel,
                "fixture_sha256": _file_sha256(DEFAULT_FIXTURE),
            }
            for i in range(case_count)
        ],
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return payload


def fixed_git_state():
    return REVIEWED_HEAD, "refs/heads/test", True


def empty_env() -> str:
    return ""


def fixed_clock() -> str:
    return "2026-10-06T00:00:00Z"


def main() -> int:
    failures: list[str] = []
    raw_good = json.dumps(good_output(), ensure_ascii=False)

    # Manifest binding and fail-closed corpus ceiling.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        write_manifest(manifest_path)
        manifest, digest = load_manifest(manifest_path)
        expect(len(digest) == 64, "manifest digest is not SHA-256", failures)
        expect(
            manifest["max_invocations"] == len(manifest["cases"]),
            "manifest call ceiling drifted",
            failures,
        )

        bad_path = td / "bad.json"
        write_manifest(bad_path, case_count=2, max_invocations=1)
        expect_gate(
            "call ceiling below frozen corpus",
            lambda: load_manifest(bad_path),
            failures,
        )

        tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
        tampered["cases"][0]["fixture_sha256"] = "0" * 64
        tampered_path = td / "tampered.json"
        tampered_path.write_text(json.dumps(tampered), encoding="utf-8")
        expect_gate(
            "fixture hash mismatch",
            lambda: load_manifest(tampered_path),
            failures,
        )

        # Corpus bytes must be tracked by git, not merely present under ROOT.
        untracked = ROOT / ".m4-drafting-campaign-untracked-fixture.json"
        untracked.write_text(DEFAULT_FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
        try:
            untracked_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            untracked_manifest["cases"][0]["fixture"] = untracked.name
            untracked_manifest["cases"][0]["fixture_sha256"] = _file_sha256(untracked)
            untracked_path = td / "untracked.json"
            untracked_path.write_text(json.dumps(untracked_manifest), encoding="utf-8")
            expect_gate(
                "untracked campaign fixture",
                lambda: load_manifest(untracked_path),
                failures,
            )
        finally:
            untracked.unlink(missing_ok=True)

        # Lock liveness is injectable: a live PID refuses, a demonstrably dead
        # same-host PID is safely reclaimable without platform-specific kill probes.
        lock_path = td / "lock-test" / ".campaign.lock"
        lock = acquire_lock(lock_path, digest, pid_alive=lambda pid: False)
        release_lock(lock)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps(
                {
                    "campaign_controller_version": CAMPAIGN_CONTROLLER_VERSION,
                    "manifest_sha256": digest,
                    "hostname": __import__("socket").gethostname(),
                    "pid": 999999,
                    "token": "stale",
                }
            ),
            encoding="utf-8",
        )
        reclaimed = acquire_lock(lock_path, digest, pid_alive=lambda pid: False)
        release_lock(reclaimed)
        lock_path.write_text(
            json.dumps(
                {
                    "campaign_controller_version": CAMPAIGN_CONTROLLER_VERSION,
                    "manifest_sha256": digest,
                    "hostname": __import__("socket").gethostname(),
                    "pid": 1,
                    "token": "live",
                }
            ),
            encoding="utf-8",
        )
        expect_gate(
            "live campaign lock",
            lambda: acquire_lock(lock_path, digest, pid_alive=lambda pid: True),
            failures,
        )

    # Complete campaign: first output is structurally rejected, second accepted;
    # rejection is evidence and does not stop the campaign.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        manifest = write_manifest(manifest_path)
        evidence_dir = td / "evidence"
        calls: list[str] = []
        key_reads: list[int] = []

        def require_key() -> str:
            key_reads.append(1)
            return "test-key"

        responses = ["{}", raw_good]

        def factory(**kwargs):
            def invoke(prompt: str) -> str:
                calls.append(prompt)
                return responses[len(calls) - 1]

            return invoke

        summary = run_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
            require_api_key=require_key,
            invoke_factory=factory,
            git_state_provider=fixed_git_state,
            env_url_provider=empty_env,
            clock=fixed_clock,
        )
        expect(
            summary["summary_version"] == CAMPAIGN_SUMMARY_VERSION,
            "summary version drifted",
            failures,
        )
        expect(
            summary["campaign_controller_version"]
            == CAMPAIGN_CONTROLLER_VERSION,
            "controller version drifted",
            failures,
        )
        expect(summary["status"] == "completed", "campaign did not complete", failures)
        expect(
            summary["counts"]["invocations"] == 2 == len(calls),
            "campaign did not invoke exactly once per case",
            failures,
        )
        expect(
            len(key_reads) == 2,
            "campaign credential reads did not match invoked cases",
            failures,
        )
        expect(
            summary["counts"]["structural_rejected"] == 1,
            "structural rejection was not retained",
            failures,
        )
        expect(
            summary["counts"]["structural_accepted"] == 1,
            "accepted case count wrong",
            failures,
        )
        expect(
            summary["counts"]["execution_failures"] == 0,
            "complete campaign has execution failure",
            failures,
        )
        expect(
            summary["qualification"]["editorial_quality_qualified"] is False,
            "campaign mechanically qualified editorial quality",
            failures,
        )
        expect(
            summary["qualification"]["publication_authority"] is False,
            "campaign has publication authority",
            failures,
        )
        expect(
            summary["qualification"]["canonical_mutation_authority"] is False,
            "campaign has canonical authority",
            failures,
        )
        expect(
            (evidence_dir / "campaign-summary.json").exists(),
            "campaign summary was not frozen",
            failures,
        )
        expect(
            (evidence_dir / "campaign-summary.json.sha256").exists(),
            "campaign summary sidecar missing",
            failures,
        )
        expect(
            (evidence_dir / "campaign-manifest.json").exists()
            and (evidence_dir / "campaign-manifest.json.sha256").exists(),
            "frozen campaign manifest artifact/sidecar missing",
            failures,
        )
        ledger = load_ledger(
            evidence_dir / "campaign-ledger.jsonl",
            manifest["campaign_id"],
            summary["manifest_sha256"],
        )
        expect(
            ledger[-1]["event_type"] == "campaign_completed",
            "ledger lacks completed terminal event",
            failures,
        )

        # Re-running a terminal campaign performs no additional invocation.
        second = run_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
            require_api_key=require_key,
            invoke_factory=factory,
            git_state_provider=fixed_git_state,
            env_url_provider=empty_env,
            clock=fixed_clock,
        )
        expect(
            second["status"] == "completed" and len(calls) == 2,
            "terminal campaign re-invoked a case",
            failures,
        )

        # DCC-01: a terminal rerun must re-close the ledger over every
        # referenced immutable per-case report before trusting the summary.
        case_report = evidence_dir / "CASE-01.json"
        case_sidecar = evidence_dir / "CASE-01.json.sha256"
        original_case_report = case_report.read_bytes()
        original_case_sidecar = case_sidecar.read_bytes()

        case_report.unlink()
        expect_gate(
            "terminal missing case report",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "missing terminal case report reached provider", failures)
        case_report.write_bytes(original_case_report)

        case_sidecar.unlink()
        expect_gate(
            "terminal missing case sidecar",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "missing terminal case sidecar reached provider", failures)
        case_sidecar.write_bytes(original_case_sidecar)

        case_report.write_bytes(original_case_report + b" ")
        expect_gate(
            "terminal case byte tamper",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "terminal case byte tamper reached provider", failures)
        case_report.write_bytes(original_case_report)

        semantic = json.loads(original_case_report.decode("utf-8"))
        semantic["qualification"]["publication_authority"] = True
        semantic_bytes = (
            json.dumps(semantic, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        ).encode("utf-8")
        case_report.write_bytes(semantic_bytes)
        semantic_sha = hashlib.sha256(semantic_bytes).hexdigest()
        case_sidecar.write_text(
            f"{semantic_sha}  {case_report.name}\n",
            encoding="utf-8",
        )
        expect_gate(
            "terminal rehashed semantic case tamper",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "semantic terminal case tamper reached provider", failures)
        case_report.write_bytes(original_case_report)
        case_sidecar.write_bytes(original_case_sidecar)

        # Resume must keep the exact campaign-start entitlement attestation.
        expect_gate(
            "resume entitlement drift",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan CHANGED attestation",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "entitlement drift reached the provider", failures)

        # Terminal summary bytes/sidecar are re-verified and compared with the
        # deterministic ledger projection before being trusted.
        summary_path = evidence_dir / "campaign-summary.json"
        summary_sidecar = evidence_dir / "campaign-summary.json.sha256"
        original_summary = summary_path.read_bytes()
        original_sidecar = summary_sidecar.read_bytes()
        tampered_summary = json.loads(original_summary.decode("utf-8"))
        tampered_summary["status"] = "tampered"
        summary_path.write_text(json.dumps(tampered_summary), encoding="utf-8")
        expect_gate(
            "terminal summary tamper",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "summary tamper reached the provider", failures)
        summary_path.write_bytes(original_summary)
        summary_sidecar.write_bytes(original_sidecar)

        # Ledger tampering is detected before any new provider work.
        ledger_path = evidence_dir / "campaign-ledger.jsonl"
        ledger_text = ledger_path.read_text(encoding="utf-8")
        ledger_path.write_text(
            ledger_text.replace(
                "campaign_completed",
                "campaign_tampered",
                1,
            ),
            encoding="utf-8",
        )
        expect_gate(
            "ledger tamper",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(
            len(calls) == 2,
            "ledger tamper reached the provider",
            failures,
        )

    # An invocation-start ledger marker without terminal case evidence is
    # ambiguous after a process death and must never be retried automatically.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        manifest = write_manifest(manifest_path)
        loaded, manifest_sha = load_manifest(manifest_path)
        evidence_dir = td / "evidence"
        evidence_dir.mkdir()
        attestation = f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test"
        append_event(
            evidence_dir / "campaign-ledger.jsonl",
            campaign_id=loaded["campaign_id"],
            manifest_sha256=manifest_sha,
            event_type="campaign_started",
            payload={
                "reviewed_head": loaded["reviewed_head"],
                "route": loaded["route"],
                "entitlement_id": loaded["entitlement_id"],
                "entitlement_attestation_sha256": hashlib.sha256(
                    attestation.encode("utf-8")
                ).hexdigest(),
                "model": loaded["model"],
                "max_invocations": loaded["max_invocations"],
                "case_count": len(loaded["cases"]),
            },
            clock=fixed_clock,
        )
        append_event(
            evidence_dir / "campaign-ledger.jsonl",
            campaign_id=loaded["campaign_id"],
            manifest_sha256=manifest_sha,
            event_type="case_invocation_started",
            payload={
                "case_id": loaded["cases"][0]["case_id"],
                "fixture": loaded["cases"][0]["fixture"],
                "fixture_sha256": loaded["cases"][0]["fixture_sha256"],
                "conservative_call_budget_charge": 1,
            },
            clock=fixed_clock,
        )
        ambiguous_calls: list[str] = []

        def ambiguous_factory(**kwargs):
            def invoke(prompt: str) -> str:
                ambiguous_calls.append(prompt)
                return raw_good
            return invoke

        expect_gate(
            "ambiguous prior invocation without terminal evidence",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation,
                require_api_key=lambda: "test-key",
                invoke_factory=ambiguous_factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(
            not ambiguous_calls,
            "ambiguous prior invocation was automatically retried",
            failures,
        )

    # DCC-02: campaign invocation-start provenance is emitted only at
    # the single-case driver's immediate pre-provider boundary. Deterministic
    # failures before that point must leave no ambiguous start marker.
    def assert_preinvoke_failure(
        label: str,
        *,
        env_provider,
        key_provider,
        provider_factory,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            manifest_path = td / "manifest.json"
            manifest = write_manifest(manifest_path)
            loaded, manifest_sha = load_manifest(manifest_path)
            evidence_dir = td / "evidence"
            provider_calls: list[str] = []
            try:
                run_campaign(
                    manifest_path=manifest_path,
                    evidence_dir=evidence_dir,
                    entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
                    require_api_key=key_provider,
                    invoke_factory=provider_factory(provider_calls),
                    git_state_provider=fixed_git_state,
                    env_url_provider=env_provider,
                    clock=fixed_clock,
                )
                failures.append(f"{label} did not fail before invocation")
            except (CampaignGateError, SystemExit, RuntimeError):
                pass
            events = load_ledger(
                evidence_dir / "campaign-ledger.jsonl",
                loaded["campaign_id"],
                manifest_sha,
            )
            expect(
                not any(
                    event["event_type"] == "case_invocation_started"
                    for event in events
                ),
                f"{label} wrote an invocation-start marker before provider boundary",
                failures,
            )
            expect(
                not provider_calls,
                f"{label} reached the provider invoker",
                failures,
            )

    def spy_factory(call_log):
        def factory(**kwargs):
            def invoke(prompt: str) -> str:
                call_log.append(prompt)
                return raw_good
            return invoke
        return factory

    assert_preinvoke_failure(
        "route-env ambiguity",
        env_provider=lambda: "https://api.z.ai/api/coding/paas/v4",
        key_provider=lambda: "test-key",
        provider_factory=spy_factory,
    )

    def missing_key():
        raise SystemExit("synthetic missing credential")

    assert_preinvoke_failure(
        "missing credential",
        env_provider=empty_env,
        key_provider=missing_key,
        provider_factory=spy_factory,
    )

    def failing_factory_builder(call_log):
        def factory(**kwargs):
            raise RuntimeError("synthetic provider construction failure")
        return factory

    assert_preinvoke_failure(
        "provider factory failure",
        env_provider=empty_env,
        key_provider=lambda: "test-key",
        provider_factory=failing_factory_builder,
    )

    # Provider/transport failure is terminal: one call, frozen failure evidence,
    # second case is never invoked.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        write_manifest(manifest_path)
        evidence_dir = td / "evidence"
        calls: list[str] = []

        def fail_factory(**kwargs):
            def invoke(prompt: str) -> str:
                calls.append(prompt)
                raise RuntimeError("synthetic provider failure")

            return invoke

        stopped = run_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test",
            require_api_key=lambda: "test-key",
            invoke_factory=fail_factory,
            git_state_provider=fixed_git_state,
            env_url_provider=empty_env,
            clock=fixed_clock,
        )
        expect(
            stopped["status"] == "stopped_execution_failure",
            "provider failure did not stop campaign",
            failures,
        )
        expect(
            len(calls) == 1,
            "provider failure retried or continued to next case",
            failures,
        )
        expect(
            stopped["counts"]["execution_failures"] == 1,
            "failure count missing",
            failures,
        )
        expect(
            stopped["counts"]["recorded_cases"] == 1,
            "campaign continued after execution failure",
            failures,
        )

    # Recovery authorization binding and campaign-start provenance.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        manifest = write_manifest(manifest_path)
        loaded, manifest_sha = load_manifest(manifest_path)
        evidence_dir = td / "evidence"
        evidence_dir.mkdir()
        case1 = manifest["cases"][0]
        attestation = f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test"
        pre_calls: list[str] = []

        def pre_factory(**kwargs):
            def invoke(prompt: str) -> str:
                pre_calls.append(prompt)
                return raw_good
            return invoke

        # A valid campaign crash-recovery window necessarily has both the
        # leading campaign-start event and the per-case invocation-start marker.
        append_event(
            evidence_dir / "campaign-ledger.jsonl",
            campaign_id=loaded["campaign_id"],
            manifest_sha256=manifest_sha,
            event_type="campaign_started",
            payload={
                "reviewed_head": loaded["reviewed_head"],
                "route": loaded["route"],
                "entitlement_id": loaded["entitlement_id"],
                "entitlement_attestation_sha256": hashlib.sha256(
                    attestation.encode("utf-8")
                ).hexdigest(),
                "model": loaded["model"],
                "max_invocations": loaded["max_invocations"],
                "case_count": len(loaded["cases"]),
            },
            clock=fixed_clock,
        )
        append_event(
            evidence_dir / "campaign-ledger.jsonl",
            campaign_id=loaded["campaign_id"],
            manifest_sha256=manifest_sha,
            event_type="case_invocation_started",
            payload={
                "case_id": case1["case_id"],
                "fixture": case1["fixture"],
                "fixture_sha256": case1["fixture_sha256"],
                "conservative_call_budget_charge": 1,
            },
            clock=fixed_clock,
        )

        run_trial(
            args=argparse.Namespace(
                fixture=ROOT / case1["fixture"],
                model=manifest["model"],
                zai_endpoint=manifest["route"],
                base_url=None,
                reviewed_head=REVIEWED_HEAD,
                entitlement_attestation=attestation,
                timeout_seconds=30,
                output=evidence_dir / "CASE-01.json",
            ),
            env_url="",
            git_head=REVIEWED_HEAD,
            git_ref="refs/heads/test",
            worktree_clean=True,
            require_api_key=lambda: "test-key",
            invoke_factory=pre_factory,
            created_at_fn=fixed_clock,
        )
        expect(
            len(pre_calls) == 1,
            "pre-crash case report was not generated once",
            failures,
        )

        # DCC-05: recovery verification binds exact attestation and route.
        report_path = evidence_dir / "CASE-01.json"
        try:
            verify_case_report(
                report_path, case1, manifest, attestation
            )
        except CampaignGateError:
            failures.append("valid campaign-bound case report was rejected")

        # DCC-07: even a tampered report with a freshly recomputed sidecar must
        # fail deterministic recovery replay.
        tampered_report = json.loads(report_path.read_text(encoding="utf-8"))
        tampered_report["structural_result"]["validation"]["status"] = "rejected"
        tampered_path = evidence_dir / "TAMPERED-CASE-01.json"
        tampered_bytes = (
            json.dumps(tampered_report, ensure_ascii=False, indent=2, allow_nan=False)
            + "\n"
        ).encode("utf-8")
        tampered_path.write_bytes(tampered_bytes)
        tampered_sha = hashlib.sha256(tampered_bytes).hexdigest()
        tampered_path.with_name(tampered_path.name + ".sha256").write_text(
            f"{tampered_sha}  {tampered_path.name}\n",
            encoding="utf-8",
        )
        expect_gate(
            "rehashed structural-result tamper",
            lambda: verify_case_report(
                tampered_path, case1, manifest, attestation
            ),
            failures,
        )
        expect_gate(
            "recovery wrong attestation",
            lambda: verify_case_report(
                report_path,
                case1,
                manifest,
                f"{ENTITLEMENT_ID} coding-plan DIFFERENT approval",
            ),
            failures,
        )
        prepaid_manifest = dict(manifest)
        prepaid_manifest["route"] = "prepaid"
        expect_gate(
            "recovery wrong route",
            lambda: verify_case_report(
                report_path, case1, prepaid_manifest, attestation
            ),
            failures,
        )

        resume_calls: list[str] = []

        def resume_factory(**kwargs):
            def invoke(prompt: str) -> str:
                resume_calls.append(prompt)
                return raw_good
            return invoke

        resumed = run_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=attestation,
            require_api_key=lambda: "test-key",
            invoke_factory=resume_factory,
            git_state_provider=fixed_git_state,
            env_url_provider=empty_env,
            clock=fixed_clock,
        )
        expect(
            resumed["status"] == "completed",
            "crash recovery did not finish campaign",
            failures,
        )
        expect(
            len(resume_calls) == 1,
            "crash recovery re-invoked the already-frozen case",
            failures,
        )
        case_rows = {row["case_id"]: row for row in resumed["cases"]}
        expect(
            case_rows["CASE-01"]["recovered_without_invocation"] is True,
            "recovered case not marked",
            failures,
        )
        expect(
            case_rows["CASE-02"]["recovered_without_invocation"] is False,
            "fresh case marked recovered",
            failures,
        )

    # DCC-06: a complete standalone report without a campaign invocation-start
    # marker is foreign evidence and must not be absorbed into the campaign.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        manifest = write_manifest(manifest_path)
        evidence_dir = td / "evidence"
        evidence_dir.mkdir()
        attestation = f"{ENTITLEMENT_ID} coding-plan bounded drafting campaign test"
        standalone_calls: list[str] = []

        def standalone_factory(**kwargs):
            def invoke(prompt: str) -> str:
                standalone_calls.append(prompt)
                return raw_good
            return invoke

        run_trial(
            args=argparse.Namespace(
                fixture=ROOT / manifest["cases"][0]["fixture"],
                model=manifest["model"],
                zai_endpoint=manifest["route"],
                base_url=None,
                reviewed_head=REVIEWED_HEAD,
                entitlement_attestation=attestation,
                timeout_seconds=30,
                output=evidence_dir / "CASE-01.json",
            ),
            env_url="",
            git_head=REVIEWED_HEAD,
            git_ref="refs/heads/test",
            worktree_clean=True,
            require_api_key=lambda: "test-key",
            invoke_factory=standalone_factory,
            created_at_fn=fixed_clock,
        )
        expect(len(standalone_calls) == 1, "standalone fixture setup failed", failures)
        campaign_calls: list[str] = []

        def campaign_factory(**kwargs):
            def invoke(prompt: str) -> str:
                campaign_calls.append(prompt)
                return raw_good
            return invoke

        expect_gate(
            "foreign report without campaign invocation-start marker",
            lambda: run_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation,
                require_api_key=lambda: "test-key",
                invoke_factory=campaign_factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(
            not campaign_calls,
            "foreign standalone report caused campaign provider activity",
            failures,
        )

    if failures:
        print("M4 drafting campaign validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated the bounded M4 drafting campaign controller without network calls: "
        "manifest/corpus hashes and reviewed versions are frozen; structural rejection "
        "continues while provider/execution failure stops; each fresh case invokes at most "
        "once with no retry; completed-but-unledgered immutable evidence is recovered "
        "without duplicate invocation and only when a matching campaign invocation-start "
        "marker exists; recovered reports are bound to the exact campaign attestation "
        "and route; the append-only ledger is hash-chained and tamper detecting; "
        "terminal reruns do not invoke again; campaign summaries remain "
        "structural-evidence-only with editorial/publication/canonical authority false."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
