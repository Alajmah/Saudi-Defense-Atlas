#!/usr/bin/env python3
"""Run a bounded long-running M4 bilingual-drafting campaign.

This controller composes over the reviewed single-case ``run_trial()`` driver.
It does not add model authority. A campaign is operator-started, manifest-bound,
route-bound, reviewed-head-bound, call-capped, resumable from immutable evidence,
and terminal on infrastructure/evidence/provenance failure. Ordinary structural
model rejection is recorded and the next case may continue.

No scheduler, autonomous recurrence, canonical mutation, publication, or retry
policy is introduced here.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_m4_drafting_trial import (  # noqa: E402
    DEFAULT_TERMINOLOGY,
    DRAFTING_ADAPTER_VERSION,
    DRAFT_PROMPT_TEMPLATE_VERSION,
    REPORT_VERSION as TRIAL_REPORT_VERSION,
    _git_head,
    _git_ref,
    _worktree_clean,
    build_drafting_context_from_fixture,
    load_fixture,
    require_zai_api_key,
    run_trial,
    sidecar_path,
    zai_invoker,
)
from scripts.run_m4_model_extraction_trial import (  # noqa: E402
    ZAI_BASE_URL_ENV,
    ZAI_ENDPOINT_URLS,
    _file_sha256,
)
from services.intelligence.bilingual_drafting import (  # noqa: E402
    DraftModelTrace,
    build_bilingual_draft_run,
    load_terminology,
    prepare_draft_input,
    split_rendered_prompt,
    terminology_digest,
)

CAMPAIGN_MANIFEST_VERSION = "m4-drafting-campaign-v0.1"
CAMPAIGN_LEDGER_VERSION = "m4-drafting-campaign-ledger-v0.1"
CAMPAIGN_SUMMARY_VERSION = "m4-drafting-campaign-summary-v0.1"
CAMPAIGN_CONTROLLER_VERSION = "m4-drafting-campaign-controller-v0.1"


class CampaignGateError(SystemExit):
    """Raised when campaign execution must fail closed before another invocation."""


def _canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _inside_root(path: Path) -> Path:
    resolved = path.resolve()
    root = ROOT.resolve()
    if resolved != root and root not in resolved.parents:
        raise CampaignGateError(f"campaign path escapes repository root: {path}")
    return resolved


def _repo_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        raise CampaignGateError(
            f"campaign manifest path must be repository-relative: {value}"
        )
    return _inside_root(ROOT / path)


def _require_tracked_repo_file(path: Path) -> None:
    try:
        relative = path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise CampaignGateError(f"campaign file is outside repository root: {path}") from exc
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--error-unmatch", "--", relative],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise CampaignGateError(
            f"campaign file is not tracked by the reviewed repository state: {relative}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--evidence-dir", type=Path, required=True)
    parser.add_argument("--entitlement-attestation", required=True)
    return parser.parse_args()


def load_manifest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CampaignGateError(f"campaign manifest is not JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise CampaignGateError("campaign manifest root must be an object")

    required = {
        "version",
        "campaign_id",
        "reviewed_head",
        "route",
        "entitlement_id",
        "model",
        "timeout_seconds",
        "max_invocations",
        "driver_report_version",
        "drafting_adapter_version",
        "prompt_template_version",
        "terminology_file",
        "terminology_file_sha256",
        "cases",
    }
    missing = sorted(required - payload.keys())
    if missing:
        raise CampaignGateError(
            f"campaign manifest missing keys: {', '.join(missing)}"
        )
    unknown = sorted(set(payload) - required)
    if unknown:
        raise CampaignGateError(
            f"campaign manifest has unknown keys: {', '.join(unknown)}"
        )

    if payload["version"] != CAMPAIGN_MANIFEST_VERSION:
        raise CampaignGateError("unsupported campaign manifest version")
    if (
        not isinstance(payload["campaign_id"], str)
        or not payload["campaign_id"].strip()
    ):
        raise CampaignGateError("campaign_id must be non-empty")
    reviewed_head = payload["reviewed_head"]
    if (
        not isinstance(reviewed_head, str)
        or len(reviewed_head) != 40
        or any(c not in "0123456789abcdef" for c in reviewed_head.lower())
    ):
        raise CampaignGateError("reviewed_head must be a 40-character hex commit SHA")
    if payload["route"] not in {"coding-plan", "prepaid"}:
        raise CampaignGateError("route must be coding-plan or prepaid")
    if (
        not isinstance(payload["entitlement_id"], str)
        or not payload["entitlement_id"].strip()
    ):
        raise CampaignGateError("entitlement_id must be non-empty")
    if not isinstance(payload["model"], str) or not payload["model"].strip():
        raise CampaignGateError("model must be non-empty")
    if (
        not isinstance(payload["timeout_seconds"], int)
        or payload["timeout_seconds"] < 1
    ):
        raise CampaignGateError("timeout_seconds must be a positive integer")
    if (
        not isinstance(payload["max_invocations"], int)
        or payload["max_invocations"] < 1
    ):
        raise CampaignGateError("max_invocations must be a positive integer")
    if payload["driver_report_version"] != TRIAL_REPORT_VERSION:
        raise CampaignGateError(
            "manifest driver_report_version does not match reviewed driver"
        )
    if payload["drafting_adapter_version"] != DRAFTING_ADAPTER_VERSION:
        raise CampaignGateError(
            "manifest drafting_adapter_version does not match reviewed adapter"
        )
    if payload["prompt_template_version"] != DRAFT_PROMPT_TEMPLATE_VERSION:
        raise CampaignGateError(
            "manifest prompt_template_version does not match reviewed template"
        )

    terminology_path = _repo_path(payload["terminology_file"])
    if not terminology_path.is_file():
        raise CampaignGateError("campaign terminology file does not exist")
    _require_tracked_repo_file(terminology_path)
    if _file_sha256(terminology_path) != payload["terminology_file_sha256"]:
        raise CampaignGateError("campaign terminology file hash mismatch")
    if terminology_path.resolve() != DEFAULT_TERMINOLOGY.resolve():
        raise CampaignGateError(
            "campaign must use the reviewed default terminology registry"
        )

    cases = payload["cases"]
    if not isinstance(cases, list) or not cases:
        raise CampaignGateError("campaign cases must be a non-empty list")
    if payload["max_invocations"] != len(cases):
        raise CampaignGateError(
            "max_invocations must equal the frozen case count; retries are not allowed"
        )

    seen: set[str] = set()
    for index, case in enumerate(cases):
        if (
            not isinstance(case, dict)
            or set(case) != {"case_id", "fixture", "fixture_sha256"}
        ):
            raise CampaignGateError(
                f"case {index} must contain only case_id/fixture/fixture_sha256"
            )
        case_id = case["case_id"]
        if (
            not isinstance(case_id, str)
            or not case_id
            or any(
                c
                not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
                for c in case_id
            )
        ):
            raise CampaignGateError(f"case {index} has invalid case_id")
        if case_id in {
            "campaign-manifest",
            "campaign-summary",
            "campaign-ledger",
        }:
            raise CampaignGateError(
                f"campaign case_id is reserved for controller artifacts: {case_id}"
            )
        if case_id in seen:
            raise CampaignGateError(f"duplicate campaign case_id: {case_id}")
        seen.add(case_id)
        fixture_path = _repo_path(case["fixture"])
        if not fixture_path.is_file():
            raise CampaignGateError(
                f"campaign fixture does not exist: {case['fixture']}"
            )
        _require_tracked_repo_file(fixture_path)
        if _file_sha256(fixture_path) != case["fixture_sha256"]:
            raise CampaignGateError(f"campaign fixture hash mismatch: {case_id}")

    return payload, _sha256_text(_canonical_json(payload))


def check_campaign_entitlement(
    manifest: dict[str, Any], attestation: str
) -> str:
    value = attestation.strip()
    if not value:
        raise CampaignGateError("campaign entitlement attestation must be non-empty")
    manifest_sha256 = _sha256_text(_canonical_json(manifest))
    folded = value.casefold()
    if manifest["entitlement_id"].casefold() not in folded:
        raise CampaignGateError(
            "campaign entitlement attestation is not bound to the manifest entitlement_id"
        )
    if manifest["campaign_id"].casefold() not in folded:
        raise CampaignGateError(
            "campaign entitlement attestation is not bound to the campaign_id"
        )
    if manifest_sha256.casefold() not in folded:
        raise CampaignGateError(
            "campaign entitlement attestation is not bound to the exact manifest SHA-256"
        )
    route_text = folded
    if manifest["route"] == "coding-plan" and "coding-plan" not in route_text:
        raise CampaignGateError(
            "campaign entitlement attestation does not name the coding-plan route"
        )
    if manifest["route"] == "prepaid" and not (
        "prepaid" in route_text or "general" in route_text
    ):
        raise CampaignGateError(
            "campaign entitlement attestation does not name the prepaid/general route"
        )
    return attestation


def _event_hash(event_without_hash: dict[str, Any]) -> str:
    return _sha256_text(_canonical_json(event_without_hash))


def load_ledger(
    path: Path, campaign_id: str, manifest_sha256: str
) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    previous = None
    for line_no, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), 1
    ):
        if not raw_line.strip():
            raise CampaignGateError(f"campaign ledger has blank line {line_no}")
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise CampaignGateError(
                f"campaign ledger line {line_no} is invalid JSON"
            ) from exc
        if event.get("ledger_version") != CAMPAIGN_LEDGER_VERSION:
            raise CampaignGateError("campaign ledger version mismatch")
        if (
            event.get("campaign_id") != campaign_id
            or event.get("manifest_sha256") != manifest_sha256
        ):
            raise CampaignGateError(
                "campaign ledger is bound to another manifest/campaign"
            )
        if event.get("sequence") != line_no:
            raise CampaignGateError("campaign ledger sequence is not contiguous")
        if event.get("previous_event_sha256") != previous:
            raise CampaignGateError("campaign ledger hash chain is broken")
        supplied = event.get("event_sha256")
        material = dict(event)
        material.pop("event_sha256", None)
        if supplied != _event_hash(material):
            raise CampaignGateError("campaign ledger event hash mismatch")
        previous = supplied
        events.append(event)
    return events


def append_event(
    path: Path,
    *,
    campaign_id: str,
    manifest_sha256: str,
    event_type: str,
    payload: dict[str, Any],
    clock: Callable[[], str],
) -> dict[str, Any]:
    events = load_ledger(path, campaign_id, manifest_sha256)
    event: dict[str, Any] = {
        "ledger_version": CAMPAIGN_LEDGER_VERSION,
        "campaign_id": campaign_id,
        "manifest_sha256": manifest_sha256,
        "sequence": len(events) + 1,
        "previous_event_sha256": (
            events[-1]["event_sha256"] if events else None
        ),
        "recorded_at": clock(),
        "event_type": event_type,
        "payload": payload,
    }
    event["event_sha256"] = _event_hash(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as handle:
        handle.write(_canonical_json(event) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    return event


def _terminal_event(events: list[dict[str, Any]]) -> dict[str, Any] | None:
    for event in reversed(events):
        if event["event_type"] in {"campaign_completed", "campaign_stopped"}:
            return event
    return None


def _case_events(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["event_type"] not in {
            "case_completed",
            "case_execution_failure",
        }:
            continue
        case_id = event["payload"].get("case_id")
        if case_id in result:
            raise CampaignGateError(
                f"campaign ledger has duplicate terminal event for case {case_id}"
            )
        result[case_id] = event
    return result


def _started_cases(events: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for event in events:
        if event["event_type"] != "case_invocation_started":
            continue
        case_id = event["payload"].get("case_id")
        if case_id in result:
            raise CampaignGateError(
                f"campaign ledger has duplicate invocation-start event for case {case_id}"
            )
        result[case_id] = event
    return result


def _read_sidecar(sidecar: Path, report_name: str) -> str:
    text = sidecar.read_text(encoding="utf-8")
    parts = text.rstrip("\n").split("  ", 1)
    if len(parts) != 2 or parts[1] != report_name or len(parts[0]) != 64:
        raise CampaignGateError(f"invalid report sidecar: {sidecar}")
    return parts[0]


def verify_case_report(
    report_path: Path,
    case: dict[str, Any],
    manifest: dict[str, Any],
    expected_attestation: str,
) -> dict[str, Any]:
    sidecar = sidecar_path(report_path)
    if not report_path.exists() or not sidecar.exists():
        raise CampaignGateError(
            f"ambiguous case evidence for {case['case_id']}: "
            "report/sidecar pair incomplete"
        )
    report_bytes = report_path.read_bytes()
    report_sha = _sha256_bytes(report_bytes)
    if _read_sidecar(sidecar, report_path.name) != report_sha:
        raise CampaignGateError(
            f"case report sidecar mismatch: {case['case_id']}"
        )
    try:
        report = json.loads(report_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignGateError(
            f"case report is not valid UTF-8 JSON: {case['case_id']}"
        ) from exc
    if report.get("report_version") != manifest["driver_report_version"]:
        raise CampaignGateError("case report version mismatch")
    if report.get("reviewed_head") != manifest["reviewed_head"]:
        raise CampaignGateError("case report reviewed-head mismatch")
    trial_context = report.get("trial_context", {})
    if trial_context.get("git_head") != manifest["reviewed_head"]:
        raise CampaignGateError(
            "case report execution git_head does not match the reviewed head"
        )
    if trial_context.get("tracked_worktree_clean") is not True:
        raise CampaignGateError(
            "case report execution provenance does not prove a clean tracked worktree"
        )
    if report.get("requested_model") != manifest["model"]:
        raise CampaignGateError("case report model mismatch")
    expected_route_url = ZAI_ENDPOINT_URLS[manifest["route"]]
    if report.get("entitlement", {}).get("attestation") != expected_attestation:
        raise CampaignGateError("case report entitlement attestation mismatch")
    if (
        report.get("provider_edge", {}).get("requested_endpoint_mode")
        != manifest["route"]
    ):
        raise CampaignGateError("case report requested route mismatch")
    if (
        report.get("provider_edge", {}).get("resolved_base_url")
        != expected_route_url
        or report.get("entitlement", {}).get("resolved_base_url")
        != expected_route_url
    ):
        raise CampaignGateError("case report resolved route mismatch")
    if (
        report.get("trial_context", {}).get("fixture_sha256")
        != case["fixture_sha256"]
    ):
        raise CampaignGateError("case report fixture hash mismatch")
    if (
        report.get("terminology", {}).get("terminology_file_sha256")
        != manifest["terminology_file_sha256"]
    ):
        raise CampaignGateError("case report terminology hash mismatch")
    invocation = report.get("invocation", {})
    invocation_count = invocation.get("count")
    if invocation.get("attempted") is not True or invocation_count != 1:
        raise CampaignGateError(
            "campaign case report must prove exactly one attempted provider invocation"
        )

    # Recovery is a separate trust boundary: independently re-verify the exact
    # frozen input/output bytes and, when a structural run exists, replay the
    # deterministic drafting boundary from those bytes.
    evidence = report.get("evidence", {})
    rendered_prompt = evidence.get("rendered_model_input")
    raw_output = evidence.get("raw_model_output")
    if not isinstance(rendered_prompt, str):
        raise CampaignGateError("case report rendered input is not text")
    if raw_output is not None and not isinstance(raw_output, str):
        raise CampaignGateError("case report raw output is neither text nor null")
    rendered_sha = _sha256_text(rendered_prompt)
    raw_sha = _sha256_text(raw_output) if raw_output is not None else None
    if invocation.get("rendered_input_sha256") != rendered_sha:
        raise CampaignGateError("case report rendered-input hash mismatch")
    if invocation.get("raw_model_output_sha256") != raw_sha:
        raise CampaignGateError("case report raw-output hash mismatch")

    try:
        _, context_json, _, delivery_json, _ = split_rendered_prompt(rendered_prompt)
        context = json.loads(context_json)
    except Exception as exc:  # noqa: BLE001
        raise CampaignGateError(
            "case report frozen rendered input cannot be reconstructed"
        ) from exc
    if not isinstance(context, dict):
        raise CampaignGateError("case report frozen context root is not an object")

    terminology_payload = json.loads(
        _repo_path(manifest["terminology_file"]).read_text(encoding="utf-8")
    )
    terminology = load_terminology(terminology_payload)
    registry_sha = terminology_digest(terminology)
    delivery_sha = _sha256_text(delivery_json)
    created_at = context.get("created_at")
    if not isinstance(created_at, str) or not created_at:
        raise CampaignGateError("case report frozen context lacks created_at")
    fixture = load_fixture(_repo_path(case["fixture"]))
    try:
        expected_context = build_drafting_context_from_fixture(
            fixture, terminology, created_at
        )
        expected_rendered, _ = prepare_draft_input(expected_context, terminology)
    except Exception as exc:  # noqa: BLE001
        raise CampaignGateError(
            "case report fixture-to-input deterministic reconstruction failed"
        ) from exc
    if expected_context != context or expected_rendered != rendered_prompt:
        raise CampaignGateError(
            "case report frozen input does not match manifest-bound fixture reconstruction"
        )
    terminology_trace = report.get("terminology", {})
    if terminology_trace.get("registry_acceptance_sha256") != registry_sha:
        raise CampaignGateError("case report terminology registry digest mismatch")
    if terminology_trace.get("delivery_payload_sha256") != delivery_sha:
        raise CampaignGateError("case report terminology delivery digest mismatch")

    qualification = report.get("qualification", {})
    if (
        qualification.get("editorial_quality_qualified") is not False
        or qualification.get("production_model_pipeline_qualified") is not False
        or qualification.get("publication_authority") is not False
        or qualification.get("canonical_mutation_authority") is not False
        or qualification.get("bounded_evidence_only") is not True
    ):
        raise CampaignGateError("case report qualification authority drift")

    structural = report.get("structural_result")
    execution_error = report.get("execution_error")
    if structural is None:
        if not isinstance(execution_error, str) or not execution_error:
            raise CampaignGateError(
                "case report without structural result lacks execution error"
            )
        if qualification.get("structural_mechanical_acceptance") is not False:
            raise CampaignGateError(
                "failed case report claims structural mechanical acceptance"
            )
    else:
        if not isinstance(structural, dict):
            raise CampaignGateError("case report structural result is not an object")
        if execution_error is not None:
            raise CampaignGateError(
                "case report has both structural result and execution error"
            )
        if raw_output is None:
            raise CampaignGateError(
                "case report structural result exists without frozen raw output"
            )
        authority = structural.get("authority", {})
        if (
            authority.get("mode") != "candidate_only"
            or authority.get("canonical_mutation_authority") is not False
            or authority.get("publication_authority") is not False
        ):
            raise CampaignGateError("case report structural authority drift")
        trace_data = structural.get("model_trace", {})
        started_at = structural.get("started_at")
        completed_at = structural.get("completed_at")
        if not all(
            isinstance(value, str) and value
            for value in (
                trace_data.get("provider"),
                trace_data.get("model"),
                trace_data.get("model_version"),
                started_at,
                completed_at,
            )
        ):
            raise CampaignGateError("case report structural provenance is incomplete")
        clock_values = iter([started_at, completed_at])

        def replay_clock() -> str:
            try:
                return next(clock_values)
            except StopIteration as exc:
                raise CampaignGateError(
                    "deterministic draft replay requested unexpected extra clock value"
                ) from exc

        def replay_invoke(prompt: str) -> str:
            if prompt != rendered_prompt:
                raise CampaignGateError(
                    "deterministic draft replay rendered input drifted"
                )
            return raw_output

        try:
            replayed = build_bilingual_draft_run(
                context=context,
                terminology=terminology,
                model_trace=DraftModelTrace(
                    provider=trace_data["provider"],
                    model=trace_data["model"],
                    model_version=trace_data["model_version"],
                ),
                invoke=replay_invoke,
                clock=replay_clock,
            )
        except CampaignGateError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise CampaignGateError(
                "case report deterministic structural replay failed"
            ) from exc
        if replayed != structural:
            raise CampaignGateError(
                "case report structural result does not match deterministic replay"
            )
        accepted = (
            structural.get("validation", {}).get("status")
            == "accepted_for_editorial_review"
        )
        if qualification.get("structural_mechanical_acceptance") is not accepted:
            raise CampaignGateError(
                "case report structural qualification disagrees with replayed result"
            )

    return {
        "report": report,
        "report_sha256": report_sha,
        "invocation_count": invocation_count,
    }


def _default_campaign_runtime_root() -> Path:
    """Return the repository runtime namespace shared by campaign evidence dirs."""

    result = subprocess.run(
        ["git", "-C", str(ROOT), "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise CampaignGateError(
            "cannot resolve git common directory for campaign runtime"
        )
    common = Path(result.stdout.strip())
    if not common.is_absolute():
        common = (ROOT / common).resolve()
    return common / "sda-m4-drafting-campaigns"


def campaign_runtime_dir(
    manifest_sha256: str, runtime_root: Path | None = None
) -> Path:
    root = (
        _default_campaign_runtime_root()
        if runtime_root is None
        else runtime_root.resolve()
    )
    return root / manifest_sha256


def campaign_lock_path(
    manifest_sha256: str, runtime_root: Path | None = None
) -> Path:
    """Return the transient live-controller lock for one exact manifest."""

    return campaign_runtime_dir(manifest_sha256, runtime_root) / ".campaign.lock"


def campaign_binding_path(
    manifest_sha256: str, runtime_root: Path | None = None
) -> Path:
    """Return the persistent manifest-to-evidence-directory binding."""

    return (
        campaign_runtime_dir(manifest_sha256, runtime_root)
        / "evidence-binding.json"
    )


def bind_campaign_evidence_dir(
    path: Path,
    *,
    manifest_sha256: str,
    campaign_id: str,
    evidence_dir: Path,
) -> None:
    """Persistently bind one approved manifest to one evidence directory.

    The binding survives normal lock release and campaign completion. This
    prevents replaying one exact approved manifest into another evidence
    directory to consume the campaign invocation ceiling again.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    expected = {
        "campaign_controller_version": CAMPAIGN_CONTROLLER_VERSION,
        "manifest_sha256": manifest_sha256,
        "campaign_id": campaign_id,
        "evidence_dir": str(evidence_dir.resolve()),
    }
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise CampaignGateError(
                "campaign evidence binding exists but cannot be validated"
            ) from exc
        if existing != expected:
            raise CampaignGateError(
                "campaign manifest is already bound to a different evidence directory"
            )
        return
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_json(expected) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError:
        # Another controller won the atomic create race. Accept only the same
        # exact binding; a different evidence directory fails closed.
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise CampaignGateError(
                "campaign evidence binding raced and cannot be validated"
            ) from exc
        if existing != expected:
            raise CampaignGateError(
                "campaign manifest was concurrently bound to another evidence directory"
            )


