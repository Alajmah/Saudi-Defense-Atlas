#!/usr/bin/env python3
"""Run the bounded M4 live bilingual drafting trial through the Z.ai provider edge.

Loads an approved canonical drafting fixture, renders the reviewed v0.2
two-block model input through the deterministic drafting boundary, sends it to
Z.ai's OpenAI-compatible API, and captures the resulting ``AI bilingual draft
run`` with full hash provenance. Mechanical/structural acceptance and human
editorial assessment are reported as independent dimensions; this runner scores
only the former and records the latter as a pending-human-review placeholder.

The runner does not read or write the canonical knowledge backend and does not
publish anything.
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
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_m4_model_extraction_trial import (  # noqa: E402
    _file_sha256,
    require_zai_api_key,
    resolve_zai_base_url,
    validate_zai_base_url,
    zai_invoker,
)
from services.intelligence.bilingual_drafting import (  # noqa: E402
    ADAPTER_VERSION as DRAFTING_ADAPTER_VERSION,
    DRAFT_PROMPT_TEMPLATE_ID,
    DRAFT_PROMPT_TEMPLATE_VERSION,
    DraftModelTrace,
    build_approved_drafting_context,
    build_bilingual_draft_run,
    draft_prompt_template_sha256,
    load_terminology,
    prepare_draft_input,
)
from services.intelligence.model_extraction_trial import (  # noqa: E402
    ADAPTER_VERSION as EXTRACTION_ADAPTER_VERSION,
)

DEFAULT_FIXTURE = ROOT / "tests" / "fixtures" / "m4-drafting-trial-v0.1.json"
DEFAULT_TERMINOLOGY = ROOT / "data" / "terminology" / "bilingual-terminology-v0.1.json"

REPORT_VERSION = "m4-drafting-live-trial-v0.1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    parser.add_argument(
        "--provider",
        choices=("zai",),
        default="zai",
        help="trial provider edge (default: zai)",
    )
    parser.add_argument(
        "--model",
        default="glm-5.3",
        help="requested model (default: glm-5.3)",
    )
    parser.add_argument("--zai-endpoint", choices=("coding-plan", "prepaid"), default=None)
    parser.add_argument("--base-url", default=None)
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


def main() -> int:
    args = parse_args()
    if args.timeout_seconds < 1:
        raise SystemExit("--timeout-seconds must be positive")
    if args.base_url is not None and args.zai_endpoint is not None:
        raise SystemExit("pass either --base-url or --zai-endpoint, not both")

    api_key = require_zai_api_key()
    base_url, base_url_source = resolve_zai_base_url(args.base_url, args.zai_endpoint)
    validate_zai_base_url(base_url)

    fixture = load_fixture(args.fixture)
    terminology = load_terminology(
        json.loads(DEFAULT_TERMINOLOGY.read_text(encoding="utf-8"))
    )
    created_at = _utc_now()
    context = build_drafting_context_from_fixture(fixture, terminology, created_at)

    rendered_prompt, delivery_json = prepare_draft_input(context, terminology)
    rendered_sha = hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest()

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

    started = time.monotonic()
    draft_run = build_bilingual_draft_run(
        context=context,
        terminology=terminology,
        model_trace=trace,
        invoke=invoke,
    )
    elapsed = time.monotonic() - started

    structural_accepted = draft_run["validation"]["status"] == "accepted_for_editorial_review"

    report = {
        "report_version": REPORT_VERSION,
        "fixture_version": fixture["version"],
        "provider": "zai-openai-compatible-api",
        "requested_model": args.model,
        "provider_checkpoint_version": None,
        "provider_edge": {
            "driver": "zai-openai-compatible-http",
            "base_url": base_url,
            "base_url_source": base_url_source,
            "endpoint_mode": args.zai_endpoint,
            "credential_source": "ZAI_API_KEY environment variable",
            "transport": "python-stdlib-urllib",
            "tools": "none",
            "reasoning_configuration": {
                "thinking_type": "enabled",
                "reasoning_effort": "max",
                "explicitly_pinned": True,
            },
        },
        "drafting_boundary_versions": {
            "drafting_adapter": DRAFTING_ADAPTER_VERSION,
            "extraction_adapter_at_build": EXTRACTION_ADAPTER_VERSION,
            "prompt_template_id": DRAFT_PROMPT_TEMPLATE_ID,
            "prompt_template_version": DRAFT_PROMPT_TEMPLATE_VERSION,
            "prompt_template_sha256": draft_prompt_template_sha256(),
        },
        "trial_context": {
            "git_head": _git_head(ROOT),
            "git_ref": _git_ref(ROOT),
            "tracked_worktree_clean": _worktree_clean(ROOT),
            "python_version": platform.python_version(),
            "fixture_sha256": _file_sha256(args.fixture),
            "terminology_file_sha256": _file_sha256(DEFAULT_TERMINOLOGY),
        },
        "invocation": {
            "rendered_input_sha256": rendered_sha,
            "delivery_payload_sha256": hashlib.sha256(
                delivery_json.encode("utf-8")
            ).hexdigest(),
            "elapsed_seconds": round(elapsed, 3),
        },
        "structural_result": draft_run,
        "editorial_assessment": {
            "status": "pending_human_review",
            "mechanical_score": None,
            "notes": None,
            "assessment_dimensions": [
                "Arabic fluency",
                "English fluency",
                "factual faithfulness of phrasing",
                "bilingual adequacy",
                "terminology quality",
                "awkward or misleading wording",
            ],
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    report_bytes = (
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    args.output.write_bytes(report_bytes)
    report_sha = hashlib.sha256(args.output.read_bytes()).hexdigest()
    sidecar = args.output.with_name(args.output.name + ".sha256")
    sidecar.write_bytes(f"{report_sha}  {args.output.name}\n".encode("utf-8"))

    print(
        json.dumps(
            {
                "structural_status": draft_run["validation"]["status"],
                "units": len(draft_run["units"]),
                "undrafted_claims": len(draft_run["undrafted_claim_ids"]),
                "unknowns_rendered": len(draft_run["unknowns_rendered"]),
                "elapsed_seconds": round(elapsed, 3),
                "report_sha256": report_sha,
                "output": str(args.output),
            },
            sort_keys=True,
            allow_nan=False,
        )
    )
    return 0


def _git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_ref(root: Path) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _worktree_clean(root: Path) -> bool | None:
    result = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        return None
    return not result.stdout.strip()


if __name__ == "__main__":
    raise SystemExit(main())
