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

from scripts.run_m4_drafting_campaign import (  # noqa: E402
    CAMPAIGN_CONTROLLER_VERSION,
    CAMPAIGN_MANIFEST_VERSION,
    CAMPAIGN_SUMMARY_VERSION,
    CampaignGateError,
    acquire_lock,
    append_event,
    campaign_lock_path,
    load_ledger,
    load_manifest,
    release_lock,
    run_campaign,
    verify_case_report,
    verify_provider_boundary_source,
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


def attestation_for(manifest_path: Path) -> str:
    manifest, manifest_sha = load_manifest(manifest_path)
    return (
        f"{manifest['entitlement_id']} {manifest['campaign_id']} "
        f"{manifest_sha} {manifest['route']} bounded drafting campaign test"
    )


def run_test_campaign(**kwargs):
    manifest_path = Path(kwargs["manifest_path"])
    kwargs.setdefault(
        "runtime_root", manifest_path.parent / ".campaign-runtime"
    )
    return run_campaign(**kwargs)


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

        # DCC-PATH-01: case IDs may not alias controller artifact stems,
        # including case-insensitive aliases on Windows/default macOS filesystems.
        for reserved_case_id in (
            "campaign-manifest",
            "campaign-summary",
            "campaign-ledger",
            "Campaign-Manifest",
            "Campaign-Summary",
            "Campaign-Ledger",
        ):
            reserved = json.loads(manifest_path.read_text(encoding="utf-8"))
            reserved["cases"][0]["case_id"] = reserved_case_id
            reserved_path = td / f"reserved-{reserved_case_id}.json"
            reserved_path.write_text(
                json.dumps(reserved, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            expect_gate(
                f"reserved campaign case_id {reserved_case_id}",
                lambda p=reserved_path: load_manifest(p),
                failures,
            )

        for windows_reserved_id in ("CON", "nul", "Com1", "lPt9"):
            windows_reserved = json.loads(
                manifest_path.read_text(encoding="utf-8")
            )
            windows_reserved["cases"][0]["case_id"] = windows_reserved_id
            windows_reserved_path = td / f"windows-reserved-{windows_reserved_id}.json"
            windows_reserved_path.write_text(
                json.dumps(windows_reserved, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            expect_gate(
                f"Windows-reserved campaign case_id {windows_reserved_id}",
                lambda p=windows_reserved_path: load_manifest(p),
                failures,
            )

        casefold_collision = json.loads(manifest_path.read_text(encoding="utf-8"))
        casefold_collision["cases"][0]["case_id"] = "CASE-COLLISION"
        casefold_collision["cases"][1]["case_id"] = "case-collision"
        casefold_collision_path = td / "casefold-collision.json"
        casefold_collision_path.write_text(
            json.dumps(casefold_collision, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        expect_gate(
            "case-insensitive case_id collision",
            lambda: load_manifest(casefold_collision_path),
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

        # DCC-AUTH-01: one approval is bound to the exact canonical
        # manifest, not merely entitlement ID + route.
        original_attestation = attestation_for(manifest_path)

        def assert_manifest_drift_rejected(label: str, drifted: dict[str, Any]) -> None:
            drifted_path = td / f"{label}.json"
            drifted_path.write_text(
                json.dumps(drifted, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            credential_reads: list[int] = []
            provider_calls: list[str] = []

            def drift_key() -> str:
                credential_reads.append(1)
                return "test-key"

            def drift_factory(**kwargs):
                def invoke(prompt: str) -> str:
                    provider_calls.append(prompt)
                    return raw_good
                return invoke

            expect_gate(
                f"manifest-bound entitlement {label}",
                lambda: run_test_campaign(
                    manifest_path=drifted_path,
                    evidence_dir=td / f"evidence-{label}",
                    entitlement_attestation=original_attestation,
                    require_api_key=drift_key,
                    invoke_factory=drift_factory,
                    git_state_provider=fixed_git_state,
                    env_url_provider=empty_env,
                    clock=fixed_clock,
                ),
                failures,
            )
            expect(
                not credential_reads and not provider_calls,
                f"manifest drift {label} reached credentials/provider",
                failures,
            )

        changed_model = copy.deepcopy(manifest)
        changed_model["model"] = "glm-5.3-drift"
        assert_manifest_drift_rejected("changed-model", changed_model)

        reordered = copy.deepcopy(manifest)
        reordered["cases"] = list(reversed(reordered["cases"]))
        assert_manifest_drift_rejected("reordered-corpus", reordered)

        enlarged = copy.deepcopy(manifest)
        extra_case = dict(enlarged["cases"][-1])
        extra_case["case_id"] = "CASE-03"
        enlarged["cases"].append(extra_case)
        enlarged["max_invocations"] = len(enlarged["cases"])
        assert_manifest_drift_rejected("changed-ceiling", enlarged)

        # DCC-13: lock acquisition never auto-reclaims an existing file.
        # This removes stale-lock TOCTOU races; crash residues require explicit
        # operator reconciliation/removal after confirming no controller is live.
        lock_path = td / "lock-test" / ".campaign.lock"
        lock = acquire_lock(lock_path, digest)
        expect_gate(
            "second campaign lock while owned",
            lambda: acquire_lock(lock_path, digest),
            failures,
        )
        release_lock(lock)
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        stale_payload = {
            "campaign_controller_version": CAMPAIGN_CONTROLLER_VERSION,
            "manifest_sha256": digest,
            "hostname": __import__("socket").gethostname(),
            "pid": 999999,
            "token": "stale",
        }
        lock_path.write_text(json.dumps(stale_payload), encoding="utf-8")
        stale_before = lock_path.read_bytes()
        expect_gate(
            "stale-shaped campaign lock",
            lambda: acquire_lock(lock_path, digest),
            failures,
        )
        expect(
            lock_path.read_bytes() == stale_before,
            "stale-shaped lock was automatically modified/reclaimed",
            failures,
        )
        lock_path.unlink()

        # DCC-LOCK-01: lock namespace is keyed by exact manifest and checkout,
        # independent of caller-selected evidence directory.
        global_path = campaign_lock_path(
            digest, runtime_root=td / ".campaign-runtime"
        )
        global_lock = acquire_lock(global_path, digest)
        blocked_key_reads: list[int] = []
        blocked_provider_calls: list[str] = []

        def blocked_key() -> str:
            blocked_key_reads.append(1)
            return "test-key"

        def blocked_factory(**kwargs):
            def invoke(prompt: str) -> str:
                blocked_provider_calls.append(prompt)
                return raw_good
            return invoke

        try:
            expect_gate(
                "same manifest different evidence directory while locked",
                lambda: run_test_campaign(
                    manifest_path=manifest_path,
                    evidence_dir=td / "different-evidence-directory",
                    entitlement_attestation=attestation_for(manifest_path),
                    require_api_key=blocked_key,
                    invoke_factory=blocked_factory,
                    git_state_provider=fixed_git_state,
                    env_url_provider=empty_env,
                    clock=fixed_clock,
                ),
                failures,
            )
            expect(
                not blocked_key_reads and not blocked_provider_calls,
                "manifest-global live lock allowed credentials/provider from another evidence directory",
                failures,
            )
        finally:
            release_lock(global_lock)

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

        summary = run_test_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=attestation_for(manifest_path),
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

        # DCC-SRC-01: the exact prompt about to be sent must still reconstruct
        # from freshly read manifest-bound bytes at the provider boundary.
        try:
            verify_provider_boundary_source(
                prompt=calls[0],
                case=manifest["cases"][0],
                manifest=manifest,
                git_state_provider=fixed_git_state,
            )
        except CampaignGateError:
            failures.append("valid provider-boundary source/prompt was rejected")
        expect_gate(
            "provider-boundary rendered prompt drift",
            lambda: verify_provider_boundary_source(
                prompt=calls[0] + " ",
                case=manifest["cases"][0],
                manifest=manifest,
                git_state_provider=fixed_git_state,
            ),
            failures,
        )
        expect_gate(
            "provider-boundary source-state drift",
            lambda: verify_provider_boundary_source(
                prompt=calls[0],
                case=manifest["cases"][0],
                manifest=manifest,
                git_state_provider=lambda: (
                    REVIEWED_HEAD,
                    "refs/heads/test",
                    False,
                ),
            ),
            failures,
        )

        # Re-running a terminal campaign performs no additional invocation.
        second = run_test_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=attestation_for(manifest_path),
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

        # DCC-LOCK-01 residual: the transient live lock is not enough. The
        # persistent manifest binding must survive normal completion so the
        # same exact approval cannot spend the ceiling again in another
        # evidence directory.
        second_dir_key_reads: list[int] = []
        second_dir_calls: list[str] = []

        def second_dir_key() -> str:
            second_dir_key_reads.append(1)
            return "test-key"

        def second_dir_factory(**kwargs):
            def invoke(prompt: str) -> str:
                second_dir_calls.append(prompt)
                return raw_good
            return invoke

        expect_gate(
            "same completed manifest second evidence directory",
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=td / "evidence-second-after-completion",
                entitlement_attestation=attestation_for(manifest_path),
                require_api_key=second_dir_key,
                invoke_factory=second_dir_factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(
            not second_dir_key_reads and not second_dir_calls,
            "persistent campaign binding allowed the call ceiling to be replayed",
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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path),
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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path),
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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path),
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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path),
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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path) + " CHANGED",
                require_api_key=require_key,
                invoke_factory=factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(len(calls) == 2, "entitlement drift reached the provider", failures)

        # DCC-ATT-01: exact attestation bytes are frozen; whitespace drift is
        # not normalized away on resume.
        expect_gate(
            "resume entitlement whitespace drift",
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=" " + attestation_for(manifest_path),
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
            "attestation whitespace drift reached the provider",
            failures,
        )

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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path),
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
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation_for(manifest_path),
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
        attestation = attestation_for(manifest_path)
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
            lambda: run_test_campaign(
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
        git_provider=fixed_git_state,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            manifest_path = td / "manifest.json"
            manifest = write_manifest(manifest_path)
            loaded, manifest_sha = load_manifest(manifest_path)
            evidence_dir = td / "evidence"
            provider_calls: list[str] = []
            try:
                run_test_campaign(
                    manifest_path=manifest_path,
                    evidence_dir=evidence_dir,
                    entitlement_attestation=attestation_for(manifest_path),
                    require_api_key=key_provider,
                    invoke_factory=provider_factory(provider_calls),
                    git_state_provider=git_provider,
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

    # Fresh/nonterminal campaign preflight must also reject aggregate-summary
    # residue before spending entitlement on any case.
    for mode in ("summary-only", "sidecar-only", "complete-foreign-summary"):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            manifest_path = td / "manifest.json"
            write_manifest(manifest_path)
            evidence_dir = td / "evidence"
            evidence_dir.mkdir()
            summary_path = evidence_dir / "campaign-summary.json"
            sidecar = summary_path.with_name(summary_path.name + ".sha256")

            if mode in {"summary-only", "complete-foreign-summary"}:
                summary_path.write_text("{}\n", encoding="utf-8")
            if mode == "sidecar-only":
                sidecar.write_text(
                    f"{'0' * 64}  {summary_path.name}\n",
                    encoding="utf-8",
                )
            if mode == "complete-foreign-summary":
                summary_bytes = summary_path.read_bytes()
                summary_sha = hashlib.sha256(summary_bytes).hexdigest()
                sidecar.write_text(
                    f"{summary_sha}  {summary_path.name}\n",
                    encoding="utf-8",
                )

            summary_calls: list[str] = []
            summary_credentials: list[int] = []

            def summary_key() -> str:
                summary_credentials.append(1)
                return "test-key"

            def summary_factory(**kwargs):
                def invoke(prompt: str) -> str:
                    summary_calls.append(prompt)
                    return raw_good
                return invoke

            expect_gate(
                f"nonterminal summary artifact preflight {mode}",
                lambda: run_test_campaign(
                    manifest_path=manifest_path,
                    evidence_dir=evidence_dir,
                    entitlement_attestation=attestation_for(manifest_path),
                    require_api_key=summary_key,
                    invoke_factory=summary_factory,
                    git_state_provider=fixed_git_state,
                    env_url_provider=empty_env,
                    clock=fixed_clock,
                ),
                failures,
            )
            expect(
                not summary_credentials,
                f"nonterminal summary artifact preflight {mode} read credentials",
                failures,
            )
            expect(
                not summary_calls,
                f"nonterminal summary artifact preflight {mode} invoked provider",
                failures,
            )

    # Fresh/nonterminal campaign preflight must inspect every manifest case
    # before spending entitlement on an earlier missing case.
    for mode in ("incomplete", "foreign-complete"):
        with tempfile.TemporaryDirectory() as tmpdir:
            td = Path(tmpdir)
            manifest_path = td / "manifest.json"
            write_manifest(manifest_path)
            evidence_dir = td / "evidence"
            evidence_dir.mkdir()
            later_report = evidence_dir / "CASE-02.json"
            later_report.write_text("{}\n", encoding="utf-8")
            if mode == "foreign-complete":
                later_bytes = later_report.read_bytes()
                later_sha = hashlib.sha256(later_bytes).hexdigest()
                later_report.with_name(
                    later_report.name + ".sha256"
                ).write_text(
                    f"{later_sha}  {later_report.name}\n",
                    encoding="utf-8",
                )

            preflight_calls: list[str] = []
            credential_reads: list[int] = []

            def preflight_key() -> str:
                credential_reads.append(1)
                return "test-key"

            def preflight_factory(**kwargs):
                def invoke(prompt: str) -> str:
                    preflight_calls.append(prompt)
                    return raw_good
                return invoke

            expect_gate(
                f"later-case artifact preflight {mode}",
                lambda: run_test_campaign(
                    manifest_path=manifest_path,
                    evidence_dir=evidence_dir,
                    entitlement_attestation=attestation_for(manifest_path),
                    require_api_key=preflight_key,
                    invoke_factory=preflight_factory,
                    git_state_provider=fixed_git_state,
                    env_url_provider=empty_env,
                    clock=fixed_clock,
                ),
                failures,
            )
            expect(
                not credential_reads,
                f"later-case artifact preflight {mode} read credentials",
                failures,
            )
            expect(
                not preflight_calls,
                f"later-case artifact preflight {mode} invoked provider",
                failures,
            )

    source_state_checks: list[int] = []

    def drift_between_outer_check_and_provider():
        source_state_checks.append(1)
        if len(source_state_checks) == 1:
            return REVIEWED_HEAD, "refs/heads/test", True
        return REVIEWED_HEAD, "refs/heads/test", False

    assert_preinvoke_failure(
        "provider-boundary source-state drift",
        env_provider=empty_env,
        key_provider=lambda: "test-key",
        provider_factory=spy_factory,
        git_provider=drift_between_outer_check_and_provider,
    )
    expect(
        len(source_state_checks) == 2,
        "provider-boundary source-state regression did not exercise both checks",
        failures,
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

        stopped = run_test_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=attestation_for(manifest_path),
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

        # DCC-11: simulate a crash after case_execution_failure was durably
        # appended but before campaign_stopped. Resume must finalize the stop
        # without invoking the next case.
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        ledger_path = evidence_dir / "campaign-ledger.jsonl"
        ledger_events = load_ledger(
            ledger_path,
            manifest["campaign_id"],
            stopped["manifest_sha256"],
        )
        expect(
            ledger_events[-1]["event_type"] == "campaign_stopped",
            "failure setup lacks terminal stop event",
            failures,
        )
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
        ledger_path.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
        (evidence_dir / "campaign-summary.json").unlink()
        (evidence_dir / "campaign-summary.json.sha256").unlink()

        resumed_calls: list[str] = []

        def resumed_factory(**kwargs):
            def invoke(prompt: str) -> str:
                resumed_calls.append(prompt)
                return raw_good
            return invoke

        resumed_failure = run_test_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=attestation_for(manifest_path),
            require_api_key=lambda: "test-key",
            invoke_factory=resumed_factory,
            git_state_provider=fixed_git_state,
            env_url_provider=empty_env,
            clock=fixed_clock,
        )
        expect(
            resumed_failure["status"] == "stopped_execution_failure",
            "recorded execution failure was not terminalized on resume",
            failures,
        )
        expect(
            not resumed_calls,
            "resume after recorded execution failure invoked a later case",
            failures,
        )
        resumed_ledger = load_ledger(
            ledger_path,
            manifest["campaign_id"],
            resumed_failure["manifest_sha256"],
        )
        expect(
            resumed_ledger[-1]["event_type"] == "campaign_stopped",
            "resume did not append campaign_stopped after recorded execution failure",
            failures,
        )

    # DCC-ERR-01: an exception with an empty string message is still a
    # recoverable/terminal execution failure with one attempted provider call.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        write_manifest(manifest_path)
        evidence_dir = td / "evidence"
        timeout_calls: list[str] = []

        def timeout_factory(**kwargs):
            def invoke(prompt: str) -> str:
                timeout_calls.append(prompt)
                raise TimeoutError()
            return invoke

        timeout_summary = run_test_campaign(
            manifest_path=manifest_path,
            evidence_dir=evidence_dir,
            entitlement_attestation=attestation_for(manifest_path),
            require_api_key=lambda: "test-key",
            invoke_factory=timeout_factory,
            git_state_provider=fixed_git_state,
            env_url_provider=empty_env,
            clock=fixed_clock,
        )
        expect(
            timeout_summary["status"] == "stopped_execution_failure",
            "empty-message provider exception did not terminalize the campaign",
            failures,
        )
        expect(
            len(timeout_calls) == 1,
            "empty-message provider exception retried or continued",
            failures,
        )
        timeout_report = json.loads(
            (evidence_dir / "CASE-01.json").read_text(encoding="utf-8")
        )
        expect(
            isinstance(timeout_report.get("execution_error"), str)
            and "TimeoutError" in timeout_report["execution_error"],
            "empty-message provider exception was not normalized to a non-empty diagnostic",
            failures,
        )

    # DCC-12: nonterminal resume must re-verify every recorded case
    # before any fresh provider activity.
    with tempfile.TemporaryDirectory() as tmpdir:
        td = Path(tmpdir)
        manifest_path = td / "manifest.json"
        manifest = write_manifest(manifest_path)
        loaded, manifest_sha = load_manifest(manifest_path)
        evidence_dir = td / "evidence"
        evidence_dir.mkdir()
        attestation = attestation_for(manifest_path)
        case1 = loaded["cases"][0]

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

        case1_calls: list[str] = []

        def case1_factory(**kwargs):
            def invoke(prompt: str) -> str:
                case1_calls.append(prompt)
                return raw_good
            return invoke

        case1_report = evidence_dir / "CASE-01.json"
        run_trial(
            args=argparse.Namespace(
                fixture=ROOT / case1["fixture"],
                model=loaded["model"],
                zai_endpoint=loaded["route"],
                base_url=None,
                reviewed_head=REVIEWED_HEAD,
                entitlement_attestation=attestation,
                timeout_seconds=30,
                output=case1_report,
            ),
            env_url="",
            git_head=REVIEWED_HEAD,
            git_ref="refs/heads/test",
            worktree_clean=True,
            require_api_key=lambda: "test-key",
            invoke_factory=case1_factory,
            created_at_fn=fixed_clock,
        )
        verified_case1 = verify_case_report(
            case1_report, case1, loaded, attestation
        )
        structural = verified_case1["report"]["structural_result"]
        append_event(
            evidence_dir / "campaign-ledger.jsonl",
            campaign_id=loaded["campaign_id"],
            manifest_sha256=manifest_sha,
            event_type="case_completed",
            payload={
                "case_id": case1["case_id"],
                "fixture": case1["fixture"],
                "fixture_sha256": case1["fixture_sha256"],
                "report_path": case1_report.name,
                "report_sha256": verified_case1["report_sha256"],
                "invocation_count": verified_case1["invocation_count"],
                "structural_status": structural["validation"]["status"],
                "execution_error": None,
                "recovered_without_invocation": False,
            },
            clock=fixed_clock,
        )

        # Damage previously recorded evidence before the campaign reaches case 2.
        (evidence_dir / "CASE-01.json.sha256").unlink()
        later_calls: list[str] = []

        def later_factory(**kwargs):
            def invoke(prompt: str) -> str:
                later_calls.append(prompt)
                return raw_good
            return invoke

        expect_gate(
            "nonterminal recorded evidence damage",
            lambda: run_test_campaign(
                manifest_path=manifest_path,
                evidence_dir=evidence_dir,
                entitlement_attestation=attestation,
                require_api_key=lambda: "test-key",
                invoke_factory=later_factory,
                git_state_provider=fixed_git_state,
                env_url_provider=empty_env,
                clock=fixed_clock,
            ),
            failures,
        )
        expect(
            not later_calls,
            "damaged recorded evidence allowed a fresh provider call",
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
        attestation = attestation_for(manifest_path)
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

        # DCC-REC-01: any campaign-bound recoverable report has a matching
        # provider-boundary start marker, so attempted must be true and count exactly 1.
        for field, value, label in (
            ("attempted", False, "false-attempt"),
            ("count", 0, "zero-count"),
        ):
            provenance_tamper = json.loads(report_path.read_text(encoding="utf-8"))
            provenance_tamper["invocation"][field] = value
            provenance_path = evidence_dir / f"PROVENANCE-{label}.json"
            provenance_bytes = (
                json.dumps(
                    provenance_tamper,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            provenance_path.write_bytes(provenance_bytes)
            provenance_sha = hashlib.sha256(provenance_bytes).hexdigest()
            provenance_path.with_name(
                provenance_path.name + ".sha256"
            ).write_text(
                f"{provenance_sha}  {provenance_path.name}\n",
                encoding="utf-8",
            )
            expect_gate(
                f"rehashed invocation provenance tamper {label}",
                lambda p=provenance_path: verify_case_report(
                    p, case1, manifest, attestation
                ),
                failures,
            )

        # Codex checkout-provenance reconciliation: recovery must bind the
        # report's actual execution checkout to the reviewed clean source state.
        for field, value, label in (
            ("git_head", "b" * 40, "wrong-git-head"),
            ("tracked_worktree_clean", False, "dirty-worktree"),
        ):
            checkout_tamper = json.loads(report_path.read_text(encoding="utf-8"))
            checkout_tamper["trial_context"][field] = value
            checkout_path = evidence_dir / f"CHECKOUT-{label}.json"
            checkout_bytes = (
                json.dumps(
                    checkout_tamper,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            checkout_path.write_bytes(checkout_bytes)
            checkout_sha = hashlib.sha256(checkout_bytes).hexdigest()
            checkout_path.with_name(
                checkout_path.name + ".sha256"
            ).write_text(
                f"{checkout_sha}  {checkout_path.name}\n",
                encoding="utf-8",
            )
            expect_gate(
                f"rehashed checkout provenance tamper {label}",
                lambda p=checkout_path: verify_case_report(
                    p, case1, manifest, attestation
                ),
                failures,
            )

        # Recovery must preserve the trial builder's unreviewed editorial
        # placeholder; campaign evidence cannot synthesize a human approval.
        for field, value, label in (
            ("status", "approved", "approved-status"),
            ("mechanical_score", 1, "non-null-score"),
            ("notes", "synthetic approval note", "non-null-notes"),
            ("assessment_dimensions", ["Arabic fluency"], "dimension-drift"),
        ):
            editorial_tamper = json.loads(report_path.read_text(encoding="utf-8"))
            editorial_tamper["editorial_assessment"][field] = value
            editorial_path = evidence_dir / f"EDITORIAL-{label}.json"
            editorial_bytes = (
                json.dumps(
                    editorial_tamper,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            editorial_path.write_bytes(editorial_bytes)
            editorial_sha = hashlib.sha256(editorial_bytes).hexdigest()
            editorial_path.with_name(editorial_path.name + ".sha256").write_text(
                f"{editorial_sha}  {editorial_path.name}\n",
                encoding="utf-8",
            )
            expect_gate(
                f"rehashed editorial-assessment tamper {label}",
                lambda p=editorial_path: verify_case_report(
                    p, case1, manifest, attestation
                ),
                failures,
            )

        # Deterministic single-case report metadata must remain bound to the
        # reviewed driver/campaign; rehashed contradictory provenance is rejected.
        fixed_metadata_tampers = (
            (("provider",), "other-provider", "top-provider"),
            (("provider_checkpoint_version",), "unexpected", "checkpoint"),
            (("provider_edge", "driver"), "other-driver", "edge-driver"),
            (("provider_edge", "resolved_base_url_source"), "flag", "route-source"),
            (("provider_edge", "credential_source"), "other-secret", "credential-source"),
            (("provider_edge", "transport"), "other-transport", "transport"),
            (("provider_edge", "tools"), "enabled", "tools"),
            (
                ("provider_edge", "reasoning_configuration"),
                {"thinking_type": "disabled"},
                "reasoning",
            ),
            (
                ("entitlement", "standing_extraction_entitlement_covers_drafting"),
                True,
                "standing-entitlement",
            ),
            (
                ("drafting_boundary_versions", "extraction_adapter_at_build"),
                "other-extraction-adapter",
                "extraction-adapter",
            ),
            (("terminology", "registry_version"), "other-registry", "registry-version"),
            (("fixture_version",), "other-fixture", "fixture-version"),
            (
                ("qualification", "served_model_checkpoint"),
                "served-checkpoint",
                "served-checkpoint",
            ),
            (("claim_ceiling",), "production-ready claim", "claim-ceiling"),
        )
        for path, value, label in fixed_metadata_tampers:
            metadata_tamper = json.loads(report_path.read_text(encoding="utf-8"))
            target = metadata_tamper
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            metadata_path = evidence_dir / f"METADATA-{label}.json"
            metadata_bytes = (
                json.dumps(
                    metadata_tamper,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            metadata_path.write_bytes(metadata_bytes)
            metadata_sha = hashlib.sha256(metadata_bytes).hexdigest()
            metadata_path.with_name(metadata_path.name + ".sha256").write_text(
                f"{metadata_sha}  {metadata_path.name}\n",
                encoding="utf-8",
            )
            expect_gate(
                f"rehashed fixed report metadata tamper {label}",
                lambda p=metadata_path: verify_case_report(
                    p, case1, manifest, attestation
                ),
                failures,
            )

        # Codex boundary-version reconciliation: recovered evidence must
        # retain the frozen adapter/template provenance from the campaign manifest.
        for field, value, label in (
            ("drafting_adapter", "other-adapter", "wrong-adapter"),
            ("prompt_template_version", "v999", "wrong-template-version"),
            ("prompt_template_id", "other-template", "wrong-template-id"),
            ("prompt_template_sha256", "0" * 64, "wrong-template-sha"),
        ):
            boundary_tamper = json.loads(report_path.read_text(encoding="utf-8"))
            boundary_tamper["drafting_boundary_versions"][field] = value
            boundary_path = evidence_dir / f"BOUNDARY-{label}.json"
            boundary_bytes = (
                json.dumps(
                    boundary_tamper,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            boundary_path.write_bytes(boundary_bytes)
            boundary_sha = hashlib.sha256(boundary_bytes).hexdigest()
            boundary_path.with_name(boundary_path.name + ".sha256").write_text(
                f"{boundary_sha}  {boundary_path.name}\n",
                encoding="utf-8",
            )
            expect_gate(
                f"rehashed drafting boundary provenance tamper {label}",
                lambda p=boundary_path: verify_case_report(
                    p, case1, manifest, attestation
                ),
                failures,
            )

        # Codex model-trace reconciliation: recovery must bind the
        # structural provenance to the exact campaign model and reviewed
        # single-case driver provider/version identity before replay.
        for field, value, label in (
            ("provider", "other-provider", "wrong-provider"),
            ("model", "other-model", "wrong-model"),
            ("model_version", "other-version", "wrong-model-version"),
        ):
            trace_tamper = json.loads(report_path.read_text(encoding="utf-8"))
            trace_tamper["structural_result"]["model_trace"][field] = value
            trace_path = evidence_dir / f"TRACE-{label}.json"
            trace_bytes = (
                json.dumps(
                    trace_tamper,
                    ensure_ascii=False,
                    indent=2,
                    allow_nan=False,
                )
                + "\n"
            ).encode("utf-8")
            trace_path.write_bytes(trace_bytes)
            trace_sha = hashlib.sha256(trace_bytes).hexdigest()
            trace_path.with_name(trace_path.name + ".sha256").write_text(
                f"{trace_sha}  {trace_path.name}\n",
                encoding="utf-8",
            )
            expect_gate(
                f"rehashed structural model-trace tamper {label}",
                lambda p=trace_path: verify_case_report(
                    p, case1, manifest, attestation
                ),
                failures,
            )

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
                attestation + " DIFFERENT",
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

        resumed = run_test_campaign(
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
        attestation = attestation_for(manifest_path)
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
            lambda: run_test_campaign(
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
