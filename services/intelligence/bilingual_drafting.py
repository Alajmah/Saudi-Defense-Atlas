"""Bounded bilingual drafting projection for M4.

Architecture rule: the model drafts language; it does not choose facts. A
deterministic :func:`build_approved_drafting_context` first selects only
already-approved canonical Claims (including material ``scope`` semantics such
as ``quantity_type``), their Claim-specific Evidence references, resolved
Entities with official bilingual names (entity-valued Claim targets must
resolve), explicit pre-written unknown statements, and the project-owned
terminology registry version and digest. A deterministic drafting-eligibility
gate rejects restricted operational detail in either locale before any model
invocation. Only that bounded object reaches the drafting adapter, which
independently re-validates the context contract, sends exactly the canonical
serialization of the context as model input, and converts the response into a
candidate-only draft run: one shared, claim-specific support set per factual
unit across paired ar/en prose, exact deterministic reuse of pre-written
unknown statements, a factual-fields-only number allowlist, exactly-once claim
accounting, and a raw-output hash. Rejected output clears all drafted text.

Unresolved factual conflicts fail closed: no conflict-aware synthesis is
attempted in this version. The mechanical guards reject defined violations;
they do not make semantic invention impossible - human editorial review
remains the authority.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator, FormatChecker

ADAPTER_VERSION = "m4-bilingual-drafting-v0.2"

ROOT = Path(__file__).resolve().parents[2]
CONTEXT_SCHEMA_PATH = ROOT / "schemas" / "v0.1" / "editorial-drafting-context.schema.json"
RUN_SCHEMA_PATH = ROOT / "schemas" / "v0.1" / "ai-bilingual-draft-run.schema.json"

RESTRICTED_MARKERS_EN = (
    "readiness",
    "patrol",
    "stock level",
    "stock levels",
    "live unit",
    "operational tempo",
    "ammunition stock",
)
RESTRICTED_MARKERS_AR = (
    "جاهزية",  # readiness
    "دورية",  # patrol
    "مخزون",  # stock
    "وحدة عاملة",  # live/operating unit
    "وتيرة العمليات",  # operational tempo
    "ذخيرة",  # ammunition
)
RESTRICTED_COORDINATE_PATTERN = re.compile(r"\d{1,2}\.\d{3,}")
_DIGIT_RUN = re.compile(r"\d+")
_ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")


class BilingualDraftingError(ValueError):
    """Raised when drafting input or output violates the bounded contract."""


@dataclass(frozen=True)
class DraftModelTrace:
    provider: str
    model: str
    model_version: str
    adapter_version: str = ADAPTER_VERSION

    def as_dict(self) -> dict[str, str]:
        values = {
            "provider": self.provider,
            "model": self.model,
            "model_version": self.model_version,
            "adapter_version": self.adapter_version,
        }
        for key, value in values.items():
            if not isinstance(value, str) or not value.strip():
                raise BilingualDraftingError(f"draft model trace {key} must be non-empty")
            if len(value) > 128:
                raise BilingualDraftingError(
                    f"draft model trace {key} exceeds schema maximum length"
                )
        return values


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_canonical_json(parts).encode("utf-8")).hexdigest()[:20].upper()
    return f"{prefix}-{digest}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _load_schema(path: Path) -> Draft202012Validator:
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


_CONTEXT_VALIDATOR = _load_schema(CONTEXT_SCHEMA_PATH)
_RUN_VALIDATOR = _load_schema(RUN_SCHEMA_PATH)


def load_terminology(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate the project-owned terminology registry and index it by term."""

    version = payload.get("version")
    if not isinstance(version, str) or not version.strip():
        raise BilingualDraftingError("terminology registry requires a version")
    terms = payload.get("terms")
    if not isinstance(terms, list) or not terms:
        raise BilingualDraftingError("terminology registry requires a non-empty terms array")
    seen_ids: set[str] = set()
    seen_en: set[str] = set()
    for term in terms:
        if not isinstance(term, Mapping):
            raise BilingualDraftingError("terminology term must be an object")
        term_id = term.get("term_id")
        if not isinstance(term_id, str) or not term_id.strip():
            raise BilingualDraftingError("terminology term requires term_id")
        if term_id in seen_ids:
            raise BilingualDraftingError(f"duplicate terminology term_id: {term_id}")
        seen_ids.add(term_id)
        category = term.get("category")
        if not isinstance(category, str) or not category.strip():
            raise BilingualDraftingError(f"terminology term {term_id} requires a category")
        for locale in ("en", "ar"):
            rendering = term.get(locale)
            if not isinstance(rendering, str) or not rendering.strip():
                raise BilingualDraftingError(
                    f"terminology term {term_id} requires a non-empty {locale} rendering"
                )
        extra = set(term) - {"term_id", "category", "en", "ar"}
        if extra:
            raise BilingualDraftingError(
                f"terminology term {term_id} carries unsupported keys: {sorted(extra)}"
            )
        en_key = str(term["en"]).casefold()
        if en_key in seen_en:
            raise BilingualDraftingError(
                f"terminology registry carries two terms with the same English rendering: {en_key!r}"
            )
        seen_en.add(en_key)
    return {"version": version, "terms": [dict(term) for term in terms]}


