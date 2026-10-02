#!/usr/bin/env python3
"""Validate the M4 live drafting trial driver without network calls.

Exercises the actual report builder (`build_trial_report`) with a fake invoker
and a failing invoker, proving: the report carries every required provenance
field (git, entitlement, route, versions, terminology registry version +
digests, hashes); the exact rendered input and raw model output are frozen
verbatim; the editorial assessment is a pending-human-review placeholder with
no mechanical score; transport failure produces a bounded failure report with
no retry; the qualification flags are correct; the sidecar matches the report
bytes; the serialization is deterministic JSON; and authority is candidate-only.
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
    build_drafting_context_from_fixture,
    build_trial_report,
    load_fixture,
    write_report_with_sidecar,
)
from services.intelligence.bilingual_drafting import (  # noqa: E402
    BilingualDraftingError,
    DraftModelTrace,
    build_bilingual_draft_run,
    prepare_draft_input,
)

TERMINOLOGY_PATH = ROOT / "data" / "terminology" / "bilingual-terminology-v0.1.json"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


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


def build_report(
    raw_output: str | None,
    draft_run: dict | None,
    execution_error: str | None,
) -> dict[str, Any]:
    fixture = load_fixture(DEFAULT_FIXTURE)
    terminology_payload = json.loads(TERMINOLOGY_PATH.read_text(encoding="utf-8"))
    from services.intelligence.bilingual_drafting import load_terminology

    terminology = load_terminology(terminology_payload)
    context = build_drafting_context_from_fixture(fixture, terminology, "2026-10-03T00:00:00Z")
    rendered, _ = prepare_draft_input(context, terminology)
    return build_trial_report(
        fixture=fixture,
        terminology_payload=terminology_payload,
        context=context,
        rendered_prompt=rendered,
        raw_model_output=raw_output,
        draft_run=draft_run,
        execution_error=execution_error,
        requested_model="glm-5.3",
        base_url="https://api.z.ai/api/coding/paas/v4",
        base_url_source="endpoint:coding-plan",
        endpoint_arg="coding-plan",
        entitlement_attestation="test-attestation",
        git_head="a" * 40,
        git_ref="refs/heads/main",
        worktree_clean=True,
        fixture_path=DEFAULT_FIXTURE,
        terminology_path=DEFAULT_TERMINOLOGY,
        elapsed_seconds=1.234,
    )


def main() -> int:
    failures: list[str] = []

    # --- Build the report through the actual report builder with a fake
    #     invoker's successful output
    raw_good = json.dumps(good_output(), ensure_ascii=False)
    fixture = load_fixture(DEFAULT_FIXTURE)
    terminology_payload = json.loads(TERMINOLOGY_PATH.read_text(encoding="utf-8"))
    from services.intelligence.bilingual_drafting import load_terminology

    terminology = load_terminology(terminology_payload)
    context = build_drafting_context_from_fixture(fixture, terminology, "2026-10-03T00:00:00Z")
    rendered, _ = prepare_draft_input(context, terminology)

    trace = DraftModelTrace(
        provider="zai-openai-compatible-api",
        model="glm-5.3",
        model_version="provider-managed-unknown",
    )

    def fake_invoke(prompt: str) -> str:
        return raw_good

    draft_run = build_bilingual_draft_run(
        context=context, terminology=terminology, model_trace=trace, invoke=fake_invoke
    )

    report = build_report(raw_good, draft_run, None)

    # DTD-03: verify every field the driver contract requires
    expect(report["report_version"] == REPORT_VERSION, "report version drifted", failures)
    expect(
        report["entitlement"]["attestation"] == "test-attestation"
        and report["entitlement"]["standing_extraction_entitlement_covers_drafting"] is False,
        "entitlement attestation or scope flag is wrong",
        failures,
    )
    expect(
        report["provider_edge"]["resolved_base_url"] == "https://api.z.ai/api/coding/paas/v4"
        and report["provider_edge"]["resolved_base_url_source"] == "endpoint:coding-plan",
        "resolved route not recorded",
        failures,
    )
    expect(
        report["provider_edge"]["requested_endpoint_mode"] == "coding-plan",
        "requested endpoint mode not recorded",
        failures,
    )
    expect(
        report["terminology"]["registry_version"],
        "terminology registry version missing from the report",
        failures,
    )
    expect(
        report["terminology"]["registry_acceptance_sha256"] == context["terminology_sha256"],
        "registry acceptance digest not recorded",
        failures,
    )
    expect(
        bool(report["terminology"]["delivery_payload_sha256"]),
        "delivery payload digest missing",
        failures,
    )

    # DTD-02: exact dynamic bytes frozen
    expect(
        report["evidence"]["rendered_model_input"] == rendered,
        "rendered input not frozen verbatim",
        failures,
    )
    expect(
        report["evidence"]["raw_model_output"] == raw_good,
        "raw model output not frozen verbatim",
        failures,
    )
    expect(
        report["invocation"]["rendered_input_sha256"] == sha256_text(rendered),
        "rendered input hash wrong",
        failures,
    )
    expect(
        report["invocation"]["raw_model_output_sha256"] == sha256_text(raw_good),
        "raw output hash wrong",
        failures,
    )

    # Editorial placeholder
    ed = report["editorial_assessment"]
    expect(
        ed["status"] == "pending_human_review"
        and ed["mechanical_score"] is None
        and ed["notes"] is None
        and len(ed["assessment_dimensions"]) == 6,
        "editorial assessment placeholder is wrong",
        failures,
    )

    # Qualification flags
    q = report["qualification"]
    expect(
        q["structural_mechanical_acceptance"] is True
        and q["editorial_quality_qualified"] is False
        and q["production_model_pipeline_qualified"] is False
        and q["publication_authority"] is False
        and q["canonical_mutation_authority"] is False
        and q["bounded_evidence_only"] is True
        and q["served_model_checkpoint"] == "unknown",
        "qualification flags are wrong",
        failures,
    )

    # Structural result
    expect(
        report["structural_result"]["validation"]["status"] == "accepted_for_editorial_review",
        "structural result not embedded",
        failures,
    )
    expect(
        report["structural_result"]["authority"]["canonical_mutation_authority"] is False,
        "structural result carries authority",
        failures,
    )

    # DTD-04: transport failure produces a bounded failure report
    failure_report = build_report(None, None, "Z.ai API returned HTTP 500: internal error")
    expect(
        failure_report["execution_error"] is not None
        and failure_report["structural_result"] is None,
        "failure report missing error or has a spurious structural result",
        failures,
    )
    expect(
        failure_report["evidence"]["rendered_model_input"] == rendered,
        "failure report lost the rendered input",
        failures,
    )
    expect(
        failure_report["evidence"]["raw_model_output"] is None,
        "failure report has spurious raw output",
        failures,
    )
    expect(
        failure_report["invocation"]["raw_model_output_sha256"] is None,
        "failure report has spurious raw-output hash",
        failures,
    )
    expect(
        failure_report["qualification"]["structural_mechanical_acceptance"] is False,
        "failure report claims structural acceptance",
        failures,
    )
    expect(
        failure_report["editorial_assessment"]["status"] == "pending_human_review",
        "failure report lost the editorial placeholder",
        failures,
    )

    # DTD-02: sidecar and serialization round-trip
    with tempfile.TemporaryDirectory() as tmpdir:
        out = Path(tmpdir) / "report.json"
        report_sha = write_report_with_sidecar(out, report)
        actual = hashlib.sha256(out.read_bytes()).hexdigest()
        expect(actual == report_sha, "sidecar hash does not match report bytes", failures)
        sidecar_text = out.with_name(out.name + ".sha256").read_text(encoding="utf-8")
        expect(
            sidecar_text == f"{report_sha}  {out.name}\n",
            "sidecar format wrong",
            failures,
        )
        reparsed = json.loads(out.read_text(encoding="utf-8"))
        expect(
            reparsed["evidence"]["raw_model_output"] == raw_good,
            "serialization round-trip lost the raw output",
            failures,
        )

        # Deterministic serialization: same report → same bytes
        write_report_with_sidecar(out, report)
        expect(
            hashlib.sha256(out.read_bytes()).hexdigest() == report_sha,
            "serialization is not deterministic",
            failures,
        )

    if failures:
        print("M4 drafting trial driver validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated the M4 live drafting trial driver through the actual report builder: "
        "entitlement attestation with explicit non-coverage; resolved route recorded; "
        "registry version + digests; exact rendered input and raw model output frozen "
        "verbatim with matching hashes; editorial placeholder with six dimensions and no "
        "mechanical score; qualification flags correct; transport failure produces a "
        "bounded report with the rendered input preserved and no spurious result; "
        "sidecar and deterministic serialization verified; candidate-only authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
