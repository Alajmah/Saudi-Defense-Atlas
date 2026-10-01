#!/usr/bin/env python3
"""Validate the bounded bilingual drafting projection without model calls."""

from __future__ import annotations

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
    ADAPTER_VERSION,
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


def sha256_of(value: Any) -> str:
    import hashlib

    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def entity(entity_id: str, entity_type: str, en: str, ar: str) -> dict[str, Any]:
    return {
        "entity_id": entity_id,
        "entity_type": entity_type,
        "record_status": "active",
        "names": {"en": en, "ar": ar},
    }


def canonical_inputs() -> tuple[list, list, list, list]:
    entities = [
        entity("SDA-ORG-ATLAS", "organization", "Atlas Aerospace", "أطلس للصناعات الجوية"),
        entity("SDA-EQUIP-FALCONX", "equipment_variant", "Falcon-X", "فالكون-إكس"),
        entity("SDA-PROC-CEDAR", "procurement_program", "Project Cedar", "مشروع الأرز"),
    ]
    claims = [
        {
            "claim_id": "SDA-CLAIM-CEDAR-QTY",
            "subject_entity_id": "SDA-PROC-CEDAR",
            "predicate_id": "procurement.quantity",
            "value": {
                "kind": "number",
                "value": 12,
                "unit": "aircraft",
                "precision": "exact",
                "lower_bound": None,
                "upper_bound": None,
            },
            "validity": {"point_in_time": {"value": "2024-03-15", "precision": "day"}},
            "claim_state": "active",
            "record_status": "active",
            "evidence_ids": ["SDA-EVID-CEDAR-1"],
        },
        {
            "claim_id": "SDA-CLAIM-FALCONX-MANUFACTURER",
            "subject_entity_id": "SDA-ORG-ATLAS",
            "predicate_id": "manufacturer.manufactures.equipment",
            "value": {"kind": "entity", "entity_id": "SDA-EQUIP-FALCONX"},
            "validity": None,
            "claim_state": "active",
            "record_status": "active",
            "evidence_ids": ["SDA-EVID-FALCONX-1"],
        },
    ]
    evidence = [
        {
            "evidence_id": "SDA-EVID-CEDAR-1",
            "document_id": "SDA-DOC-CEDAR",
            "record_status": "active",
            "locator": {"fragment": "source-text"},
            "role": "supports",
        },
        {
            "evidence_id": "SDA-EVID-FALCONX-1",
            "document_id": "SDA-DOC-FALCONX",
            "record_status": "active",
            "locator": {"fragment": "source-text"},
            "role": "supports",
        },
    ]
    unknowns = [
        {
            "unknown_id": "UNK-FALCONX-OPERATOR",
            "aspect": "operator",
            "entity_id": "SDA-EQUIP-FALCONX",
            "statement_en": "The operator of Falcon-X is not established by approved claims.",
            "statement_ar": "لم يثبت المشغّل لمنظومة فالكون-إكس من الادعاءات المعتمدة.",
        }
    ]
    return entities, claims, evidence, unknowns


