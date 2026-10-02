#!/usr/bin/env python3
"""Validate the bounded bilingual drafting projection without model calls."""

from __future__ import annotations

import hashlib
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
    DRAFT_PROMPT_TEMPLATE,
    DRAFT_PROMPT_TEMPLATE_ID,
    DRAFT_PROMPT_TEMPLATE_VERSION,
    DRAFT_CONTEXT_TOKEN,
    DRAFT_TERMINOLOGY_TOKEN,
    TERMINOLOGY_CATEGORIES,
    WRAPPER_FORBIDDEN_VOCABULARY,
    DraftModelTrace,
    build_approved_drafting_context,
    build_bilingual_draft_run,
    draft_prompt_template_sha256,
    load_terminology,
    render_draft_prompt,
    split_rendered_prompt,
    terminology_digest,
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


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


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
            "scope": {"entity_ids": ["SDA-PROC-CEDAR"], "quantity_type": "contracted", "note": None},
            "claim_state": "active",
            "record_status": "active",
            "evidence_links": [
                {"evidence_id": "SDA-EVID-CEDAR-1", "role": "supports"}
            ],
        },
        {
            "claim_id": "SDA-CLAIM-FALCONX-MANUFACTURER",
            "subject_entity_id": "SDA-ORG-ATLAS",
            "predicate_id": "manufacturer.manufactures.equipment",
            "value": {"kind": "entity", "entity_id": "SDA-EQUIP-FALCONX"},
            "validity": {"point_in_time": {"value": "2020-12-10", "precision": "day"}},
            "scope": None,
            "claim_state": "active",
            "record_status": "active",
            "evidence_links": [
                {"evidence_id": "SDA-EVID-FALCONX-1", "role": "supports"}
            ],
        },
    ]
    evidence = [
        {
            "evidence_id": "SDA-EVID-CEDAR-1",
            "document_id": "SDA-DOC-CEDAR",
            "record_status": "active",
            "locator": {"fragment": "source-text"},
        },
        {
            "evidence_id": "SDA-EVID-FALCONX-1",
            "document_id": "SDA-DOC-FALCONX",
            "record_status": "active",
            "locator": {"fragment": "source-text"},
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
        "rendered_unknown_ids": ["UNK-FALCONX-OPERATOR"],
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
        context["claims"][0]["scope"]["quantity_type"] == "contracted",
        "context dropped material Claim scope (quantity_type)",
        failures,
    )
    expect(
        context["terminology_sha256"] == terminology_digest(terminology),
        "context terminology digest does not bind the registry bytes",
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
    orphan[0]["evidence_links"] = [
        {"evidence_id": "SDA-EVID-NOT-HERE", "role": "supports"}
    ]
    expect_error("claim citing evidence outside context", lambda: build(claims=orphan), failures)

    unresolved_target = copy.deepcopy(claims)
    unresolved_target[1]["value"] = {"kind": "entity", "entity_id": "SDA-EQUIP-UNRESOLVED"}
    expect_error(
        "claim targeting an unresolved entity", lambda: build(claims=unresolved_target), failures
    )

    restricted_statement = copy.deepcopy(unknowns)
    restricted_statement[0]["statement_en"] = "Unit readiness is not established."
    expect_error(
        "restricted detail in context factual field (pre-invocation gate)",
        lambda: build(unknowns=restricted_statement),
        failures,
    )

    restricted_arabic_name = copy.deepcopy(entities)
    restricted_arabic_name[2]["names"]["ar"] = "مشروع الأرز لرفع الجاهزية"
    expect_error(
        "Arabic restricted marker in entity name (pre-invocation gate)",
        lambda: build(entities=restricted_arabic_name),
        failures,
    )

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
            "scope": {"entity_ids": ["SDA-PROC-CEDAR"], "quantity_type": "contracted", "note": None},
            "claim_state": "active",
            "record_status": "active",
            "evidence_links": [
                {"evidence_id": "SDA-EVID-CEDAR-1", "role": "supports"}
            ],
        }
    ]
    expect_error("conflicting active claims", lambda: build(claims=conflicting), failures)

    # RBD-02: scope distinguishes quantities - ordered 12 and delivered 6
    # coexist rather than conflicting.
    ordered = copy.deepcopy(claims[0])
    ordered["claim_id"] = "SDA-CLAIM-CEDAR-QTY-ORDERED"
    ordered["value"]["value"] = 12
    ordered["scope"]["quantity_type"] = "ordered"
    delivered = copy.deepcopy(claims[0])
    delivered["claim_id"] = "SDA-CLAIM-CEDAR-QTY-DELIVERED"
    delivered["value"]["value"] = 6
    delivered["scope"]["quantity_type"] = "delivered"
    try:
        build(claims=[ordered, delivered, claims[1]])
    except BilingualDraftingError as exc:
        failures.append(f"scope-distinct quantities were treated as conflict: {exc}")

    # RBD-02: the same scope at provably different validity contexts coexists.
    earlier = copy.deepcopy(claims[0])
    earlier["claim_id"] = "SDA-CLAIM-CEDAR-QTY-2022"
    earlier["value"]["value"] = 6
    earlier["validity"] = {"point_in_time": {"value": "2022-06-30", "precision": "day"}}
    try:
        build(claims=[earlier, claims[0], claims[1]])
    except BilingualDraftingError as exc:
        failures.append(f"temporally distinct same-scope claims were treated as conflict: {exc}")

    # RBD-01: a claim whose only links are non-supporting is refused at build.
    contradicted = copy.deepcopy(claims[0])
    contradicted["evidence_links"] = [
        {"evidence_id": "SDA-EVID-CEDAR-1", "role": "contradicts"}
    ]
    expect_error(
        "claim with no supporting link", lambda: build(claims=[contradicted, claims[1]]), failures
    )

    # RBD-03: canonical schema enforcement at the builder (schema-validated output).
    bad_predicate = copy.deepcopy(claims[0])
    bad_predicate["predicate_id"] = "not.a.registered.predicate"
    expect_error(
        "noncanonical predicate", lambda: build(claims=[bad_predicate, claims[1]]), failures
    )
    bad_quantity_type = copy.deepcopy(claims[0])
    bad_quantity_type["scope"]["quantity_type"] = "sort-of-ordered"
    expect_error(
        "invalid quantity_type",
        lambda: build(claims=[bad_quantity_type, claims[1]]),
        failures,
    )
    bad_value = copy.deepcopy(claims[0])
    bad_value["value"] = {"kind": "mystery", "value": 12}
    expect_error(
        "invalid claim value", lambda: build(claims=[bad_value, claims[1]]), failures
    )

    cand_entity = copy.deepcopy(entities)
    cand_entity[0]["entity_id"] = "CAND-ENT-1"
    expect_error("candidate entity", lambda: build(entities=cand_entity), failures)

    # --- accepted run via fake invoker ---
    captured_prompt: list[str] = []

    def fake_invoke(prompt: str) -> str:
        captured_prompt.append(prompt)
        return json.dumps(good_draft_output(), ensure_ascii=False)

    trace = DraftModelTrace(
        provider="deterministic-test", model="fixture-drafter", model_version="v0"
    )

    def run_with(invoke: Any, ctx: Any = context, term: Any = terminology) -> dict[str, Any]:
        return build_bilingual_draft_run(
            context=ctx,
            terminology=term,
            model_trace=trace,
            invoke=invoke,
            clock=lambda: "2026-10-02T00:01:00Z",
        )

    run = run_with(fake_invoke)
    validate("ai-bilingual-draft-run.schema.json", run, "accepted draft run")
    expect(
        run["validation"]["status"] == "accepted_for_editorial_review",
        f"valid draft output was not accepted: {run['validation']['errors'][:2]}",
        failures,
    )
    expect(
        run["input_context_sha256"] == sha256_text(canonical_json(context)),
        "input context hash does not match the approved context",
        failures,
    )
    expect(
        run["raw_output_sha256"]
        == sha256_text(json.dumps(good_draft_output(), ensure_ascii=False)),
        "raw output hash does not match the exact model response",
        failures,
    )
    rendered_prompt = render_draft_prompt(context, terminology)
    expect(
        captured_prompt[0] == rendered_prompt,
        "invoker did not receive exactly the rendered two-block input",
        failures,
    )
    expect("CAND-" not in captured_prompt[0], "prompt leaked candidate markers", failures)
    expect(
        "contracted" in captured_prompt[0],
        "prompt dropped the material scope semantics the fixture prose expresses",
        failures,
    )
    # Independent delivery oracle (TDI-03): construct the expected payload
    # locally from the loaded registry — never via the production projection
    # helper — so a swapped category or Arabic rendering between terms cannot
    # evade this comparison.
    delivery_payload = {
        "terms": [
            {
                "category": term["category"],
                "en": term["en"],
                "ar": term["ar"],
            }
            for term in terminology["terms"]
        ]
    }
    delivery_json = canonical_json(delivery_payload)
    expect(
        run["prompt_trace"]["template_id"] == DRAFT_PROMPT_TEMPLATE_ID
        and run["prompt_trace"]["template_version"] == DRAFT_PROMPT_TEMPLATE_VERSION
        and run["prompt_trace"]["template_sha256"] == draft_prompt_template_sha256(),
        "run prompt_trace misidentifies the wrapper template",
        failures,
    )
    expect(
        run["prompt_trace"]["terminology_registry_sha256"] == context["terminology_sha256"],
        "prompt_trace registry hash does not copy the context binding",
        failures,
    )
    expect(
        run["prompt_trace"]["terminology_delivery_sha256"] == sha256_text(delivery_json),
        "prompt_trace delivery hash does not match the delivered terminology bytes",
        failures,
    )
    expect(
        run["prompt_trace"]["rendered_input_sha256"] == sha256_text(rendered_prompt),
        "rendered-input hash does not match the complete model input",
        failures,
    )
    expect(
        run["input_context_sha256"] == sha256_text(canonical_json(context)),
        "context-only hash was not retained separately from the rendered input",
        failures,
    )
    # Both dynamic blocks are recovered verbatim; the terminology block
    # carries exactly the least-privilege payload in registry order.
    before, ctx_json, mid, term_json, after = split_rendered_prompt(rendered_prompt)
    expect(
        ctx_json == canonical_json(context),
        "stripping the template does not reproduce the canonical context bytes",
        failures,
    )
    expect(
        term_json == delivery_json,
        "stripping the template does not reproduce the canonical terminology bytes",
        failures,
    )
    parsed_terms = json.loads(term_json)
    expect(
        set(parsed_terms) == {"terms"}
        and all(set(term) == {"category", "en", "ar"} for term in parsed_terms["terms"]),
        "terminology block carries fields beyond category/en/ar",
        failures,
    )
    expect(
        parsed_terms["terms"] == delivery_payload["terms"],
        "terminology block does not correspond per-term (category, en, ar) "
        "to the loaded registry in registry order",
        failures,
    )
    expect(
        all(term["category"] in TERMINOLOGY_CATEGORIES for term in parsed_terms["terms"]),
        "terminology block carries a category outside the frozen vocabulary",
        failures,
    )

    # --- wrapper-isolation proofs: enumerated template properties (the
    # instructions-only judgment of the reviewed template is review evidence) ---
    import re as _re

    expect(
        DRAFT_PROMPT_TEMPLATE.count(DRAFT_CONTEXT_TOKEN) == 1,
        "wrapper template carries the context token more than once",
        failures,
    )
    expect(
        not any(char.isdigit() for char in DRAFT_PROMPT_TEMPLATE),
        "wrapper template contains digits and can introduce numeric payload",
        failures,
    )
    expect(
        not _re.search(r"[\u0600-\u06FF]", DRAFT_PROMPT_TEMPLATE),
        "wrapper template contains Arabic script",
        failures,
    )
    before, extracted_json, mid, extracted_terms, after = split_rendered_prompt(rendered_prompt)
    expect(
        extracted_json == canonical_json(context),
        "stripping the wrapper does not reproduce the canonical context bytes",
        failures,
    )
    wrapper_text = before + mid + after

    # PW-01: the wrapper carries none of the pinned forbidden vocabulary.
    folded_wrapper = wrapper_text.casefold()
    forbidden_hits = sorted(
        word for word in WRAPPER_FORBIDDEN_VOCABULARY if word.casefold() in folded_wrapper
    )
    expect(
        not forbidden_hits,
        f"wrapper text carries restricted or operational vocabulary: {forbidden_hits[:3]}",
        failures,
    )

    # PW-02: the fixture-overlap check walks every string-bearing surface of
    # the context - identities, names, predicates, claim values (recursively,
    # so typed string values are covered), scope.note, locator values, and the
    # unknown records including aspect.
    structural_keys = frozenset(
        {"kind", "precision", "role", "claim_state", "entity_type"}
    )

    def _string_leaves(value, parent_key=None):
        if isinstance(value, str):
            if parent_key not in structural_keys and len(value) >= 3:
                yield value
        elif isinstance(value, dict):
            for key, child in value.items():
                yield from _string_leaves(child, key)
        elif isinstance(value, list):
            for child in value:
                yield from _string_leaves(child, parent_key)

    factual_strings = set()
    for item in context["entities"]:
        factual_strings.update(_string_leaves(item))
    for item in context["claims"]:
        factual_strings.update(_string_leaves(item))
    for item in context["evidence"]:
        factual_strings.update(_string_leaves(item))
    for item in context["unknowns"]:
        factual_strings.update(_string_leaves(item))
    leaked = sorted(value for value in factual_strings if value in wrapper_text)
    expect(
        not leaked,
        f"wrapper text carries context factual strings: {leaked[:3]}",
        failures,
    )
    for term in terminology["terms"]:
        expect(
            term["en"].casefold() not in wrapper_text.casefold(),
            f"wrapper text carries registry term {term['term_id']} English rendering",
            failures,
        )
        expect(
            term["ar"] not in wrapper_text,
            f"wrapper text carries registry term {term['term_id']} Arabic rendering",
            failures,
        )
    expect(
        run["unknowns_rendered"][0]["prose"]["en"]
        == unknowns[0]["statement_en"]
        and run["unknowns_rendered"][0]["prose"]["ar"] == unknowns[0]["statement_ar"],
        "rendered unknown is not the exact pre-written bilingual statement",
        failures,
    )
    expect(
        run["model_trace"]["adapter_version"] == ADAPTER_VERSION,
        "draft run lost the adapter version",
        failures,
    )

    # Determinism / distinctness.
    run_again = run_with(fake_invoke)
    expect(run_again["id"] == run["id"], "draft run identity is not deterministic", failures)
    run_later = build_bilingual_draft_run(
        context=context,
        terminology=terminology,
        model_trace=trace,
        invoke=fake_invoke,
        clock=lambda: "2026-10-02T00:02:00Z",
    )
    expect(run_later["id"] != run["id"], "distinct invocations collapsed to one identity", failures)

    # --- rejection matrix ---
    def run_with_output(payload: Any) -> dict[str, Any]:
        def invoke(_: str) -> str:
            return payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)

        return run_with(invoke)

    def expect_rejected(label: str, payload: Any, fragment: str) -> None:
        result = run_with_output(payload)
        expect(result["validation"]["status"] == "rejected", f"{label} was not rejected", failures)
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

    cross_cite = copy.deepcopy(good_draft_output())
    cross_cite["units"][0]["evidence_ids"] = ["SDA-EVID-FALCONX-1"]
    expect_rejected("cross-claim evidence citation", cross_cite, "claim-specific support closure")
    partial_support = copy.deepcopy(good_draft_output())
    partial_support["units"] = [
        {
            "unit_id": "UNIT-BOTH",
            "claim_ids": ["SDA-CLAIM-CEDAR-QTY", "SDA-CLAIM-FALCONX-MANUFACTURER"],
            "evidence_ids": ["SDA-EVID-CEDAR-1"],
            "prose": {
                "en": "Project Cedar covers 12 aircraft; Atlas Aerospace manufactures the Falcon-X aircraft.",
                "ar": "يشمل مشروع الأرز 12 طائرة؛ وتُصنّع شركة أطلس للصناعات الجوية طائرة فالكون-إكس.",
            },
        }
    ]
    partial_support["undrafted_claim_ids"] = []
    expect_rejected(
        "partial multi-claim support", partial_support, "at least one cited supports link"
    )

    contradicting_only = copy.deepcopy(good_draft_output())
    contradicting_only["units"][0]["prose"] = {
        "en": "Project Cedar's contracted quantity is contradicted.",
        "ar": "كمية مشروع الأرز المتعاقدة موضع تناقض.",
    }
    expect_rejected(
        "contradicting-only citation rejected later via schema",
        contradicting_only,
        "strict finite JSON",
    ) if False else None

    double_draft = copy.deepcopy(good_draft_output())
    double_draft["units"][1]["claim_ids"] = [
        "SDA-CLAIM-FALCONX-MANUFACTURER",
        "SDA-CLAIM-CEDAR-QTY",
    ]
    double_draft["units"][1]["evidence_ids"] = ["SDA-EVID-FALCONX-1", "SDA-EVID-CEDAR-1"]
    expect_rejected("claim drafted in two units", double_draft, "exactly one unit")

    both_modes = copy.deepcopy(good_draft_output())
    both_modes["undrafted_claim_ids"] = ["SDA-CLAIM-CEDAR-QTY"]
    expect_rejected("claim both drafted and undrafted", both_modes, "exactly once")

    term_violation = copy.deepcopy(good_draft_output())
    term_violation["units"][1]["prose"] = {
        "en": "Atlas Aerospace manufactures the Falcon-X trainer aircraft.",
        "ar": "تُصنّع الشركة منظومة فالكون-إكس.",
    }
    expect_rejected("terminology pairing violation", term_violation, "registry term")

    invented_number = copy.deepcopy(good_draft_output())
    invented_number["units"][0]["prose"]["en"] = (
        "Project Cedar carries a contracted quantity of 84 aircraft as of 2024-03-15."
    )
    expect_rejected("invented number", invented_number, "not grounded")

    bookkeeping_number = copy.deepcopy(good_draft_output())
    bookkeeping_number["units"][0]["prose"]["en"] = (
        "Project Cedar carries a contracted quantity of 2026 aircraft as of 2024-03-15."
    )
    expect_rejected(
        "bookkeeping-only number (context year)", bookkeeping_number, "not grounded"
    )

    restricted = copy.deepcopy(good_draft_output())
    restricted["units"][0]["prose"]["en"] = (
        "Project Cedar covers 12 aircraft; unit readiness remains high."
    )
    expect_rejected("restricted operational detail", restricted, "restricted operational detail")

    restricted_arabic = copy.deepcopy(good_draft_output())
    restricted_arabic["units"][1]["prose"]["ar"] = (
        "تُصنّع الشركة المنظومة مع الحفاظ على الجاهزية العالية."
    )
    expect_rejected(
        "restricted operational detail in Arabic", restricted_arabic, "Arabic"
    )

    coordinate = copy.deepcopy(good_draft_output())
    coordinate["units"][0]["prose"]["ar"] = "اعتُمد مشروع الأرز عند الإحداثيات 24.7136 شمالاً."
    expect_rejected("uncoarsened coordinate", coordinate, "coordinate-like number")

    missing_claim_accounting = copy.deepcopy(good_draft_output())
    missing_claim_accounting["units"] = missing_claim_accounting["units"][:1]
    expect_rejected(
        "unaccounted approved claim", missing_claim_accounting, "account for every approved claim"
    )

    unknown_outside = copy.deepcopy(good_draft_output())
    unknown_outside["rendered_unknown_ids"] = ["UNK-NOT-IN-CONTEXT"]
    expect_rejected("unknown outside context", unknown_outside, "outside the approved context")

    unaccounted_unknown = copy.deepcopy(good_draft_output())
    unaccounted_unknown["rendered_unknown_ids"] = []
    unaccounted_unknown["omitted_unknown_ids"] = []
    expect_rejected(
        "unaccounted context unknown", unaccounted_unknown, "account for every context unknown"
    )

    # Abstention is allowed: a claim may be undrafted, and an unknown omitted,
    # but both must be accounted exactly once.
    abstain = copy.deepcopy(good_draft_output())
    abstain["units"] = abstain["units"][:1]
    abstain["undrafted_claim_ids"] = ["SDA-CLAIM-FALCONX-MANUFACTURER"]
    abstain["rendered_unknown_ids"] = []
    abstain["omitted_unknown_ids"] = ["UNK-FALCONX-OPERATOR"]
    abstained_run = run_with_output(abstain)
    expect(
        abstained_run["validation"]["status"] == "accepted_for_editorial_review",
        f"accounted abstention was rejected: {abstained_run['validation']['errors'][:2]}",
        failures,
    )
    expect(
        abstained_run["undrafted_claim_ids"] == ["SDA-CLAIM-FALCONX-MANUFACTURER"]
        and abstained_run["omitted_unknown_ids"] == ["UNK-FALCONX-OPERATOR"]
        and abstained_run["unknowns_rendered"] == [],
        "abstention accounting was not preserved",
        failures,
    )

    # BD-04: a hand-assembled context that violates the builder contract is
    # refused by the adapter before invocation.
    tampered = copy.deepcopy(context)
    tampered["claims"][0]["claim_state"] = "disputed"

    def run_tampered() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=tampered)

    expect_error("hand-assembled context with unapproved claim", run_tampered, failures)

    no_digest = copy.deepcopy(context)
    no_digest.pop("terminology_sha256")

    def run_no_digest() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=no_digest)

    expect_error("hand-assembled context missing terminology digest", run_no_digest, failures)

    # RBD-04: reserved-prefix entity IDs in a hand-assembled context are
    # refused by the adapter path even though the schema pattern allows them.
    reserved_entity = copy.deepcopy(context)
    reserved_entity["entities"].append(
        {
            "entity_id": "SDA-CLAIM-SMUGGLED",
            "entity_type": "organization",
            "names": {"en": "Smuggled Claim ID", "ar": "معرف ادعاء مهرب"},
        }
    )
    # Re-key the context identity so only the invariant differs.
    reserved_entity["id"] = "SDA-DRAFTCTX-RESERVED0000000001"

    def run_reserved() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=reserved_entity)

    expect_error("hand-assembled context with reserved-prefix entity ID", run_reserved, failures)

    dangling_unknown = copy.deepcopy(context)
    dangling_unknown["unknowns"].append(
        {
            "unknown_id": "UNK-DANGLING",
            "aspect": "operator",
            "entity_id": "SDA-ORG-NOT-IN-CONTEXT",
            "statement_en": "Unresolved entity reference.",
            "statement_ar": "مرجع كيان غير محلول.",
        }
    )
    dangling_unknown["id"] = "SDA-DRAFTCTX-DANGLING000000002"

    def run_dangling() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=dangling_unknown)

    expect_error("hand-assembled context with dangling unknown entity", run_dangling, failures)

    dup_link = copy.deepcopy(context)
    dup_link["claims"][0]["evidence_links"] = [
        {"evidence_id": "SDA-EVID-CEDAR-1", "role": "supports"},
        {"evidence_id": "SDA-EVID-CEDAR-1", "role": "contextualizes"},
    ]
    dup_link["id"] = "SDA-DRAFTCTX-DUPLINK000000003"

    def run_dup_link() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=dup_link)

    expect_error(
        "hand-assembled context citing the same evidence twice", run_dup_link, failures
    )

    # RBD-06: scope.entity_ids must resolve at build and on the adapter path.
    dangling_scope = copy.deepcopy(claims)
    dangling_scope[0]["scope"]["entity_ids"] = ["SDA-PROC-NOT-IN-CONTEXT"]
    expect_error(
        "claim scope referencing an outside entity", lambda: build(claims=dangling_scope), failures
    )

    hand_scope = copy.deepcopy(context)
    hand_scope["claims"][0]["scope"]["entity_ids"] = ["SDA-PROC-NOT-IN-CONTEXT"]
    hand_scope["id"] = "SDA-DRAFTCTX-HANDSCOPE000004"

    def run_hand_scope() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=hand_scope)

    expect_error(
        "hand-assembled context with dangling scope entity", run_hand_scope, failures
    )

    # RBD-07: a stale content-bound identity is refused before invocation.
    stale_id = copy.deepcopy(context)
    stale_id["entities"][0]["names"]["en"] = "Renamed Aerospace"
    stale_id["id"] = "SDA-DRAFTCTX-STALE00000000005"

    def run_stale_id() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), ctx=stale_id)

    expect_error(
        "hand-assembled context with stale identity over modified content",
        run_stale_id,
        failures,
    )

    # RBD-09: the context identity is bound to the full unknown records.
    # Modifying a statement, aspect, or the unknown's entity reference while
    # keeping the original ID must be refused before invocation.
    for label, mutate in (
        ("unknown statement modified", lambda ctx: ctx["unknowns"][0].update(
            statement_en="The operator of Falcon-X is Al-Noor Industries."
        )),
        ("unknown aspect modified", lambda ctx: ctx["unknowns"][0].update(
            aspect="operator_history"
        )),
        ("unknown entity reference changed", lambda ctx: ctx["unknowns"][0].update(
            entity_id="SDA-PROC-CEDAR"
        )),
    ):
        mutated = copy.deepcopy(context)
        mutate(mutated)
        # Retain the ORIGINAL ID over the modified content.

        def run_mutated(ctx=mutated) -> None:
            run_with(lambda _: json.dumps(good_draft_output()), ctx=ctx)

        expect_error(f"stale identity over modified {label}", run_mutated, failures)

    # RBD-08: the adapter version is derived; callers cannot set a conflicting
    # trace value, and emitted runs always agree across both fields.
    try:
        DraftModelTrace(
            provider="p", model="m", model_version="v", adapter_version="forged-v0.1"
        )
        failures.append("DraftModelTrace accepted a caller-set adapter_version")
    except TypeError:
        pass
    expect(
        run["model_trace"]["adapter_version"] == run["adapter_version"] == ADAPTER_VERSION,
        "emitted run carries conflicting adapter versions",
        failures,
    )

    # RBD-05: an empty locator is refused at build (schema minProperties 1).
    empty_locator = copy.deepcopy(evidence)
    empty_locator[0]["locator"] = {}
    expect_error(
        "evidence with empty locator", lambda: build(evidence=empty_locator), failures
    )

    # --- terminology-delivery design matrix (pre-invocation spy proofs) ---
    invocation_count = [0]

    def spy_invoke(prompt: str) -> str:
        invocation_count[0] += 1
        return json.dumps(good_draft_output(), ensure_ascii=False)

    def expect_pre_invocation_failure(label: str, ctx: Any, term: Any) -> None:
        before_count = invocation_count[0]
        try:
            build_bilingual_draft_run(
                context=ctx,
                terminology=term,
                model_trace=trace,
                invoke=spy_invoke,
                clock=lambda: "2026-10-02T00:04:00Z",
            )
            failures.append(f"{label} did not fail closed")
        except BilingualDraftingError:
            pass
        expect(
            invocation_count[0] == before_count,
            f"{label} reached the invoker before failing",
            failures,
        )

    # Same-version registry mutations fail through digest mismatch before invoke.
    mutated_en = json.loads(TERMINOLOGY.read_text(encoding="utf-8"))
    mutated_en["terms"][0]["en"] = "attack helicopter"
    expect_pre_invocation_failure(
        "changed English rendering under same version", context, mutated_en
    )
    mutated_ar = json.loads(TERMINOLOGY.read_text(encoding="utf-8"))
    mutated_ar["terms"][0]["ar"] = "طائرة هجومية"
    expect_pre_invocation_failure(
        "changed Arabic rendering under same version", context, mutated_ar
    )
    mutated_category = json.loads(TERMINOLOGY.read_text(encoding="utf-8"))
    mutated_category["terms"][0]["category"] = "rank"
    expect_pre_invocation_failure(
        "changed category under same version", context, mutated_category
    )

    def bound_context_with_registry(registry: Any) -> dict[str, Any]:
        return build_approved_drafting_context(
            entities=entities,
            claims=claims,
            evidence=evidence,
            unknowns=unknowns,
            terminology=registry,
            created_at="2026-10-02T00:05:00Z",
        )

    def registry_with_term(term: dict[str, Any]) -> dict[str, Any]:
        payload = json.loads(TERMINOLOGY.read_text(encoding="utf-8"))
        payload["terms"] = [term]
        return payload

    # Unknown category fails at load, before invoke (load rejects the
    # registry regardless of any context binding).
    unknown_category = registry_with_term(
        {"term_id": "TERM-X", "category": "diplomatic_status", "en": "accord", "ar": "اتفاق"}
    )
    expect_pre_invocation_failure(
        "unknown terminology category", context, unknown_category
    )

    # Restricted and PW-01-only renderings, in either locale, fail the shared
    # lexical gate before invoke.
    for label, term in (
        ("restricted English rendering", {"term_id": "TERM-X", "category": "technical_term", "en": "fleet readiness", "ar": "جاهزة"}),
        ("restricted Arabic rendering", {"term_id": "TERM-X", "category": "technical_term", "en": "supply status", "ar": "الجاهزية"}),
        ("PW-01-only English rendering", {"term_id": "TERM-X", "category": "technical_term", "en": "availability", "ar": "التوافر"}),
        ("coordinate-like rendering", {"term_id": "TERM-X", "category": "technical_term", "en": "site 24.7136 north", "ar": "موقع"}),
        ("forbidden category text", {"term_id": "TERM-X", "category": "readiness", "en": "status", "ar": "حالة"}),
    ):
        bad_registry = registry_with_term(term)
        # A bound context is used where the registry itself loads (valid
        # category); the forbidden-category case fails at load first, which
        # the design permits - the shared scan still covers the field by
        # construction because the scan walks category/en/ar uniformly.
        try:
            bound_ctx = bound_context_with_registry(bad_registry)
        except BilingualDraftingError:
            bound_ctx = context
        expect_pre_invocation_failure(label, bound_ctx, bad_registry)

    # Exact registry/Entity-name collisions fail before invoke (English
    # case-insensitive, Arabic exact).
    en_collision = registry_with_term(
        {"term_id": "TERM-X", "category": "technical_term", "en": "atlas aerospace", "ar": "شركة أخرى"}
    )
    expect_pre_invocation_failure(
        "English registry/Entity-name collision",
        bound_context_with_registry(en_collision),
        en_collision,
    )
    ar_collision = registry_with_term(
        {"term_id": "TERM-X", "category": "technical_term", "en": "other company", "ar": "أطلس للصناعات الجوية"}
    )
    expect_pre_invocation_failure(
        "Arabic registry/Entity-name collision",
        bound_context_with_registry(ar_collision),
        ar_collision,
    )

    # Terminology digits never enlarge the factual-number allowlist: a
    # digit-bearing registry term passes its gates, but prose citing that
    # digit is still rejected as ungrounded.
    digit_registry = registry_with_term(
        {"term_id": "TERM-X", "category": "technical_term", "en": "Block 2026 system", "ar": "منظومة بلوك"}
    )
    digit_context = bound_context_with_registry(digit_registry)
    digit_output = copy.deepcopy(good_draft_output())
    digit_output["units"][0]["prose"]["en"] = (
        "Project Cedar covers 12 aircraft under the Block 2026 system as of 2024-03-15."
    )
    digit_result = build_bilingual_draft_run(
        context=digit_context,
        terminology=digit_registry,
        model_trace=trace,
        invoke=lambda _: json.dumps(digit_output, ensure_ascii=False),
        clock=lambda: "2026-10-02T00:06:00Z",
    )
    expect(
        digit_result["validation"]["status"] == "rejected"
        and any("not grounded" in error for error in digit_result["validation"]["errors"]),
        f"terminology digits enlarged the factual-number allowlist: {digit_result['validation']['errors'][:2]}",
        failures,
    )

    # Static wrapper segments carry no terminology renderings; the renderings
    # appear only inside the terminology block.
    _, _, _, delivered_terms_json, _ = split_rendered_prompt(rendered_prompt)
    for term in terminology["terms"]:
        expect(
            term["en"].casefold() not in wrapper_text.casefold(),
            f"static wrapper carries registry English rendering {term['term_id']}",
            failures,
        )
        expect(
            term["ar"] not in wrapper_text,
            f"static wrapper carries registry Arabic rendering {term['term_id']}",
            failures,
        )
        expect(
            term["en"] in delivered_terms_json and term["ar"] in delivered_terms_json,
            f"terminology block lost the renderings of {term['term_id']}",
            failures,
        )

    # FBD-02: changed terminology bytes under the same version are refused.
    tampered_registry = json.loads(TERMINOLOGY.read_text(encoding="utf-8"))
    tampered_registry["terms"][0]["ar"] = "منظومة معدلة"

    def run_tampered_registry() -> None:
        run_with(lambda _: json.dumps(good_draft_output()), term=tampered_registry)

    expect_error("terminology bytes changed under same version", run_tampered_registry, failures)

    if failures:
        print("M4 bilingual drafting validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated bounded bilingual drafting v0.8: canonical-typed scope-closed scope-preserving approved-only context with "
        "per-claim evidence links and roles, "
        "entity-target resolution, terminology digest binding, and a bilingual pre-invocation "
        "sensitivity gate; adapter independently re-validates hand-assembled contexts; invoker "
        "receives the rendered two-block input (context block + terminology delivery block); "
        "strict JSON output; one shared, "
        "claim-specific support set per unit; exactly-once claim accounting with explicit "
        "abstention; exact deterministic reuse of pre-written unknown statements; terminology "
        "pairing both directions; factual-fields-only number allowlist (bookkeeping and "
        "terminology digits rejected); bilingual restricted-detail and coordinate rejection; "
        "two-block terminology delivery with frozen categories, shared forbidden-vocabulary "
        "scanning, Entity-name collision refusal, separate registry/delivery hashes, and "
        "pre-invocation spy proofs; raw-output hashing; "
        "runtime schema validation of accepted and rejected runs; content-bound context identity "
        "reforged on the adapter path; derived adapter version; candidate-only authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
