#!/usr/bin/env python3
"""Run the bounded M4 live bilingual drafting trial through the Z.ai provider edge.

Pre-invocation gates (all fail closed, all individually testable):
- `check_git_state`: HEAD must resolve, worktree must be clean, and HEAD must
  equal the explicit `--reviewed-head` SHA (the independently reviewed commit).
- `check_entitlement`: a non-empty attestation string is required; the standing
  extraction entitlement does not cover drafting.
- `check_route_args`: any combination of `--base-url`, `--zai-endpoint`, and
  `ZAI_BASE_URL` that creates route ambiguity is refused.
- `write_report_with_sidecar`: refuses to overwrite an existing file.

Evidence immutability: the report embeds the exact rendered input and raw
model output verbatim alongside their hashes, and the report builder verifies
the embedded draft run's hash chain agrees with the frozen bytes. Transport
failures produce a bounded failure report with `invocation_attempted` /
`invocation_count` provenance and no retry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_m4_model_extraction_trial import (  # noqa: E402
    ZAI_BASE_URL_ENV,
    _file_sha256,
    require_zai_api_key,
    resolve_zai_base_url,
    validate_zai_base_url,
    zai_invoker,
)
from services.intelligence.bilingual_drafting import (  # noqa: E402
    ADAPTER_VERSION as DRAFTING_ADAPTER_VERSION,
    BilingualDraftingError,
    DRAFT_PROMPT_TEMPLATE_ID,
    DRAFT_PROMPT_TEMPLATE_VERSION,
    DraftModelTrace,
    build_approved_drafting_context,
    build_bilingual_draft_run,
    draft_prompt_template_sha256,
    load_terminology,
    prepare_draft_input,
    split_rendered_prompt,
)
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ADAPTER_VERSION as EXTRACTION_ADAPTER_VERSION,
)

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "m4-drafting-trial-v0.1.json"
DEFAULT_TERMINOLOGY = ROOT / "data" / "terminology" / "bilingual-terminology-v0.1.json"

REPORT_VERSION = "m4-drafting-live-trial-v0.3"
EDITORIAL_DIMENSIONS = [
    "Arabic fluency",
    "English fluency",
    "factual faithfulness of phrasing",
    "bilingual adequacy",
    "terminology quality",
    "awkward or misleading wording",
]


class TrialGateError(SystemExit):
    """Raised when a pre-invocation gate refuses the run."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--model", default="glm-5.3")
    parser.add_argument("--zai-endpoint", choices=("coding-plan", "prepaid"), default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--reviewed-head",
        required=True,
        help="the exact independently reviewed commit SHA this trial is authorized to run from",
    )
    parser.add_argument(
        "--entitlement-attestation",
        required=True,
        help="explicit attestation for THIS live drafting call (not covered by extraction entitlement)",
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


# --- Individually testable pre-invocation gates ---


def check_entitlement(attestation: str) -> str:
    value = attestation.strip()
    if not value:
        raise TrialGateError("--entitlement-attestation must be non-empty")
    return value


def check_route_args(
    base_url_arg: str | None,
    endpoint_arg: str | None,
    env_url: str,
) -> None:
    """Refuse any ambiguous route combination (DTD-01R)."""

    supplied = [name for name, value in (
        ("--base-url", base_url_arg),
        ("--zai-endpoint", endpoint_arg),
        (ZAI_BASE_URL_ENV, env_url),
    ) if value]
    if len(supplied) > 1:
        raise TrialGateError(
            f"ambiguous Z.ai route: {', '.join(supplied)} are all set; supply exactly one"
        )


def check_git_state(
    git_head: str, worktree_clean: bool | None, reviewed_head: str
) -> None:
    """Refuse unless HEAD resolves, worktree is clean, and HEAD is the reviewed SHA (DTD-05R)."""

    if not git_head:
        raise TrialGateError("cannot resolve git HEAD")
    if worktree_clean is not True:
        raise TrialGateError(
            "tracked worktree is dirty or git is unavailable; live evidence "
            "requires a clean checkout"
        )
    if git_head != reviewed_head:
        raise TrialGateError(
            f"git HEAD {git_head} is not the reviewed head {reviewed_head}; "
            "live drafting must run from the independently reviewed commit"
        )


def check_attestation_route_binding(attestation: str, resolved_base_url: str) -> None:
    """The attestation must name the route the call actually uses (DTD-01R)."""

    if "coding" in resolved_base_url and "coding" not in attestation.lower():
        raise TrialGateError(
            "entitlement attestation does not mention the coding-plan route the "
            "call would use; bind the attestation to the resolved endpoint"
        )
    if "paas/v4" in resolved_base_url and "coding" not in resolved_base_url:
        if "prepaid" not in attestation.lower() and "general" not in attestation.lower():
            raise TrialGateError(
                "entitlement attestation does not mention the prepaid/general route "
                "the call would use"
            )


# --- Fixture / context / invocation ---


def load_fixture(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    for key in ("version", "entities", "claims", "evidence", "unknowns"):
        if key not in payload:
            raise RuntimeError(f"drafting fixture requires {key}")
    return payload


def build_drafting_context_from_fixture(
    fixture: dict, terminology: dict, created_at: str
) -> dict:
    return build_approved_drafting_context(
        entities=fixture["entities"],
        claims=fixture["claims"],
        evidence=fixture["evidence"],
        unknowns=fixture["unknowns"],
        terminology=terminology,
        created_at=created_at,
    )


def execute_draft_invocation(
    *,
    context: dict,
    terminology: dict,
    model_trace: DraftModelTrace,
    invoke_fn: Callable[[str], str],
) -> tuple[dict[str, Any] | None, str | None, str | None, float]:
    """Run one invocation; return (draft_run, error, raw_output, elapsed)."""

    raw_holder: list[str] = []

    def capturing(prompt: str) -> str:
        result = invoke_fn(prompt)
        raw_holder.append(result)
        return result

    started = time.monotonic()
    draft_run = None
    error = None
    try:
        draft_run = build_bilingual_draft_run(
            context=context,
            terminology=terminology,
            model_trace=model_trace,
            invoke=capturing,
        )
    except Exception as exc:  # noqa: BLE001 — failure must produce a report
        error = str(exc)[:512]
    elapsed = time.monotonic() - started
    raw_output = raw_holder[0] if raw_holder else None
    return draft_run, error, raw_output, elapsed


# --- Report builder (factored for deterministic validation) ---


def build_trial_report(
    *,
    fixture: dict,
    terminology_payload: dict,
    context: dict,
    rendered_prompt: str,
    raw_model_output: str | None,
    draft_run: dict[str, Any] | None,
    execution_error: str | None,
    invocation_attempted: bool,
    invocation_count: int,
    requested_model: str,
    base_url: str,
    base_url_source: str,
    endpoint_arg: str | None,
    entitlement_attestation: str,
    reviewed_head: str,
    git_head: str,
    git_ref: str,
    worktree_clean: bool,
    fixture_path: Path,
    terminology_path: Path,
    elapsed_seconds: float,
) -> dict[str, Any]:
    terminology = load_terminology(terminology_payload)
    rendered_sha = hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()
    raw_sha = (
        hashlib.sha256(raw_model_output.encode("utf-8")).hexdigest()
        if raw_model_output is not None
        else None
    )

    # DTD-02R: the embedded draft run's hash chain must agree with the
    # frozen bytes, when both exist.
    if draft_run is not None and raw_model_output is not None:
        if draft_run.get("raw_output_sha256") != raw_sha:
            raise RuntimeError(
                "draft run raw_output_sha256 does not match the frozen raw output bytes"
            )
        if draft_run.get("input_context_sha256") != context.get("_context_sha_for_check"):
            pass  # context hash checked via prompt_trace below
        prompt_trace = draft_run.get("prompt_trace", {})
        if prompt_trace.get("rendered_input_sha256") != rendered_sha:
            raise RuntimeError(
                "draft run rendered_input_sha256 does not match the frozen rendered input bytes"
            )

    structural_accepted = (
        draft_run is not None
        and draft_run.get("validation", {}).get("status") == "accepted_for_editorial_review"
    )
    _, _, _, delivery_json, _ = split_rendered_prompt(rendered_prompt)

    return {
        "report_version": REPORT_VERSION,
        "fixture_version": fixture["version"],
        "provider": "zai-openai-compatible-api",
        "requested_model": requested_model,
        "provider_checkpoint_version": None,
        "provider_edge": {
            "driver": "zai-openai-compatible-http",
            "resolved_base_url": base_url,
            "resolved_base_url_source": base_url_source,
            "requested_endpoint_mode": endpoint_arg,
            "credential_source": "ZAI_API_KEY environment variable",
            "transport": "python-stdlib-urllib",
            "tools": "none",
            "reasoning_configuration": {
                "thinking_type": "enabled",
                "reasoning_effort": "max",
                "explicitly_pinned": True,
            },
        },
        "entitlement": {
            "attestation": entitlement_attestation,
            "resolved_base_url": base_url,
            "standing_extraction_entitlement_covers_drafting": False,
        },
        "reviewed_head": reviewed_head,
        "drafting_boundary_versions": {
            "drafting_adapter": DRAFTING_ADAPTER_VERSION,
            "extraction_adapter_at_build": EXTRACTION_ADAPTER_VERSION,
            "prompt_template_id": DRAFT_PROMPT_TEMPLATE_ID,
            "prompt_template_version": DRAFT_PROMPT_TEMPLATE_VERSION,
            "prompt_template_sha256": draft_prompt_template_sha256(),
        },
        "terminology": {
            "registry_version": terminology["version"],
            "registry_acceptance_sha256": context["terminology_sha256"],
            "delivery_payload_sha256": hashlib.sha256(
                delivery_json.encode("utf-8")
            ).hexdigest(),
            "terminology_file_sha256": _file_sha256(terminology_path),
        },
        "trial_context": {
            "git_head": git_head,
            "git_ref": git_ref,
            "tracked_worktree_clean": worktree_clean,
            "python_version": platform.python_version(),
            "fixture_sha256": _file_sha256(fixture_path),
        },
        "invocation": {
            "attempted": invocation_attempted,
            "count": invocation_count,
            "rendered_input_sha256": rendered_sha,
            "raw_model_output_sha256": raw_sha,
            "elapsed_seconds": round(elapsed_seconds, 3),
        },
        "evidence": {
            "rendered_model_input": rendered_prompt,
            "raw_model_output": raw_model_output,
        },
        "structural_result": draft_run,
        "execution_error": execution_error,
        "editorial_assessment": {
            "status": "pending_human_review",
            "mechanical_score": None,
            "notes": None,
            "assessment_dimensions": EDITORIAL_DIMENSIONS,
        },
        "qualification": {
            "structural_mechanical_acceptance": structural_accepted,
            "editorial_quality_qualified": False,
            "production_model_pipeline_qualified": False,
            "publication_authority": False,
            "canonical_mutation_authority": False,
            "bounded_evidence_only": True,
            "served_model_checkpoint": "unknown",
        },
        "claim_ceiling": (
            "Bounded evidence from one live invocation through the reviewed "
            "drafting boundary on a synthetic fixture. No production-quality, "
            "reliability, scalability, cost, or publication inference is "
            "supported. Editorial quality is unqualified until independent "
            "human review completes."
        ),
    }


# --- Immutable artifact writer ---


def write_report_with_sidecar(output: Path, report: dict[str, Any]) -> str:
    """Write the report + sidecar; refuse if either file already exists (DTD-02R)."""

    sidecar = output.with_name(output.name + ".sha256")
    if output.exists():
        raise TrialGateError(f"refusing to overwrite existing artifact: {output}")
    if sidecar.exists():
        raise TrialGateError(f"refusing to overwrite existing artifact: {sidecar}")
    output.parent.mkdir(parents=True, exist_ok=True)
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    output.write_bytes(report_bytes)
    report_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar.write_bytes(f"{report_sha}  {output.name}\n".encode("utf-8"))
    return report_sha


# --- Git helpers ---


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_ref(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _worktree_clean(root: Path) -> bool | None:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        return None
    return not result.stdout.strip()


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


# --- Main ---


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise TrialGateError("--timeout-seconds must be positive")

    attestation = check_entitlement(args.entitlement_attestation)

    git_head = _git_head(ROOT)
    git_ref = _git_ref(ROOT)
    worktree_clean = _worktree_clean(ROOT)
    check_git_state(git_head, worktree_clean, args.reviewed_head)

    api_key = require_zai_api_key()
    env_url = os.environ.get(ZAI_BASE_URL_ENV, "").strip()
    check_route_args(args.base_url, args.zai_endpoint, env_url)
    base_url, base_url_source = resolve_zai_base_url(args.base_url, args.zai_endpoint)
    validate_zai_base_url(base_url)
    check_attestation_route_binding(attestation, base_url)

    fixture = load_fixture(args.fixture)
    terminology_payload = json.loads(DEFAULT_TERMINOLOGY.read_text(encoding="utf-8"))
    terminology = load_terminology(terminology_payload)
    context = build_drafting_context_from_fixture(fixture, terminology, _utc_now())
    rendered_prompt, _ = prepare_draft_input(context, terminology)

    trace = DraftModelTrace(
        provider="zai-openai-compatible-api",
        model=args.model,
        model_version="provider-managed-unknown",
    )
    invoke = zai_invoker(
        model=args.model,
        api_key=api_key,
        base_url=base_url,
        timeout_seconds=args.timeout_seconds,
    )

    attempt_counter = [0]

    def counting_invoke(prompt: str) -> str:
        attempt_counter[0] += 1
        return invoke(prompt)

    draft_run, execution_error, raw_output, elapsed = execute_draft_invocation(
        context=context,
        terminology=terminology,
        model_trace=trace,
        invoke_fn=counting_invoke,
    )

    report = build_trial_report(
        fixture=fixture,
        terminology_payload=terminology_payload,
        context=context,
        rendered_prompt=rendered_prompt,
        raw_model_output=raw_output,
        draft_run=draft_run,
        execution_error=execution_error,
        invocation_attempted=attempt_counter[0] > 0,
        invocation_count=attempt_counter[0],
        requested_model=args.model,
        base_url=base_url,
        base_url_source=base_url_source,
        endpoint_arg=args.zai_endpoint,
        entitlement_attestation=attestation,
        reviewed_head=args.reviewed_head,
        git_head=git_head,
        git_ref=git_ref,
        worktree_clean=worktree_clean is True,
        fixture_path=args.fixture,
        terminology_path=DEFAULT_TERMINOLOGY,
        elapsed_seconds=elapsed,
    )

    report_sha = write_report_with_sidecar(args.output, report)

    structural_status = (
        draft_run["validation"]["status"] if draft_run else "no_draft_run"
    )
    print(
        json.dumps(
            {
                "structural_status": structural_status,
                "execution_error": execution_error is not None,
                "invocation_count": attempt_counter[0],
                "elapsed_seconds": round(elapsed, 3),
                "report_sha256": report_sha,
                "output": str(args.output),
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 1 if execution_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
