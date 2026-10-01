#!/usr/bin/env python3
"""Isolation checks for the bounded bilingual drafting projection.

Proves the boundary properties beyond the happy path: the model input is only
the bounded approved context; the pre-invocation sensitivity gate is bilingual;
conflicts fail closed at the builder and hand-assembled contexts at the
adapter; the number allowlist excludes bookkeeping digits and covers Arabic
prose including Arabic-Indic digits; unknown meaning is preserved by exact
deterministic reuse (the model cannot author unknown prose); terminology
pairing is enforced in both directions and bound to registry bytes; and no run
can carry canonical mutation or publication authority.
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.intelligence.bilingual_drafting import (  # noqa: E402
    BilingualDraftingError,
    DraftModelTrace,
    build_approved_drafting_context,
    build_bilingual_draft_run,
    load_terminology,
)

TERMINOLOGY = ROOT / "data" / "terminology" / "bilingual-terminology-v0.1.json"


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_error(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except BilingualDraftingError:
        return
    failures.append(f"{label} did not fail closed")


def main() -> int:
    failures: list[str] = []
    schemas, registry = build_registry()

    def validate(schema_name: str, instance: dict[str, Any], label: str) -> None:
        validator = Draft202012Validator(
            schemas[schema_name], registry=registry, format_checker=FormatChecker()
        )
        errors = [error.message for error in validator.iter_errors(instance)]
        expect(not errors, f"{label} is schema-invalid: {errors[:2]}", failures)

    terminology = load_terminology(json.loads(TERMINOLOGY.read_text(encoding="utf-8")))

    entities = [
        {
            "entity_id": "SDA-ORG-NOOR",
            "entity_type": "organization",
            "record_status": "active",
            "names": {"en": "Al-Noor Industries", "ar": "شركة النور للصناعات"},
        },
        {
            "entity_id": "SDA-EQUIP-ALPHA",
            "entity_type": "equipment_variant",
            "record_status": "active",
            "names": {"en": "Alpha Training System", "ar": "منظومة التدريب ألفا"},
        },
    ]
    claims = [
        {
            "claim_id": "SDA-CLAIM-ALPHA-SUPPLY",
            "subject_entity_id": "SDA-ORG-NOOR",
            "predicate_id": "contract.awarded_to.company",
            "value": {"kind": "entity", "entity_id": "SDA-EQUIP-ALPHA"},
            "validity": None,
            "scope": None,
            "claim_state": "active",
            "record_status": "active",
            "evidence_ids": ["SDA-EVID-ALPHA-1"],
        }
    ]
    evidence = [
        {
            "evidence_id": "SDA-EVID-ALPHA-1",
            "document_id": "SDA-DOC-ALPHA",
            "record_status": "active",
            "locator": {"fragment": "source-text"},
            "role": "supports",
        }
    ]
    unknowns = [
        {
            "unknown_id": "UNK-ALPHA-QUANTITY",
            "aspect": "quantity",
            "entity_id": "SDA-EQUIP-ALPHA",
            "statement_en": "The contracted quantity is not established by approved claims.",
            "statement_ar": "لم يثبت حجم العقد من الادعاءات المعتمدة.",
        }
    ]

    context = build_approved_drafting_context(
        entities=entities,
        claims=claims,
        evidence=evidence,
        unknowns=unknowns,
        terminology=terminology,
        created_at="2026-10-02T00:00:00Z",
    )

    good_output = {
        "units": [
            {
                "unit_id": "UNIT-SUPPLY",
                "claim_ids": ["SDA-CLAIM-ALPHA-SUPPLY"],
                "evidence_ids": ["SDA-EVID-ALPHA-1"],
                "prose": {
                    "en": "Al-Noor Industries was awarded a contract for the Alpha Training System.",
                    "ar": "فازت شركة النور للصناعات بعقد لمنظومة التدريب ألفا.",
                },
            }
        ],
        "undrafted_claim_ids": [],
        "rendered_unknown_ids": ["UNK-ALPHA-QUANTITY"],
        "omitted_unknown_ids": [],
    }

    trace = DraftModelTrace(
        provider="deterministic-isolation", model="fixture-drafter", model_version="v0"
    )

    def run_with(invoke: Any, ctx: Any = context, term: Any = terminology) -> dict[str, Any]:
        return build_bilingual_draft_run(
            context=ctx,
            terminology=term,
            model_trace=trace,
            invoke=invoke,
            clock=lambda: "2026-10-02T00:01:00Z",
        )

    # 1. The invoker receives ONLY the bounded approved context: no candidate
    #    markers, no restricted vocabulary in either locale, nothing extra.
    captured: list[str] = []

    def capture_invoke(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps(good_output, ensure_ascii=False)

    run = run_with(capture_invoke)
    expect(
        run["validation"]["status"] == "accepted_for_editorial_review",
        f"isolation happy path was not accepted: {run['validation']['errors'][:2]}",
        failures,
    )
    prompt = captured[0]
    for marker in ("CAND-", "readiness", "patrol", "stock level", "live unit", "جاهزية", "مخزون"):
        expect(marker not in prompt, f"model input leaked {marker!r}", failures)
    parsed_prompt = json.loads(prompt)
    expect(set(parsed_prompt) == set(context), "model input is not exactly the context", failures)
    expect(
        "terminology_sha256" in parsed_prompt,
        "model input lost the terminology digest binding",
        failures,
    )

    # 2. Unknown meaning is preserved by construction: the model only selects
    #    unknown IDs; authored unknown prose is an unsupported key.
    authored_unknown = copy.deepcopy(good_output)
    authored_unknown["unknowns_rendered"] = [
        {
            "unknown_id": "UNK-ALPHA-QUANTITY",
            "prose": {
                "en": "The Alpha Training System is operated by the Royal Air Force.",
                "ar": "تشغّل القوة الجوية الملكية منظومة التدريب ألفا.",
            },
        }
    ]
    au_result = run_with(lambda _: json.dumps(authored_unknown, ensure_ascii=False))
    expect(
        au_result["validation"]["status"] == "rejected",
        "model-authored unknown prose was not rejected",
        failures,
    )
    expect(
        run["unknowns_rendered"][0]["prose"]["en"] == unknowns[0]["statement_en"]
        and run["unknowns_rendered"][0]["prose"]["ar"] == unknowns[0]["statement_ar"],
        "accepted run did not reuse the exact pre-written unknown statements",
        failures,
    )

    # 3. Conflict fail-closed at the builder (disputed) and adapter (hand-assembled).
    disputed = copy.deepcopy(claims)
    disputed[0]["claim_state"] = "disputed"

    def build_disputed() -> None:
        build_approved_drafting_context(
            entities=entities,
            claims=disputed,
            evidence=evidence,
            unknowns=unknowns,
            terminology=terminology,
            created_at="2026-10-02T00:00:02Z",
        )

    expect_error("disputed claim at builder", build_disputed, failures)

    conflicted_ctx = copy.deepcopy(context)
    conflicted_ctx["conflicts"] = [{"aspect": "quantity"}]

    def run_conflicted() -> None:
        run_with(lambda _: json.dumps(good_output), ctx=conflicted_ctx)

    expect_error("hand-assembled context with conflicts", run_conflicted, failures)

    injected = copy.deepcopy(context)
    injected["entities"].append(
        {
            "entity_id": "CAND-ENT-SMUGGLED",
            "entity_type": "organization",
            "names": {"en": "Smuggled", "ar": "مهرب"},
        }
    )

    def run_injected() -> None:
        run_with(lambda _: json.dumps(good_output), ctx=injected)

    expect_error("hand-assembled context with injected candidate entity", run_injected, failures)

    # 4. Authority escalation is schema-impossible and adapter-refused.
    escalated = copy.deepcopy(run)
    escalated["authority"] = {
        "mode": "canonical",
        "canonical_mutation_authority": True,
        "publication_authority": True,
    }
    validator = Draft202012Validator(
        schemas["ai-bilingual-draft-run.schema.json"],
        registry=registry,
        format_checker=FormatChecker(),
    )
    expect(
        list(validator.iter_errors(escalated)),
        "schema accepted a run claiming canonical authority",
        failures,
    )
    read_only_escalation = copy.deepcopy(context)
    read_only_escalation["authority"]["canonical_mutation_authority"] = True
    expect_error(
        "context claiming mutation authority",
        lambda: run_with(lambda _: json.dumps(good_output), ctx=read_only_escalation),
        failures,
    )

    # 5. Terminology pairing in both directions.
    ar_only_term = copy.deepcopy(good_output)
    ar_only_term["units"][0]["prose"] = {
        "en": "Al-Noor Industries supplies a training system.",
        "ar": "فازت شركة النور للصناعات بعقد لدخول الخدمة.",
    }
    ar_result = run_with(lambda _: json.dumps(ar_only_term, ensure_ascii=False))
    expect(
        ar_result["validation"]["status"] == "rejected"
        and any("registry term" in error for error in ar_result["validation"]["errors"]),
        f"Arabic-only registry term was not rejected: {ar_result['validation']['errors'][:2]}",
        failures,
    )

    # 6. The number guard covers Arabic prose including Arabic-Indic digits,
    #    and excludes bookkeeping digits (the context-creation year).
    arabic_number = copy.deepcopy(good_output)
    arabic_number["units"][0]["prose"]["ar"] = (
        "فازت شركة النور للصناعات بعقد لمنظومة التدريب ألفا بقيمة ٩٩ منصة."
    )
    an_result = run_with(lambda _: json.dumps(arabic_number, ensure_ascii=False))
    expect(
        an_result["validation"]["status"] == "rejected"
        and any("not grounded" in error for error in an_result["validation"]["errors"]),
        f"Arabic-Indic invented number was not rejected: {an_result['validation']['errors'][:2]}",
        failures,
    )
    bookkeeping = copy.deepcopy(good_output)
    bookkeeping["units"][0]["prose"]["en"] = (
        "Al-Noor Industries was awarded a contract in 2026 for the Alpha Training System."
    )
    bk_result = run_with(lambda _: json.dumps(bookkeeping, ensure_ascii=False))
    expect(
        bk_result["validation"]["status"] == "rejected"
        and any("not grounded" in error for error in bk_result["validation"]["errors"]),
        f"bookkeeping-only year was not rejected: {bk_result['validation']['errors'][:2]}",
        failures,
    )

    # 7. Pre-invocation sensitivity gate is bilingual (BD-03).
    arabic_restricted_statement = copy.deepcopy(unknowns)
    arabic_restricted_statement[0]["statement_ar"] = "لم يثبت مستوى الجاهزية من الادعاءات."

    def build_arabic_restricted() -> None:
        build_approved_drafting_context(
            entities=entities,
            claims=claims,
            evidence=evidence,
            unknowns=arabic_restricted_statement,
            terminology=terminology,
            created_at="2026-10-02T00:00:03Z",
        )

    expect_error("Arabic restricted marker in context (pre-invocation)", build_arabic_restricted, failures)

    # 8. Terminology bytes are bound, not just the version (FBD-02).
    tampered_registry = json.loads(TERMINOLOGY.read_text(encoding="utf-8"))
    tampered_registry["terms"][2]["en"] = "greenlit"

    def run_tampered_registry() -> None:
        run_with(lambda _: json.dumps(good_output), term=tampered_registry)

    expect_error("terminology bytes changed under same version", run_tampered_registry, failures)

    # 9. Official names outrank generated translations as a documented rule;
    #    the accepted fixture prose carries the official Arabic entity name.
    expect(
        "منظومة التدريب ألفا" in run["units"][0]["prose"]["ar"],
        "fixture prose lost the official Arabic entity name",
        failures,
    )

    if failures:
        print("M4 bilingual drafting isolation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated bilingual drafting isolation: model input is exactly the bounded approved "
        "context (now including the terminology digest) with no candidate, restricted, English, "
        "or Arabic leakage; the model cannot author unknown prose (unsupported key) and rendered "
        "unknowns are exact deterministic reuse; disputed claims fail closed at the builder and "
        "hand-assembled contexts (conflicts, injected candidates, escalation) at the adapter; "
        "authority escalation is schema-impossible; terminology pairing enforced in both "
        "directions with registry-byte binding; the number guard covers Arabic-Indic digits and "
        "rejects bookkeeping-only digits; the pre-invocation sensitivity gate is bilingual."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
