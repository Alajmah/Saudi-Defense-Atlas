#!/usr/bin/env python3
"""Run the bounded M4 live bilingual drafting trial through the Z.ai provider edge.

Loads an approved canonical drafting fixture, renders the reviewed v0.2
two-block model input through the deterministic drafting boundary, sends it to
Z.ai's OpenAI-compatible API, and captures the resulting ``AI bilingual draft
run`` with the exact rendered input, exact raw model output, full hash
provenance, and a failure-report path for transport errors. Mechanical/
structural acceptance and human editorial assessment are independent dimensions;
this runner scores only the former and records the latter as a
pending-human-review placeholder.

Pre-invocation gates (fail closed):
- git HEAD must resolve; tracked worktree must be clean;
- an explicit ``--entitlement-attestation`` is required (the standing
  extraction entitlement does not cover live drafting);
- the route must be unambiguous (``ZAI_BASE_URL`` and ``--zai-endpoint``
  together are refused);
- output files must not already exist (no overwrite).

The runner does not read or write the canonical knowledge backend and does not
publish anything. Transport/provider failures produce a bounded failure report
with no retry.
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
    DRAFT_TERMINOLOGY_TOKEN,
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

REPORT_VERSION = "m4-drafting-live-trial-v0.2"
EDITERIAL_DIMENSIONS = [
    "Arabic fluency",
    "English fluency",
    "factual faithfulness of phrasing",
    "bilingual adequacy",
    "terminology quality",
    "awkward or misleading wording",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument("--model", default="glm-5.3")
    parser.add_argument("--zai-endpoint", choices=("coding-plan", "prepaid"), default=None)
    parser.add_argument("--base-url", default=None)
    parser.add_argument(
        "--entitlement-attestation",
        required=True,
        help=(
            "explicit attestation string for THIS live drafting call (the standing "
            "extraction entitlement does not cover drafting); recorded verbatim"
        ),
    )
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


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


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _refuse_overwrite(*paths: Path) -> None:
    existing = [str(p) for p in paths if p.exists()]
    if existing:
        raise SystemExit(
            f"refusing to overwrite existing artifact(s): {', '.join(existing)}"
        )


def resolve_route(
    base_url_arg: str | None, endpoint_arg: str | None
) -> tuple[str, str]:
    """Resolve the endpoint with fail-closed ambiguity handling (DTD-01)."""

    env_url = os.environ.get(ZAI_BASE_URL_ENV, "").strip()
    if endpoint_arg and env_url:
        raise SystemExit(
            f"ambiguous Z.ai route: both --zai-endpoint {endpoint_arg} and "
            f"{ZAI_BASE_URL_ENV} are set; remove one before running"
        )
    if base_url_arg and env_url:
        raise SystemExit(
            f"ambiguous Z.ai route: both --base-url and {ZAI_BASE_URL_ENV} are set"
        )
    base_url, source = resolve_zai_base_url(base_url_arg, endpoint_arg)
    validate_zai_base_url(base_url)
    return base_url, source


def build_trial_report(
    *,
    fixture: dict,
    terminology_payload: dict,
    context: dict,
    rendered_prompt: str,
    raw_model_output: str | None,
    draft_run: dict | None,
    execution_error: str | None,
    requested_model: str,
    base_url: str,
    base_url_source: str,
    endpoint_arg: str | None,
    entitlement_attestation: str,
    git_head: str,
    git_ref: str,
    worktree_clean: bool,
    fixture_path: Path,
    terminology_path: Path,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Build the evidence report; callable with fake invoker results (DTD-03)."""

    terminology = load_terminology(terminology_payload)
    rendered_sha = hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()
    raw_sha = (
        hashlib.sha256(raw_model_output.encode("utf-8")).hexdigest()
        if raw_model_output is not None
        else None
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
            "standing_extraction_entitlement_covers_drafting": False,
            "note": (
                "The standing Coding Plan approval covers bounded M4 structured-extraction "
                "runs. Live drafting requires this explicit per-run attestation."
            ),
        },
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
            "rendered_input_sha256": rendered_sha,
            "raw_model_output_sha256": raw_sha,
            "elapsed_seconds": round(elapsed_seconds, 3),
        },
        "evidence": {
            "rendered_model_input": rendered_prompt,
            "raw_model_output": raw_model_output,
            "note": (
                "Exact dynamic bytes frozen for audit; the structural result below is "
                "the reviewed boundary's typed projection of the raw output."
            ),
        },
        "structural_result": draft_run,
        "execution_error": execution_error,
        "editorial_assessment": {
            "status": "pending_human_review",
            "mechanical_score": None,
            "notes": None,
            "assessment_dimensions": EDITERIAL_DIMENSIONS,
            "note": (
                "This section is a placeholder for independent human editorial "
                "review. A mechanically accepted draft can still be editorially "
                "poor; a fluent draft cannot override a mechanical rejection. "
                "No mechanical editorial score exists in this increment."
            ),
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


def write_report_with_sidecar(output: Path, report: dict[str, Any]) -> str:
    output.parent.mkdir(parents=True, exist_ok=True)
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    output.write_bytes(report_bytes)
    report_sha = hashlib.sha256(output.read_bytes()).hexdigest()
    sidecar = output.with_name(output.name + ".sha256")
    sidecar.write_bytes(f"{report_sha}  {output.name}\n".encode("utf-8"))
    return report_sha


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    attestation = args.entitlement_attestation.strip()
    if not attestation:
        raise SystemExit("--entitlement-attestation must be non-empty")

    # DTD-05: pre-invocation git gate
    git_head = _git_head(ROOT)
    if not git_head:
        raise SystemExit(
            "cannot resolve git HEAD; live drafting evidence requires a reviewed commit"
        )
    git_ref = _git_ref(ROOT)
    worktree_clean = _worktree_clean(ROOT)
    if worktree_clean is not True:
        raise SystemExit(
            "tracked worktree is dirty or git is unavailable; live drafting "
            "evidence requires a clean checkout of the reviewed tip"
        )

    # DTD-01: credential + route resolution with ambiguity refusal
    api_key = require_zai_api_key()
    base_url, base_url_source = resolve_route(args.base_url, args.zai_endpoint)

    fixture = load_fixture(args.fixture)
    terminology_payload = json.loads(DEFAULT_TERMINOLOGY.read_text(encoding="utf-8"))
    terminology = load_terminology(terminology_payload)
    created_at = _utc_now()
    context = build_drafting_context_from_fixture(fixture, terminology, created_at)
    rendered_prompt, _delivery_json = prepare_draft_input(context, terminology)

    # DTD-02: refuse overwrite before any invocation
    _refuse_overwrite(args.output, args.output.with_name(args.output.name + ".sha256"))

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

    raw_output_holder: list[str] = []

    def capturing_invoke(prompt: str) -> str:
        result = invoke(prompt)
        raw_output_holder.append(result)
        return result

    started = time.monotonic()
    draft_run: dict | None = None
    execution_error: str | None = None
    try:
        draft_run = build_bilingual_draft_run(
            context=context,
            terminology=terminology,
            model_trace=trace,
            invoke=capturing_invoke,
        )
    except (BilingualDraftingError, RuntimeError, Exception) as exc:  # noqa: BLE001
        execution_error = str(exc)[:512]
    elapsed = time.monotonic() - started

    raw_output = raw_output_holder[0] if raw_output_holder else None

    report = build_trial_report(
        fixture=fixture,
        terminology_payload=terminology_payload,
        context=context,
        rendered_prompt=rendered_prompt,
        raw_model_output=raw_output,
        draft_run=draft_run,
        execution_error=execution_error,
        requested_model=args.model,
        base_url=base_url,
        base_url_source=base_url_source,
        endpoint_arg=args.zai_endpoint,
        entitlement_attestation=attestation,
        git_head=git_head,
        git_ref=git_ref,
        worktree_clean=worktree_clean,
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