def terminology_digest(registry: Mapping[str, Any]) -> str:
    """Canonical digest over the registry bytes that govern acceptance."""

    return _sha256_text(_canonical_json({"version": registry["version"], "terms": registry["terms"]}))


def _require_active(record: Mapping[str, Any], label: str) -> None:
    status = record.get("record_status", "active")
    if status != "active":
        raise BilingualDraftingError(f"{label} is not an active canonical record")


def _restricted_in_text(label: str, text: str, failures: list[str]) -> None:
    folded = text.casefold()
    for marker in RESTRICTED_MARKERS_EN:
        if marker in folded:
            failures.append(f"{label} carries restricted operational detail: {marker}")
    for marker in RESTRICTED_MARKERS_AR:
        if marker in text:
            failures.append(f"{label} carries restricted operational detail (Arabic): {marker}")
    if RESTRICTED_COORDINATE_PATTERN.search(text):
        failures.append(f"{label} carries an uncoarsened coordinate-like number")


def _eligibility_parts(context: Mapping[str, Any]) -> dict[str, str]:
    parts = {
        f"entity {item['entity_id']} names": f"{item['names']['en']} {item['names']['ar']}"
        for item in context["entities"]
    }
    parts.update(
        {
            f"claim {item['claim_id']} factual fields": _canonical_json(
                {
                    "predicate_id": item["predicate_id"],
                    "value": item["value"],
                    "validity": item["validity"],
                    "scope": item["scope"],
                }
            )
            for item in context["claims"]
        }
    )
    parts.update(
        {
            f"unknown {item['unknown_id']} statements": (
                f"{item['statement_en']} {item['statement_ar']}"
            )
            for item in context["unknowns"]
        }
    )
    return parts


def _drafting_eligibility_gate(context: Mapping[str, Any]) -> None:
    """Deterministic sensitivity gate before any model invocation (BD-03)."""

    failures: list[str] = []
    for label, text in _eligibility_parts(context).items():
        _restricted_in_text(label, text, failures)
    if failures:
        raise BilingualDraftingError("; ".join(failures[:3]))