@dataclass
class CampaignLock:
    path: Path
    token: str


def acquire_lock(
    path: Path,
    manifest_sha256: str,
) -> CampaignLock:
    """Acquire the campaign lock exclusively; never reclaim an existing lock.

    Any existing lock, including an apparent same-host crash residue, requires
    explicit operator reconciliation/removal. This avoids stale-lock TOCTOU
    races that could otherwise admit concurrent campaign controllers.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    host = socket.gethostname()
    token = _sha256_text(f"{host}:{os.getpid()}:{manifest_sha256}")
    if path.exists():
        raise CampaignGateError(
            "campaign lock already exists; refuse automatic stale-lock recovery"
        )
    payload = {
        "campaign_controller_version": CAMPAIGN_CONTROLLER_VERSION,
        "manifest_sha256": manifest_sha256,
        "hostname": host,
        "pid": os.getpid(),
        "token": token,
    }
    try:
        with open(path, "x", encoding="utf-8", newline="\n") as handle:
            handle.write(_canonical_json(payload) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except FileExistsError as exc:
        raise CampaignGateError(
            "campaign lock raced with another process"
        ) from exc
    return CampaignLock(path=path, token=token)


def release_lock(lock: CampaignLock) -> None:
    if not lock.path.exists():
        return
    try:
        payload = json.loads(lock.path.read_text(encoding="utf-8"))
    except Exception:
        return
    if payload.get("token") == lock.token:
        lock.path.unlink()


def _summary_from_events(
    manifest: dict[str, Any],
    manifest_sha256: str,
    events: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    case_rows = []
    counts = {
        "total_cases": len(manifest["cases"]),
        "recorded_cases": 0,
        "structural_accepted": 0,
        "structural_rejected": 0,
        "execution_failures": 0,
        "invocations": 0,
    }
    for event in events:
        if event["event_type"] not in {
            "case_completed",
            "case_execution_failure",
        }:
            continue
        row = dict(event["payload"])
        case_rows.append(row)
        counts["recorded_cases"] += 1
        counts["invocations"] += int(row["invocation_count"])
        if event["event_type"] == "case_execution_failure":
            counts["execution_failures"] += 1
        elif row["structural_status"] == "accepted_for_editorial_review":
            counts["structural_accepted"] += 1
        else:
            counts["structural_rejected"] += 1
    return {
        "summary_version": CAMPAIGN_SUMMARY_VERSION,
        "campaign_controller_version": CAMPAIGN_CONTROLLER_VERSION,
        "campaign_id": manifest["campaign_id"],
        "manifest_sha256": manifest_sha256,
        "reviewed_head": manifest["reviewed_head"],
        "route": manifest["route"],
        "entitlement_id": manifest["entitlement_id"],
        "model": manifest["model"],
        "status": status,
        "counts": counts,
        "cases": case_rows,
        "qualification": {
            "structural_campaign_evidence_only": True,
            "editorial_quality_qualified": False,
            "production_model_pipeline_qualified": False,
            "publication_authority": False,
            "canonical_mutation_authority": False,
        },
        "claim_ceiling": (
            "Bounded campaign evidence over the frozen manifest only. "
            "Structural outcomes are deterministic boundary results; "
            "Arabic/English editorial quality remains pending human review. "
            "No production reliability, scale, publication, or "
            "canonical-mutation inference is supported."
        ),
    }


def _verify_immutable_json(path: Path) -> tuple[dict[str, Any], str]:
    sidecar = sidecar_path(path)
    if not path.exists() or not sidecar.exists():
        raise CampaignGateError(f"incomplete immutable campaign artifact: {path}")
    body = path.read_bytes()
    digest = _sha256_bytes(body)
    if _read_sidecar(sidecar, path.name) != digest:
        raise CampaignGateError(f"campaign artifact sidecar mismatch: {path}")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CampaignGateError(f"campaign artifact is not valid UTF-8 JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise CampaignGateError(f"campaign JSON artifact root must be an object: {path}")
    return payload, digest


def _write_immutable_json(path: Path, payload: dict[str, Any]) -> str:
    sidecar = sidecar_path(path)
    if path.exists() or sidecar.exists():
        raise CampaignGateError(
            f"refusing to overwrite campaign artifact: {path}"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    body = (
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
        + "\n"
    ).encode("utf-8")
    digest = _sha256_bytes(body)
    try:
        with open(path, "xb") as handle:
            handle.write(body)
        with open(sidecar, "xb") as handle:
            handle.write(f"{digest}  {path.name}\n".encode("utf-8"))
    except FileExistsError as exc:
        raise CampaignGateError(
            "campaign artifact creation raced with another writer"
        ) from exc
    return digest


def _case_payload(
    case: dict[str, Any],
    report_path: Path,
    verified: dict[str, Any],
) -> dict[str, Any]:
    report = verified["report"]
    structural = report.get("structural_result")
    structural_status = (
        structural.get("validation", {}).get("status")
        if isinstance(structural, dict)
        else "no_draft_run"
    )
    return {
        "case_id": case["case_id"],
        "fixture": case["fixture"],
        "fixture_sha256": case["fixture_sha256"],
        "report_path": report_path.name,
        "report_sha256": verified["report_sha256"],
        "invocation_count": verified["invocation_count"],
        "structural_status": structural_status,
        "execution_error": report.get("execution_error"),
    }


def _verify_recorded_case_evidence(
    manifest: dict[str, Any],
    events: list[dict[str, Any]],
    evidence_dir: Path,
    attestation: str,
) -> None:
    """Re-close recorded case ledger events over immutable case evidence."""

    cases_by_id = {case["case_id"]: case for case in manifest["cases"]}
    terminal_cases = _case_events(events)
    for case_id, event in terminal_cases.items():
        case = cases_by_id.get(case_id)
        if case is None:
            raise CampaignGateError(
                f"terminal ledger references unknown campaign case {case_id}"
            )
        report_path = evidence_dir / f"{case_id}.json"
        payload = event["payload"]
        if payload.get("report_path") != report_path.name:
            raise CampaignGateError(
                f"terminal ledger report path mismatch for {case_id}"
            )
        verified = verify_case_report(
            report_path, case, manifest, attestation
        )
        rebuilt = _case_payload(case, report_path, verified)
        for field in (
            "case_id",
            "fixture",
            "fixture_sha256",
            "report_path",
            "report_sha256",
            "invocation_count",
            "structural_status",
            "execution_error",
        ):
            if payload.get(field) != rebuilt[field]:
                raise CampaignGateError(
                    f"terminal ledger/evidence mismatch for {case_id}: {field}"
                )
        if not isinstance(payload.get("recovered_without_invocation"), bool):
            raise CampaignGateError(
                f"terminal ledger recovery flag is invalid for {case_id}"
            )


def verify_provider_boundary_source(
    *,
    prompt: str,
    case: dict[str, Any],
    manifest: dict[str, Any],
    git_state_provider: Callable[[], tuple[str, str, bool | None]],
) -> None:
    """Revalidate reviewed source bytes against the exact prompt about to be sent."""

    git_head, _git_ref_value, clean = git_state_provider()
    if git_head != manifest["reviewed_head"] or clean is not True:
        raise CampaignGateError(
            "campaign source state drifted at the provider boundary"
        )

    fixture_path = _repo_path(case["fixture"])
    terminology_path = _repo_path(manifest["terminology_file"])
    if _file_sha256(fixture_path) != case["fixture_sha256"]:
        raise CampaignGateError(
            f"campaign fixture hash drifted at provider boundary: {case['case_id']}"
        )
    if _file_sha256(terminology_path) != manifest["terminology_file_sha256"]:
        raise CampaignGateError(
            "campaign terminology hash drifted at provider boundary"
        )

    try:
        _, context_json, _, _delivery_json, _ = split_rendered_prompt(prompt)
        prompt_context = json.loads(context_json)
        if not isinstance(prompt_context, dict):
            raise CampaignGateError(
                "provider-boundary prompt context is not an object"
            )
        created_at = prompt_context.get("created_at")
        if not isinstance(created_at, str) or not created_at:
            raise CampaignGateError(
                "provider-boundary prompt context lacks created_at"
            )
        fixture = load_fixture(fixture_path)
        terminology_payload = json.loads(
            terminology_path.read_text(encoding="utf-8")
        )
        terminology = load_terminology(terminology_payload)
        expected_context = build_drafting_context_from_fixture(
            fixture, terminology, created_at
        )
        expected_prompt, _ = prepare_draft_input(
            expected_context, terminology
        )
    except CampaignGateError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise CampaignGateError(
            "provider-boundary source/prompt reconstruction failed"
        ) from exc

    if expected_context != prompt_context or expected_prompt != prompt:
        raise CampaignGateError(
            "provider-boundary prompt does not match fresh manifest-bound source bytes"
        )


def run_campaign(
    *,
    manifest_path: Path,
    evidence_dir: Path,
    entitlement_attestation: str,
    require_api_key: Callable[[], str] = require_zai_api_key,
    invoke_factory: Callable[..., Callable[[str], str]] = zai_invoker,
    git_state_provider: (
        Callable[[], tuple[str, str, bool | None]] | None
    ) = None,
    env_url_provider: Callable[[], str] | None = None,
    clock: Callable[[], str] | None = None,
    runtime_root: Path | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone

    if clock is None:
        clock = lambda: datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        )
    if git_state_provider is None:
        git_state_provider = lambda: (
            _git_head(ROOT),
            _git_ref(ROOT),
            _worktree_clean(ROOT),
        )
    if env_url_provider is None:
        env_url_provider = lambda: os.environ.get(
            ZAI_BASE_URL_ENV, ""
        ).strip()

    manifest, manifest_sha256 = load_manifest(manifest_path)
    attestation = check_campaign_entitlement(manifest, entitlement_attestation)
    evidence_dir = evidence_dir.resolve()
    bind_campaign_evidence_dir(
        campaign_binding_path(manifest_sha256, runtime_root),
        manifest_sha256=manifest_sha256,
        campaign_id=manifest["campaign_id"],
        evidence_dir=evidence_dir,
    )
    evidence_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = evidence_dir / "campaign-ledger.jsonl"
    frozen_manifest_path = evidence_dir / "campaign-manifest.json"
    summary_path = evidence_dir / "campaign-summary.json"
    lock = acquire_lock(
        campaign_lock_path(manifest_sha256, runtime_root),
        manifest_sha256,
    )
    try:
        if frozen_manifest_path.exists() or sidecar_path(frozen_manifest_path).exists():
            frozen_manifest, _ = _verify_immutable_json(frozen_manifest_path)
            if _sha256_text(_canonical_json(frozen_manifest)) != manifest_sha256:
                raise CampaignGateError(
                    "frozen campaign manifest does not match the supplied manifest"
                )
        else:
            _write_immutable_json(frozen_manifest_path, manifest)

        events = load_ledger(
            ledger_path, manifest["campaign_id"], manifest_sha256
        )
        if events:
            campaign_starts = [
                event for event in events if event["event_type"] == "campaign_started"
            ]
            if len(campaign_starts) != 1 or campaign_starts[0]["sequence"] != 1:
                raise CampaignGateError(
                    "campaign ledger must contain exactly one leading campaign_started event"
                )
            frozen_attestation_sha = campaign_starts[0]["payload"].get(
                "entitlement_attestation_sha256"
            )
            if frozen_attestation_sha != _sha256_text(attestation):
                raise CampaignGateError(
                    "campaign entitlement attestation changed across resume"
                )
        recorded = _case_events(events)
        if recorded:
            _verify_recorded_case_evidence(
                manifest, events, evidence_dir, attestation
            )

        terminal = _terminal_event(events)
        if terminal is None:
            failed_events = [
                event
                for event in recorded.values()
                if event["event_type"] == "case_execution_failure"
            ]
            if failed_events:
                if len(failed_events) != 1:
                    raise CampaignGateError(
                        "campaign ledger has multiple recorded execution failures"
                    )
                failed_event = failed_events[0]
                later_case_events = [
                    event
                    for event in events
                    if event["event_type"] in {
                        "case_completed",
                        "case_execution_failure",
                    }
                    and event["sequence"] > failed_event["sequence"]
                ]
                if later_case_events:
                    raise CampaignGateError(
                        "campaign ledger contains case results after an execution failure"
                    )
                append_event(
                    ledger_path,
                    campaign_id=manifest["campaign_id"],
                    manifest_sha256=manifest_sha256,
                    event_type="campaign_stopped",
                    payload={
                        "status": "stopped_execution_failure",
                        "case_id": failed_event["payload"]["case_id"],
                    },
                    clock=clock,
                )
                events = load_ledger(
                    ledger_path, manifest["campaign_id"], manifest_sha256
                )
                terminal = _terminal_event(events)

        if terminal is not None:
            expected_summary = _summary_from_events(
                manifest,
                manifest_sha256,
                events,
                terminal["payload"]["status"],
            )
            if summary_path.exists() or sidecar_path(summary_path).exists():
                stored_summary, _ = _verify_immutable_json(summary_path)
                if stored_summary != expected_summary:
                    raise CampaignGateError(
                        "terminal campaign summary does not match the verified ledger"
                    )
            else:
                _write_immutable_json(summary_path, expected_summary)
            return expected_summary

        if not events:
            append_event(
                ledger_path,
                campaign_id=manifest["campaign_id"],
                manifest_sha256=manifest_sha256,
                event_type="campaign_started",
                payload={
                    "reviewed_head": manifest["reviewed_head"],
                    "route": manifest["route"],
                    "entitlement_id": manifest["entitlement_id"],
                    "entitlement_attestation_sha256": _sha256_text(attestation),
                    "model": manifest["model"],
                    "max_invocations": manifest["max_invocations"],
                    "case_count": len(manifest["cases"]),
                },
                clock=clock,
            )
            events = load_ledger(
                ledger_path, manifest["campaign_id"], manifest_sha256
            )

        recorded = _case_events(events)
        started = _started_cases(events)
        invocations_used = len(started)

        for case in manifest["cases"]:
            if case["case_id"] in recorded:
                continue
            report_path = evidence_dir / f"{case['case_id']}.json"
            report_exists = report_path.exists()
            sidecar_exists = sidecar_path(report_path).exists()

            if case["case_id"] in started and not (report_exists and sidecar_exists):
                raise CampaignGateError(
                    f"ambiguous prior invocation for {case['case_id']}; "
                    "start event exists without complete immutable case evidence"
                )

            if report_exists or sidecar_exists:
                if not (report_exists and sidecar_exists):
                    raise CampaignGateError(
                        f"ambiguous crash evidence for {case['case_id']}"
                    )
                if case["case_id"] not in started:
                    raise CampaignGateError(
                        f"foreign/ambiguous case evidence for {case['case_id']}: "
                        "complete report exists without campaign invocation-start marker"
                    )
                verified = verify_case_report(report_path, case, manifest, attestation)
                payload = _case_payload(case, report_path, verified)
                if case["case_id"] not in started:
                    invocations_used += int(payload["invocation_count"])
                event_type = (
                    "case_execution_failure"
                    if payload["execution_error"] is not None
                    else "case_completed"
                )
                append_event(
                    ledger_path,
                    campaign_id=manifest["campaign_id"],
                    manifest_sha256=manifest_sha256,
                    event_type=event_type,
                    payload={
                        **payload,
                        "recovered_without_invocation": True,
                    },
                    clock=clock,
                )
                if event_type == "case_execution_failure":
                    append_event(
                        ledger_path,
                        campaign_id=manifest["campaign_id"],
                        manifest_sha256=manifest_sha256,
                        event_type="campaign_stopped",
                        payload={
                            "status": "stopped_execution_failure",
                            "case_id": case["case_id"],
                        },
                        clock=clock,
                    )
                    break
                continue

            if invocations_used >= manifest["max_invocations"]:
                append_event(
                    ledger_path,
                    campaign_id=manifest["campaign_id"],
                    manifest_sha256=manifest_sha256,
                    event_type="campaign_stopped",
                    payload={
                        "status": "stopped_call_ceiling",
                        "case_id": case["case_id"],
                    },
                    clock=clock,
                )
                break

            git_head, git_ref, clean = git_state_provider()
            if git_head != manifest["reviewed_head"] or clean is not True:
                raise CampaignGateError(
                    "campaign source state drifted from reviewed clean head"
                )

            case_args = argparse.Namespace(
                fixture=_repo_path(case["fixture"]),
                model=manifest["model"],
                zai_endpoint=manifest["route"],
                base_url=None,
                reviewed_head=manifest["reviewed_head"],
                entitlement_attestation=attestation,
                timeout_seconds=manifest["timeout_seconds"],
                output=report_path,
            )
            marker_written = False

            def mark_invocation_started(rendered_prompt: str) -> None:
                nonlocal invocations_used, marker_written
                verify_provider_boundary_source(
                    prompt=rendered_prompt,
                    case=case,
                    manifest=manifest,
                    git_state_provider=git_state_provider,
                )
                if marker_written or case["case_id"] in started:
                    raise CampaignGateError(
                        f"duplicate invocation-start marker for {case['case_id']}"
                    )
                if invocations_used >= manifest["max_invocations"]:
                    raise CampaignGateError(
                        "campaign invocation ceiling reached before provider invocation"
                    )
                event = append_event(
                    ledger_path,
                    campaign_id=manifest["campaign_id"],
                    manifest_sha256=manifest_sha256,
                    event_type="case_invocation_started",
                    payload={
                        "case_id": case["case_id"],
                        "fixture": case["fixture"],
                        "fixture_sha256": case["fixture_sha256"],
                        "conservative_call_budget_charge": 1,
                    },
                    clock=clock,
                )
                started[case["case_id"]] = event
                invocations_used += 1
                marker_written = True

            run_trial(
                args=case_args,
                env_url=env_url_provider(),
                git_head=git_head,
                git_ref=git_ref,
                worktree_clean=clean,
                require_api_key=require_api_key,
                invoke_factory=invoke_factory,
                created_at_fn=clock,
                before_invoke=mark_invocation_started,
            )
            if not marker_written:
                raise CampaignGateError(
                    f"single-case driver returned without invocation marker for {case['case_id']}"
                )
            verified = verify_case_report(report_path, case, manifest, attestation)
            payload = _case_payload(case, report_path, verified)
            if invocations_used > manifest["max_invocations"]:
                raise CampaignGateError(
                    "campaign invocation ceiling exceeded"
                )
            event_type = (
                "case_execution_failure"
                if payload["execution_error"] is not None
                else "case_completed"
            )
            append_event(
                ledger_path,
                campaign_id=manifest["campaign_id"],
                manifest_sha256=manifest_sha256,
                event_type=event_type,
                payload={
                    **payload,
                    "recovered_without_invocation": False,
                },
                clock=clock,
            )
            if event_type == "case_execution_failure":
                append_event(
                    ledger_path,
                    campaign_id=manifest["campaign_id"],
                    manifest_sha256=manifest_sha256,
                    event_type="campaign_stopped",
                    payload={
                        "status": "stopped_execution_failure",
                        "case_id": case["case_id"],
                    },
                    clock=clock,
                )
                break

        events = load_ledger(
            ledger_path, manifest["campaign_id"], manifest_sha256
        )
        terminal = _terminal_event(events)
        if terminal is None:
            recorded = _case_events(events)
            if len(recorded) == len(manifest["cases"]):
                append_event(
                    ledger_path,
                    campaign_id=manifest["campaign_id"],
                    manifest_sha256=manifest_sha256,
                    event_type="campaign_completed",
                    payload={"status": "completed"},
                    clock=clock,
                )
                events = load_ledger(
                    ledger_path, manifest["campaign_id"], manifest_sha256
                )
                terminal = _terminal_event(events)

        status = (
            terminal["payload"]["status"] if terminal else "running"
        )
        if terminal is not None:
            _verify_recorded_case_evidence(
                manifest, events, evidence_dir, attestation
            )
        summary = _summary_from_events(
            manifest, manifest_sha256, events, status
        )
        if status in {
            "completed",
            "stopped_execution_failure",
            "stopped_call_ceiling",
        }:
            if summary_path.exists() or sidecar_path(summary_path).exists():
                stored_summary, _ = _verify_immutable_json(summary_path)
                if stored_summary != summary:
                    raise CampaignGateError(
                        "campaign summary does not match the verified ledger"
                    )
            else:
                _write_immutable_json(summary_path, summary)
        return summary
    finally:
        release_lock(lock)


def main() -> int:
    args = parse_args()
    summary = run_campaign(
        manifest_path=args.manifest,
        evidence_dir=args.evidence_dir,
        entitlement_attestation=args.entitlement_attestation,
    )
    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