def good_draft_output() -> dict[str, Any]:
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
        "unknowns_rendered": [
            {
                "unknown_id": "UNK-FALCONX-OPERATOR",
                "prose": {
                    "en": "The operator of Falcon-X remains unknown.",
                    "ar": "يبقى مشغّل فالكون-إكس غير معروف.",
                },
            }
        ],
        "omitted_unknown_ids": [],
    }


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
    entities, claims, evidence, unknowns = canonical_inputs()

    # --- context construction ---
    context = build_approved_drafting_context(
        entities=entities,
        claims=claims,
        evidence=evidence,
        unknowns=unknowns,
        terminology=terminology,
        created_at="2026-10-02T00:00:00Z",
    )
    validate("editorial-drafting-context.schema.json", context, "drafting context")
    expect(
        context["authority"]
        == {
            "mode": "approved_canonical_read_only",
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "context carries wrong authority",
        failures,
    )
    expect(context["conflicts"] == [], "accepted context carries conflicts", failures)
    rebuilt = build_approved_drafting_context(
        entities=entities,
        claims=claims,
        evidence=evidence,
        unknowns=unknowns,
        terminology=terminology,
        created_at="2026-10-02T00:00:00Z",
    )
    expect(rebuilt["id"] == context["id"], "context identity is not deterministic", failures)

    # --- builder fail-closed matrix ---
    import copy

    def build(**overrides: Any) -> None:
        build_approved_drafting_context(
            entities=overrides.get("entities", entities),
            claims=overrides.get("claims", claims),
            evidence=overrides.get("evidence", evidence),
            unknowns=overrides.get("unknowns", unknowns),
            terminology=overrides.get("terminology", terminology),
            created_at="2026-10-02T00:00:01Z",
        )

    candidate_claim = copy.deepcopy(claims)
    candidate_claim[0]["claim_id"] = "CAND-CLAIM-1"
    expect_error("candidate claim", lambda: build(claims=candidate_claim), failures)

    unapproved = copy.deepcopy(claims)
    unapproved[0]["claim_state"] = "disputed"
    expect_error("disputed claim", lambda: build(claims=unapproved), failures)

    inactive = copy.deepcopy(claims)
    inactive[0]["record_status"] = "superseded"
    expect_error("non-active claim record", lambda: build(claims=inactive), failures)

    missing_ar = copy.deepcopy(entities)
    missing_ar[0]["names"] = {"en": "Atlas Aerospace"}
    expect_error("entity missing official Arabic name", lambda: build(entities=missing_ar), failures)

    orphan = copy.deepcopy(claims)
    orphan[0]["evidence_ids"] = ["SDA-EVID-NOT-HERE"]
    expect_error("claim citing evidence outside context", lambda: build(claims=orphan), failures)

    conflicting = claims + [
        {
            "claim_id": "SDA-CLAIM-CEDAR-QTY-2",
            "subject_entity_id": "SDA-PROC-CEDAR",
            "predicate_id": "procurement.quantity",
            "value": {
                "kind": "number",
                "value": 15,
                "unit": "aircraft",
                "precision": "exact",
                "lower_bound": None,
                "upper_bound": None,
            },
            "validity": {"point_in_time": {"value": "2024-03-15", "precision": "day"}},
            "claim_state": "active",
            "record_status": "active",
            "evidence_ids": ["SDA-EVID-CEDAR-1"],
        }
    ]
    expect_error("conflicting active claims", lambda: build(claims=conflicting), failures)

    cand_entity = copy.deepcopy(entities)
    cand_entity[0]["entity_id"] = "CAND-ENT-1"
    expect_error("candidate entity", lambda: build(entities=cand_entity), failures)

    bad_term = copy.deepcopy(terminology)
    bad_term["terms"][0]["ar"] = ""
    expect_error("terminology term missing Arabic rendering", lambda: build(terminology=bad_term), failures)

    # --- accepted run via fake invoker ---
    captured_prompt: list[str] = []

    def fake_invoke(prompt: str) -> str:
        captured_prompt.append(prompt)
        return json.dumps(good_draft_output(), ensure_ascii=False)

    run = build_bilingual_draft_run(
        context=context,
        terminology=terminology,
        model_trace=DraftModelTrace(
            provider="deterministic-test", model="fixture-drafter", model_version="v0"
        ),
        invoke=fake_invoke,
        clock=lambda: "2026-10-02T00:01:00Z",
    )
    validate("ai-bilingual-draft-run.schema.json", run, "accepted draft run")
    expect(
        run["validation"]["status"] == "accepted_for_editorial_review",
        "valid draft output was not accepted",
        failures,
    )
    expect(
        run["input_context_sha256"] == sha256_of(context),
        "input context hash does not match the approved context",
        failures,
    )
    expect(
        captured_prompt[0] == json.dumps(context, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        "invoker did not receive exactly the canonical context serialization",
        failures,
    )
    expect(
        "CAND-" not in captured_prompt[0],
        "canonical prompt leaked candidate identity markers",
        failures,
    )
    expect(
        run["authority"]
        == {"mode": "candidate_only", "canonical_mutation_authority": False, "publication_authority": False},
        "draft run carries more than candidate-only authority",
        failures,
    )
    expect(
        run["model_trace"]["adapter_version"] == ADAPTER_VERSION,
        "draft run lost the adapter version",
        failures,
    )
    expect(
        [unit["unit_id"] for unit in run["units"]] == ["UNIT-QTY", "UNIT-MANUFACTURER"],
        "accepted run altered the unit list",
        failures,
    )

    # Determinism: same inputs and clock -> same identity; different clock -> different identity.
    run_again = build_bilingual_draft_run(
        context=context,
        terminology=terminology,
        model_trace=DraftModelTrace(
            provider="deterministic-test", model="fixture-drafter", model_version="v0"
        ),
        invoke=fake_invoke,
        clock=lambda: "2026-10-02T00:01:00Z",
    )
    expect(run_again["id"] == run["id"], "draft run identity is not deterministic", failures)
    run_later = build_bilingual_draft_run(
        context=context,
        terminology=terminology,
        model_trace=DraftModelTrace(
            provider="deterministic-test", model="fixture-drafter", model_version="v0"
        ),
        invoke=fake_invoke,
        clock=lambda: "2026-10-02T00:02:00Z",
    )
    expect(run_later["id"] != run["id"], "distinct invocations collapsed to one identity", failures)

    # --- rejection matrix ---
    def run_with_output(payload: Any) -> dict[str, Any]:
        def invoke(_: str) -> str:
            return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

        return build_bilingual_draft_run(
            context=context,
            terminology=terminology,
            model_trace=DraftModelTrace(
                provider="deterministic-test", model="fixture-drafter", model_version="v0"
            ),
            invoke=invoke,
            clock=lambda: "2026-10-02T00:03:00Z",
        )

    def expect_rejected(label: str, payload: Any, fragment: str) -> None:
        result = run_with_output(payload)
        expect(
            result["validation"]["status"] == "rejected",
            f"{label} was not rejected",
            failures,
        )
        expect(
            not result["units"] and not result["unknowns_rendered"],
            f"{label} rejection leaked drafted text",
            failures,
        )
        expect(
            any(fragment in error for error in result["validation"]["errors"]),
            f"{label} rejection lacks the expected reason ({fragment!r}): "
            f"{result['validation']['errors'][:2]}",
            failures,
        )
        validate("ai-bilingual-draft-run.schema.json", result, f"rejected run ({label})")

    expect_rejected("malformed JSON", "not-json", "strict finite JSON")
    expect_rejected("duplicate JSON keys", '{"units": [], "units": []}', "duplicate JSON")

    unsupported = copy.deepcopy(good_draft_output())
    unsupported["units"][0]["claim_ids"] = ["SDA-CLAIM-NOT-APPROVED"]
    expect_rejected("unsupported claim id", unsupported, "outside the approved context")

    orphan_cite = copy.deepcopy(good_draft_output())
    orphan_cite["units"][0]["evidence_ids"] = ["SDA-EVID-ORPHAN"]
    expect_rejected("orphaned citation", orphan_cite, "orphaned citation")

    term_violation = copy.deepcopy(good_draft_output())
    term_violation["units"][1]["prose"] = {
        "en": "Atlas Aerospace manufactures the Falcon-X trainer aircraft.",
        "ar": "تُصنّع الشركة منظومة فالكون-إكس.",  # registry Arabic for trainer aircraft absent
    }
    expect_rejected("terminology pairing violation", term_violation, "registry term")

    invented_number = copy.deepcopy(good_draft_output())
    invented_number["units"][0]["prose"]["en"] = (
        "Project Cedar carries a contracted quantity of 84 aircraft as of 2024-03-15."
    )
    expect_rejected("invented number", invented_number, "not grounded in the context")

    restricted = copy.deepcopy(good_draft_output())
    restricted["units"][0]["prose"]["en"] = (
        "Project Cedar covers 12 aircraft; unit readiness remains high."
    )
    expect_rejected("restricted operational detail", restricted, "restricted operational detail")

    coordinate = copy.deepcopy(good_draft_output())
    coordinate["units"][0]["prose"]["ar"] = "اعتُمد مشروع الأرز عند الإحداثيات 24.7136 شمالاً."
    expect_rejected("uncoarsened coordinate", coordinate, "coordinate-like number")

    missing_claim_accounting = copy.deepcopy(good_draft_output())
    missing_claim_accounting["units"] = missing_claim_accounting["units"][:1]
    expect_rejected(
        "unaccounted approved claim", missing_claim_accounting, "account for every approved claim"
    )

    unknown_outside = copy.deepcopy(good_draft_output())
    unknown_outside["unknowns_rendered"][0]["unknown_id"] = "UNK-NOT-IN-CONTEXT"
    expect_rejected("unknown outside context", unknown_outside, "outside the approved context")

    unaccounted_unknown = copy.deepcopy(good_draft_output())
    unaccounted_unknown["unknowns_rendered"] = []
    unaccounted_unknown["omitted_unknown_ids"] = []
    expect_rejected(
        "unaccounted context unknown", unaccounted_unknown, "account for every context unknown"
    )

    # Abstention is allowed: a claim may be undrafted, but must be accounted.
    abstain = copy.deepcopy(good_draft_output())
    abstain["units"] = abstain["units"][:1]
    abstain["undrafted_claim_ids"] = ["SDA-CLAIM-FALCONX-MANUFACTURER"]
    abstained_run = run_with_output(abstain)
    expect(
        abstained_run["validation"]["status"] == "accepted_for_editorial_review",
        "accounted abstention was rejected",
        failures,
    )
    expect(
        abstained_run["undrafted_claim_ids"] == ["SDA-CLAIM-FALCONX-MANUFACTURER"],
        "abstention lost the undrafted claim",
        failures,
    )

    if failures:
        print("M4 bilingual drafting validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated bounded bilingual drafting: deterministic approved-only context selection with "
        "official bilingual names and conflict fail-closed; invoker receives exactly the canonical "
        "context serialization; strict JSON draft output; one shared support set per unit across "
        "locales; support closure and full claim/unknown accounting with explicit abstention; "
        "terminology-registry pairing in both directions; unknown preservation; invented-number "
        "and restricted-detail rejection including coordinate-like precision; deterministic run "
        "identity per invocation; candidate-only authority with zero canonical mutation or "
        "publication rights."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
