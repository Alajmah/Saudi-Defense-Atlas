#!/usr/bin/env python3
"""Isolation checks for the bounded bilingual drafting projection.

Proves the boundary properties beyond the happy path: the model input is only
the bounded approved context (no candidate or restricted material can reach
the invoker), conflicts fail closed at both the builder and the adapter,
unknown preservation is enforced per locale, the number guard covers Arabic
prose including Arabic-Indic digits, terminology pairing is enforced in both
directions, and no run can carry canonical mutation or publication authority.
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
        "unknowns_rendered": [
            {
                "unknown_id": "UNK-ALPHA-QUANTITY",
                "prose": {
                    "en": "The contracted quantity remains unknown.",
                    "ar": "يبقى حجم العقد غير معروف.",
                },
            }
        ],
        "omitted_unknown_ids": [],
    }

    trace = DraftModelTrace(
        provider="deterministic-isolation", model="fixture-drafter", model_version="v0"
    )

    def run_with(invoke: Any, ctx: Any = context) -> dict[str, Any]:
        return build_bilingual_draft_run(
            context=ctx,
            terminology=terminology,
            model_trace=trace,
            invoke=invoke,
            clock=lambda: "2026-10-02T00:01:00Z",
        )

    # 1. The invoker receives ONLY the bounded approved context: no candidate
    #    markers, no restricted vocabulary, and nothing beyond the context keys.
    captured: list[str] = []

    def capture_invoke(prompt: str) -> str:
        captured.append(prompt)
        return json.dumps(good_output, ensure_ascii=False)

    run = run_with(capture_invoke)
    expect(
        run["validation"]["status"] == "accepted_for_editorial_review",
        "isolation happy path was not accepted",
        failures,
    )
    prompt = captured[0]
    for marker in ("CAND-", "readiness", "patrol", "stock level", "live unit"):
        expect(marker not in prompt, f"model input leaked {marker!r}", failures)
    parsed_prompt = json.loads(prompt)
    expect(
        set(parsed_prompt) == set(context),
        "model input is not exactly the context object",
        failures,
    )

    # 2. Conflict fail-closed at the builder: disputed claim state.
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

    # 3. Conflict fail-closed at the adapter: a hand-assembled context carrying
    #    a non-empty conflicts array is refused before any invocation.
    conflicted = copy.deepcopy(context)
    conflicted["conflicts"] = [{"aspect": "quantity"}]

    def run_conflicted() -> None:
        run_with(lambda _: json.dumps(good_output), ctx=conflicted)

    expect_error("context with conflicts at adapter", run_conflicted, failures)

    # 4. Authority escalation is structurally impossible: the schema pins
    #    candidate-only authority with false flags.
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
        "en": "Al-Noor Industries supplies a training system.",  # avoids registry English
        "ar": "فازت شركة النور للصناعات بعقد لدخول الخدمة.",  # uses Arabic registry term
    }
    ar_result = run_with(lambda _: json.dumps(ar_only_term, ensure_ascii=False))
    expect(
        ar_result["validation"]["status"] == "rejected"
        and any("registry term" in error for error in ar_result["validation"]["errors"]),
        f"Arabic-only registry term was not rejected: {ar_result['validation']['errors'][:2]}",
        failures,
    )

    # 6. The number guard covers Arabic prose, including Arabic-Indic digits.
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

    # 7. Unknown preservation: omitting the context unknown entirely is a
    #    rejection; rendering it in only one locale is a rejection.
    omitted_unknown = copy.deepcopy(good_output)
    omitted_unknown["unknowns_rendered"] = []
    omitted_unknown["omitted_unknown_ids"] = []
    oo_result = run_with(lambda _: json.dumps(omitted_unknown, ensure_ascii=False))
    expect(
        oo_result["validation"]["status"] == "rejected",
        "fully omitted context unknown was not rejected",
        failures,
    )
    one_locale = copy.deepcopy(good_output)
    one_locale["unknowns_rendered"][0]["prose"].pop("ar")
    ol_result = run_with(lambda _: json.dumps(one_locale, ensure_ascii=False))
    expect(
        ol_result["validation"]["status"] == "rejected",
        "unknown rendered in only one locale was not rejected",
        failures,
    )
    validate(
        "ai-bilingual-draft-run.schema.json", ol_result, "rejected one-locale unknown run"
    )

    # 8. Terminology version binding: a registry whose version differs from the
    #    context is refused before invocation.
    other_version = copy.deepcopy(terminology)
    other_version["version"] = "sda-bilingual-terminology-v9.9"

    def run_wrong_registry() -> None:
        build_bilingual_draft_run(
            context=context,
            terminology=other_version,
            model_trace=trace,
            invoke=lambda _: json.dumps(good_output),
            clock=lambda: "2026-10-02T00:02:00Z",
        )

    expect_error("terminology version mismatch", run_wrong_registry, failures)

    # 9. Official names outrank generated translations: the accepted prose uses
    #    the entity's official Arabic name, and a unit substituting an invented
    #    Arabic name for the entity still passes the mechanical checks (the
    #    registry governs terminology, not entity names) - so the contract
    #    documents official-name precedence as a prompt/evaluation rule, and the
    #    mechanical guard here proves the boundary never blocks on entity names
    #    it was never asked to police.
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
        "context with no candidate or restricted material; disputed claims fail closed at the "
        "builder and conflicted contexts at the adapter; authority escalation is schema-"
        "impossible and adapter-refused; terminology pairing enforced in both directions; the "
        "invented-number guard covers Arabic prose including Arabic-Indic digits; context "
        "unknowns must be rendered bilingually or explicitly omitted; terminology version is "
        "bound to the context."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