def build_approved_drafting_context(
    *,
    entities: list[Mapping[str, Any]],
    claims: list[Mapping[str, Any]],
    evidence: list[Mapping[str, Any]],
    unknowns: list[Mapping[str, Any]],
    terminology: Mapping[str, Any],
    created_at: str,
) -> dict[str, Any]:
    """Select only approved canonical records into the bounded drafting context.

    Fails closed on: candidate or non-canonical identities; unapproved or
    disputed claim state; conflicting active claims on the same
    subject/predicate; unresolved entity-valued Claim targets; entities without
    official bilingual names in both locales; evidence references that do not
    resolve; restricted operational detail in any factual field (either
    locale, before invocation); and malformed registry entries.
    """

    registry = load_terminology(terminology)

    entity_by_id: dict[str, dict[str, Any]] = {}
    for entity in entities:
        if not isinstance(entity, Mapping):
            raise BilingualDraftingError("drafting entity must be an object")
        entity_id = entity.get("entity_id")
        if not isinstance(entity_id, str) or not entity_id.startswith("SDA-"):
            raise BilingualDraftingError(
                f"drafting entity identity {entity_id!r} is not canonical SDA identity"
            )
        if entity_id.startswith(("SDA-CLAIM-", "SDA-EVID-", "CAND-")):
            raise BilingualDraftingError(
                f"drafting entity identity {entity_id!r} is not an Entity identity"
            )
        if entity_id in entity_by_id:
            raise BilingualDraftingError(f"duplicate drafting entity: {entity_id}")
        _require_active(entity, f"entity {entity_id}")
        names = entity.get("names")
        if not isinstance(names, Mapping):
            raise BilingualDraftingError(f"entity {entity_id} requires official names")
        for locale in ("en", "ar"):
            name = names.get(locale)
            if not isinstance(name, str) or not name.strip():
                raise BilingualDraftingError(
                    f"entity {entity_id} lacks an official {locale} name; "
                    "drafting never invents translations"
                )
        entity_type = entity.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type.strip():
            raise BilingualDraftingError(f"entity {entity_id} requires an entity_type")
        entity_by_id[entity_id] = {
            "entity_id": entity_id,
            "entity_type": entity_type,
            "names": {"en": str(names["en"]), "ar": str(names["ar"])},
        }

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for record in evidence:
        if not isinstance(record, Mapping):
            raise BilingualDraftingError("drafting evidence must be an object")
        evidence_id = record.get("evidence_id")
        if not isinstance(evidence_id, str) or not evidence_id.startswith("SDA-EVID-"):
            raise BilingualDraftingError(
                f"drafting evidence identity {evidence_id!r} is not canonical Evidence identity"
            )
        if evidence_id in evidence_by_id:
            raise BilingualDraftingError(f"duplicate drafting evidence: {evidence_id}")
        _require_active(record, f"evidence {evidence_id}")
        document_id = record.get("document_id")
        if not isinstance(document_id, str) or not document_id.startswith("SDA-DOC-"):
            raise BilingualDraftingError(
                f"evidence {evidence_id} must reference a canonical Document"
            )
        locator = record.get("locator")
        if not isinstance(locator, Mapping):
            raise BilingualDraftingError(f"evidence {evidence_id} requires a locator")
        role = record.get("role", "supports")
        if role not in ("supports", "contradicts", "contextualizes"):
            raise BilingualDraftingError(f"evidence {evidence_id} carries an unsupported role")
        evidence_by_id[evidence_id] = {
            "evidence_id": evidence_id,
            "document_id": document_id,
            "locator": dict(locator),
            "role": role,
        }

    prepared_claims: dict[str, dict[str, Any]] = {}
    claim_fingerprints: dict[tuple[str, str], str] = {}
    for claim in claims:
        if not isinstance(claim, Mapping):
            raise BilingualDraftingError("drafting claim must be an object")
        claim_id = claim.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id.startswith("SDA-CLAIM-"):
            raise BilingualDraftingError(
                f"drafting claim identity {claim_id!r} is not an approved canonical Claim; "
                "candidate claims cannot be drafted"
            )
        if claim_id in prepared_claims:
            raise BilingualDraftingError(f"duplicate drafting claim: {claim_id}")
        _require_active(claim, f"claim {claim_id}")
        state = claim.get("claim_state")
        if state != "active":
            raise BilingualDraftingError(
                f"claim {claim_id} has state {state!r}; unresolved conflict fails closed "
                "and disputed claims cannot be drafted"
            )
        subject = claim.get("subject_entity_id")
        if not isinstance(subject, str) or subject not in entity_by_id:
            raise BilingualDraftingError(
                f"claim {claim_id} subject {subject!r} is not a resolved context Entity"
            )
        predicate = claim.get("predicate_id")
        if not isinstance(predicate, str) or not predicate.strip():
            raise BilingualDraftingError(f"claim {claim_id} requires a predicate_id")
        value = claim.get("value")
        if not isinstance(value, Mapping):
            raise BilingualDraftingError(f"claim {claim_id} requires a typed value object")
        if value.get("kind") == "entity":
            target = value.get("entity_id")
            if not isinstance(target, str) or target not in entity_by_id:
                raise BilingualDraftingError(
                    f"claim {claim_id} targets unresolved entity {target!r}"
                )
        scope = claim.get("scope")
        if scope is not None and not isinstance(scope, Mapping):
            raise BilingualDraftingError(f"claim {claim_id} scope must be an object or null")
        evidence_ids = claim.get("evidence_ids")
        if (
            not isinstance(evidence_ids, list)
            or not evidence_ids
            or len(evidence_ids) != len(set(evidence_ids))
        ):
            raise BilingualDraftingError(
                f"claim {claim_id} requires a non-empty, unique evidence_ids array"
            )
        for evidence_id in evidence_ids:
            if not isinstance(evidence_id, str) or evidence_id not in evidence_by_id:
                raise BilingualDraftingError(
                    f"claim {claim_id} references evidence {evidence_id!r} outside the context"
                )
        fingerprint = (subject, predicate)
        rendered_value = _canonical_json(value)
        if fingerprint in claim_fingerprints and claim_fingerprints[fingerprint] != rendered_value:
            raise BilingualDraftingError(
                f"conflicting active claims on {predicate} for {subject}; "
                "drafting fails closed on unresolved conflict"
            )
        claim_fingerprints[fingerprint] = rendered_value
        prepared_claims[claim_id] = {
            "claim_id": claim_id,
            "subject_entity_id": subject,
            "predicate_id": predicate,
            "value": dict(value),
            "validity": claim.get("validity"),
            "scope": dict(scope) if scope is not None else None,
            "claim_state": "active",
            "evidence_ids": sorted(evidence_ids),
        }

    prepared_unknowns: list[dict[str, Any]] = []
    seen_unknowns: set[str] = set()
    for unknown in unknowns:
        if not isinstance(unknown, Mapping):
            raise BilingualDraftingError("drafting unknown must be an object")
        unknown_id = unknown.get("unknown_id")
        if not isinstance(unknown_id, str) or not unknown_id.startswith("UNK-"):
            raise BilingualDraftingError("drafting unknown requires UNK-* identity")
        if unknown_id in seen_unknowns:
            raise BilingualDraftingError(f"duplicate drafting unknown: {unknown_id}")
        seen_unknowns.add(unknown_id)
        aspect = unknown.get("aspect")
        if not isinstance(aspect, str) or not aspect.strip():
            raise BilingualDraftingError(f"unknown {unknown_id} requires an aspect")
        entity_id = unknown.get("entity_id")
        if entity_id is not None and (
            not isinstance(entity_id, str) or entity_id not in entity_by_id
        ):
            raise BilingualDraftingError(
                f"unknown {unknown_id} references an entity outside the context"
            )
        for key in ("statement_en", "statement_ar"):
            statement = unknown.get(key)
            if not isinstance(statement, str) or not statement.strip():
                raise BilingualDraftingError(f"unknown {unknown_id} requires {key}")
        prepared_unknowns.append(
            {
                "unknown_id": unknown_id,
                "aspect": aspect,
                "entity_id": entity_id,
                "statement_en": str(unknown["statement_en"]),
                "statement_ar": str(unknown["statement_ar"]),
            }
        )

    context = {
        "id": "",
        "created_at": created_at,
        "terminology_version": registry["version"],
        "terminology_sha256": terminology_digest(registry),
        "entities": [entity_by_id[key] for key in sorted(entity_by_id)],
        "claims": [prepared_claims[key] for key in sorted(prepared_claims)],
        "evidence": [evidence_by_id[key] for key in sorted(evidence_by_id)],
        "unknowns": prepared_unknowns,
        "conflicts": [],
        "authority": {
            "mode": "approved_canonical_read_only",
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }
    context["id"] = _stable_id(
        "SDA-DRAFTCTX",
        context["entities"],
        context["claims"],
        context["evidence"],
        [item["unknown_id"] for item in prepared_unknowns],
        context["terminology_sha256"],
        created_at,
    )
    _drafting_eligibility_gate(context)
    return context


def validate_drafting_context(context: Mapping[str, Any]) -> None:
    """Independently enforce the ApprovedDraftingContext contract (BD-04).

    The adapter calls this before invocation so a hand-assembled context must
    satisfy the same schema and builder-level invariants the builder produces,
    including support closure, entity resolution, conflict refusal, and the
    bilingual restricted-detail gate.
    """

    if not isinstance(context, Mapping):
        raise BilingualDraftingError("drafting context must be an object")
    schema_errors = [
        error.message for error in _CONTEXT_VALIDATOR.iter_errors(dict(context))
    ]
    if schema_errors:
        raise BilingualDraftingError(
            f"drafting context violates its schema: {schema_errors[0]}"
        )
    authority = context["authority"]
    if authority["mode"] != "approved_canonical_read_only":
        raise BilingualDraftingError("drafting requires an approved read-only context")
    if (
        authority["canonical_mutation_authority"] is not False
        or authority["publication_authority"] is not False
    ):
        raise BilingualDraftingError("drafting context exceeded read-only authority")
    if context["conflicts"] != []:
        raise BilingualDraftingError(
            "drafting context carries unresolved conflicts; drafting fails closed"
        )

    entity_ids = {item["entity_id"] for item in context["entities"]}
    evidence_ids = {item["evidence_id"] for item in context["evidence"]}
    if len(entity_ids) != len(context["entities"]):
        raise BilingualDraftingError("drafting context carries duplicate entities")
    if len(evidence_ids) != len(context["evidence"]):
        raise BilingualDraftingError("drafting context carries duplicate evidence")
    if len({item["claim_id"] for item in context["claims"]}) != len(context["claims"]):
        raise BilingualDraftingError("drafting context carries duplicate claims")

    fingerprints: dict[tuple[str, str], str] = {}
    for claim in context["claims"]:
        if claim["subject_entity_id"] not in entity_ids:
            raise BilingualDraftingError(
                f"claim {claim['claim_id']} subject is not a resolved context Entity"
            )
        if claim["claim_state"] != "active":
            raise BilingualDraftingError(
                f"claim {claim['claim_id']} is not an approved active claim"
            )
        if (
            claim["value"].get("kind") == "entity"
            and claim["value"].get("entity_id") not in entity_ids
        ):
            raise BilingualDraftingError(
                f"claim {claim['claim_id']} targets an unresolved entity"
            )
        for evidence_id in claim["evidence_ids"]:
            if evidence_id not in evidence_ids:
                raise BilingualDraftingError(
                    f"claim {claim['claim_id']} cites evidence outside the context"
                )
        fingerprint = (claim["subject_entity_id"], claim["predicate_id"])
        rendered = _canonical_json(claim["value"])
        if fingerprint in fingerprints and fingerprints[fingerprint] != rendered:
            raise BilingualDraftingError("drafting context carries conflicting active claims")
        fingerprints[fingerprint] = rendered

    unknown_ids = [item["unknown_id"] for item in context["unknowns"]]
    if len(unknown_ids) != len(set(unknown_ids)):
        raise BilingualDraftingError("drafting context carries duplicate unknowns")

    _drafting_eligibility_gate(context)


def _reject_json_constant(value: str) -> Any:
    raise ValueError(f"non-finite JSON constant is not allowed: {value}")


def _finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number is not allowed: {value}")
    return parsed


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    rendered: dict[str, Any] = {}
    for key, value in pairs:
        if key in rendered:
            raise ValueError(f"duplicate JSON object key is not allowed: {key}")
        rendered[key] = value
    return rendered


def _parse_draft_output(raw_output: str) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        payload = json.loads(
            raw_output,
            parse_constant=_reject_json_constant,
            parse_float=_finite_json_float,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        return None, [f"draft output is not strict finite JSON: {exc}"]
    if not isinstance(payload, dict):
        return None, ["draft output root must be an object"]
    return payload, []


def _factual_number_allowlist(context: Mapping[str, Any]) -> set[str]:
    """Digits from factual fields a draft may express only (BD-06).

    Deliberately excludes IDs, timestamps, versions, and bookkeeping: the
    allowlist covers Claim values/validity/scope and official entity names.
    """

    factual: list[Any] = []
    for claim in context["claims"]:
        factual.append(
            {
                "value": claim["value"],
                "validity": claim["validity"],
                "scope": claim["scope"],
            }
        )
    for entity in context["entities"]:
        factual.append({"names": entity["names"]})
    rendered = _canonical_json(factual)
    return {
        token.translate(_ARABIC_INDIC) for token in _DIGIT_RUN.findall(rendered)
    }


def _terminology_violations(
    prose_en: str, prose_ar: str, terms: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    en_folded = prose_en.casefold()
    for term in terms:
        en_used = str(term["en"]).casefold() in en_folded
        ar_used = str(term["ar"]) in prose_ar
        if en_used and not ar_used:
            errors.append(
                f"unit uses registry term {term['term_id']} in English prose without the "
                "registry Arabic rendering"
            )
        if ar_used and not en_used:
            errors.append(
                f"unit uses registry term {term['term_id']} in Arabic prose without the "
                "registry English rendering"
            )
    return errors


def build_bilingual_draft_run(
    *,
    context: Mapping[str, Any],
    terminology: Mapping[str, Any],
    model_trace: DraftModelTrace,
    invoke: Callable[[str], str],
    clock: Callable[[], str] = _utc_now,
) -> dict[str, Any]:
    """Convert exact model output into a candidate-only bilingual draft run.

    The context is independently re-validated (schema plus builder invariants)
    before invocation; the invoker receives exactly the canonical serialization
    of the context; the registry is bound by version AND digest; every unit's
    evidence must close over its cited claims specifically; claims are
    accounted exactly once; unknowns are preserved by exact deterministic reuse
    of the pre-written bilingual statements; and both accepted and rejected
    runs are schema-validated, carrying the raw-output hash.
    """

    validate_drafting_context(context)

    registry = load_terminology(terminology)
    if registry["version"] != context["terminology_version"]:
        raise BilingualDraftingError(
            "terminology registry version does not match the drafting context"
        )
    digest = terminology_digest(registry)
    if digest != context["terminology_sha256"]:
        raise BilingualDraftingError(
            "terminology registry bytes do not match the context terminology_sha256"
        )

    context_json = _canonical_json(dict(context))
    input_context_sha256 = _sha256_text(context_json)
    trace = model_trace.as_dict()

    allowed_numbers = _factual_number_allowlist(context)
    claim_evidence = {
        str(item["claim_id"]): {str(eid) for eid in item["evidence_ids"]}
        for item in context["claims"]
    }
    claim_ids = set(claim_evidence)
    unknown_by_id = {
        str(item["unknown_id"]): item for item in context["unknowns"]
    }

    started_at = clock()
    raw_output = invoke(context_json)
    completed_at = clock()
    if not isinstance(raw_output, str):
        raise BilingualDraftingError("draft invoker must return text")
    raw_output_sha256 = _sha256_text(raw_output)

    seed = {
        "drafting_context_id": context["id"],
        "input_context_sha256": input_context_sha256,
        "raw_output_sha256": raw_output_sha256,
        "model_trace": trace,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    run = {
        "id": _stable_id("SDA-AIDRAFT", seed),
        "drafting_context_id": context["id"],
        "started_at": started_at,
        "completed_at": completed_at,
        "model_trace": trace,
        "input_context_sha256": input_context_sha256,
        "raw_output_sha256": raw_output_sha256,
        "adapter_version": ADAPTER_VERSION,
        "authority": {
            "mode": "candidate_only",
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }

    def rejected(errors: list[str]) -> dict[str, Any]:
        rendered = [str(error)[:512] for error in errors if str(error)] or [
            "draft output rejected"
        ]
        candidate = {
            **run,
            "validation": {"status": "rejected", "errors": rendered},
            "units": [],
            "undrafted_claim_ids": [],
            "unknowns_rendered": [],
            "omitted_unknown_ids": [],
        }
        schema_errors = [error.message for error in _RUN_VALIDATOR.iter_errors(candidate)]
        if schema_errors:
            raise BilingualDraftingError(
                f"rejected draft run is schema-invalid: {schema_errors[0]}"
            )
        return candidate

    payload, errors = _parse_draft_output(raw_output)
    if errors:
        return rejected(errors)

    expected_keys = {"units", "undrafted_claim_ids", "rendered_unknown_ids", "omitted_unknown_ids"}
    unexpected = sorted(set(payload) - expected_keys)
    missing = sorted(expected_keys - set(payload))
    if unexpected or missing:
        return rejected(
            [
                f"draft output carries unsupported keys: {', '.join(unexpected)}"
                if unexpected
                else f"draft output missing keys: {', '.join(missing)}"
            ]
        )

    units = payload.get("units")
    if not isinstance(units, list):
        return rejected(["draft output units must be an array"])

    seen_unit_ids: set[str] = set()
    claim_use_count: dict[str, int] = {}
    unit_errors: list[str] = []
    accepted_units: list[dict[str, Any]] = []
    for unit in units:
        if not isinstance(unit, Mapping):
            unit_errors.append("draft unit must be an object")
            continue
        unit_keys = set(unit)
        if unit_keys != {"unit_id", "claim_ids", "evidence_ids", "prose"}:
            unit_errors.append(
                f"draft unit carries keys outside unit_id/claim_ids/evidence_ids/prose: "
                f"{sorted(unit_keys)}"
            )
            continue
        unit_id = unit.get("unit_id")
        if not isinstance(unit_id, str) or not unit_id.startswith("UNIT-"):
            unit_errors.append(f"draft unit requires a UNIT-* identity, got {unit_id!r}")
            continue
        if unit_id in seen_unit_ids:
            unit_errors.append(f"duplicate draft unit identity: {unit_id}")
            continue
        seen_unit_ids.add(unit_id)

        unit_claims = unit.get("claim_ids")
        if (
            not isinstance(unit_claims, list)
            or not unit_claims
            or len(unit_claims) != len(set(unit_claims))
        ):
            unit_errors.append(f"unit {unit_id} requires a non-empty unique claim_ids array")
            continue
        for claim_id in unit_claims:
            if claim_id not in claim_ids:
                unit_errors.append(
                    f"unit {unit_id} references claim {claim_id!r} outside the approved context"
                )
            else:
                claim_use_count[claim_id] = claim_use_count.get(claim_id, 0) + 1
        unit_evidence = unit.get("evidence_ids")
        if (
            not isinstance(unit_evidence, list)
            or not unit_evidence
            or len(unit_evidence) != len(set(unit_evidence))
        ):
            unit_errors.append(f"unit {unit_id} requires a non-empty unique evidence_ids array")
            continue
        cited_evidence = {
            evidence_id
            for claim_id in unit_claims
            if claim_id in claim_evidence
            for evidence_id in claim_evidence[claim_id]
        }
        for evidence_id in unit_evidence:
            if evidence_id not in cited_evidence:
                unit_errors.append(
                    f"unit {unit_id} cites evidence {evidence_id!r} that does not support any "
                    "of the unit's claims (claim-specific support closure)"
                )
        prose = unit.get("prose")
        if not isinstance(prose, Mapping) or set(prose) != {"en", "ar"}:
            unit_errors.append(f"unit {unit_id} requires exactly en and ar prose")
            continue
        prose_en = prose.get("en")
        prose_ar = prose.get("ar")
        if not isinstance(prose_en, str) or not prose_en.strip():
            unit_errors.append(f"unit {unit_id} requires non-empty English prose")
            continue
        if not isinstance(prose_ar, str) or not prose_ar.strip():
            unit_errors.append(f"unit {unit_id} requires non-empty Arabic prose")
            continue
        unit_errors.extend(_terminology_violations(prose_en, prose_ar, registry["terms"]))
        _restricted_in_text(f"unit {unit_id} English prose", prose_en, unit_errors)
        _restricted_in_text(f"unit {unit_id} Arabic prose", prose_ar, unit_errors)
        for text in (prose_en, prose_ar.translate(_ARABIC_INDIC)):
            for token in _DIGIT_RUN.findall(text):
                if token not in allowed_numbers:
                    unit_errors.append(
                        f"unit {unit_id} prose carries a number not grounded in the "
                        f"context's factual fields: {token}"
                    )
        accepted_units.append(dict(unit))

    rendered_ids = payload.get("rendered_unknown_ids")
    if not isinstance(rendered_ids, list) or len(rendered_ids) != len(set(rendered_ids)):
        return rejected(
            unit_errors or ["draft output rendered_unknown_ids must be a unique array"]
        )
    for unknown_id in rendered_ids:
        if unknown_id not in unknown_by_id:
            unit_errors.append(
                f"rendered unknown {unknown_id!r} is outside the approved context"
            )

    omitted = payload.get("omitted_unknown_ids")
    if not isinstance(omitted, list) or len(omitted) != len(set(omitted)):
        return rejected(unit_errors or ["draft output omitted_unknown_ids must be a unique array"])
    for unknown_id in omitted:
        if unknown_id not in unknown_by_id:
            unit_errors.append(
                f"omitted unknown {unknown_id!r} is outside the approved context"
            )
        if unknown_id in rendered_ids:
            unit_errors.append(f"unknown {unknown_id} is both rendered and omitted")

    if unit_errors:
        return rejected(unit_errors)

    undrafted = payload.get("undrafted_claim_ids")
    if not isinstance(undrafted, list) or len(undrafted) != len(set(undrafted)):
        return rejected(["draft output undrafted_claim_ids must be a unique array"])
    for claim_id in undrafted:
        if claim_id not in claim_ids:
            return rejected(
                [f"undrafted claim {claim_id!r} is outside the approved context"]
            )
        if claim_use_count.get(claim_id, 0) > 0:
            return rejected(
                [
                    f"claim {claim_id} is both drafted in a unit and listed as undrafted "
                    "(claims must be accounted exactly once)"
                ]
            )
    double_drafts = sorted(
        claim_id for claim_id, count in claim_use_count.items() if count > 1
    )
    if double_drafts:
        return rejected(
            [
                "claims must be drafted in exactly one unit; duplicated: "
                f"{', '.join(double_drafts)}"
            ]
        )
    accounted = set(undrafted) | set(claim_use_count)
    if accounted != claim_ids:
        return rejected(
            [
                "draft output does not account for every approved claim: "
                f"{sorted(claim_ids - accounted)} missing"
            ]
        )

    unknown_accounted = set(rendered_ids) | set(omitted)
    if unknown_accounted != set(unknown_by_id):
        return rejected(
            [
                "draft output does not account for every context unknown: "
                f"{sorted(set(unknown_by_id) - unknown_accounted)} missing"
            ]
        )

    # Unknown meaning is preserved by exact deterministic reuse of the
    # pre-written bilingual statements (BD-05): the model only selects whether
    # an unknown is rendered; it never authors unknown prose.
    unknowns_rendered = [
        {
            "unknown_id": unknown_id,
            "prose": {
                "en": unknown_by_id[unknown_id]["statement_en"],
                "ar": unknown_by_id[unknown_id]["statement_ar"],
            },
        }
        for unknown_id in sorted(rendered_ids)
    ]

    accepted = {
        **run,
        "validation": {"status": "accepted_for_editorial_review", "errors": []},
        "units": accepted_units,
        "undrafted_claim_ids": sorted(undrafted),
        "unknowns_rendered": unknowns_rendered,
        "omitted_unknown_ids": sorted(omitted),
    }
    schema_errors = [error.message for error in _RUN_VALIDATOR.iter_errors(accepted)]
    if schema_errors:
        return rejected(
            [f"accepted draft failed runtime schema validation: {schema_errors[0]}"]
        )
    return accepted
