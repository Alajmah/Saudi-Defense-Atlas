"""Bounded bilingual drafting projection for M4.

Architecture rule: the model drafts language; it does not choose facts. A
deterministic :func:`build_approved_drafting_context` first selects only
already-approved canonical Claims, their Evidence references, resolved
Entities with official bilingual names, explicit unknown statements, and the
project-owned terminology registry version. Only that bounded object reaches
the drafting adapter. The adapter sends exactly the canonical serialization of
the context as model input, converts the response into a candidate-only
``AI bilingual draft run`` with one shared support set per factual unit, and
owns no truth, canonical-mutation, or publication authority.

Unresolved factual conflicts fail closed: no conflict-aware synthesis is
attempted in this version.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

ADAPTER_VERSION = "m4-bilingual-drafting-v0.1"

RESTRICTED_PROSE_MARKERS = (
    "readiness",
    "patrol",
    "stock level",
    "stock levels",
    "live unit",
    "operational tempo",
    "ammunition stock",
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
        en_key = str(term["en"]).casefold()
        if en_key in seen_en:
            raise BilingualDraftingError(
                f"terminology registry carries two terms with the same English rendering: {en_key!r}"
            )
        seen_en.add(en_key)
    return {"version": version, "terms": [dict(term) for term in terms]}


def _require_active(record: Mapping[str, Any], label: str) -> None:
    status = record.get("record_status", "active")
    if status != "active":
        raise BilingualDraftingError(f"{label} is not an active canonical record")


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

    Fails closed on: candidate or non-canonical identities, unapproved claim
    state, disputed claims, conflicting active claims on the same
    subject/predicate, entities without official bilingual names in both
    locales, evidence references that do not resolve, and non-active records.
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
        if entity_id.startswith("SDA-CLAIM-") or entity_id.startswith("CAND-"):
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

    context_id = _stable_id(
        "SDA-DRAFTCTX",
        sorted(entity_by_id),
        sorted(prepared_claims),
        sorted(evidence_by_id),
        [item["unknown_id"] for item in prepared_unknowns],
        registry["version"],
        created_at,
    )
    return {
        "id": context_id,
        "created_at": created_at,
        "terminology_version": registry["version"],
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


def _prose_number_violations(prose_en: str, prose_ar: str, allowed: set[str]) -> list[str]:
    violations: list[str] = []
    for text in (prose_en, prose_ar.translate(_ARABIC_INDIC)):
        for token in _DIGIT_RUN.findall(text):
            if token not in allowed:
                violations.append(f"prose carries a number not grounded in the context: {token}")
    return violations


def _terminology_violations(
    prose_en: str, prose_ar: str, terms: list[dict[str, Any]]
) -> list[str]:
    errors: list[str] = []
    en_folded = prose_en.casefold()
    ar_text = prose_ar
    for term in terms:
        en_used = str(term["en"]).casefold() in en_folded
        ar_used = str(term["ar"]) in ar_text
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


def _restricted_detail_violations(prose_en: str, prose_ar: str) -> list[str]:
    errors: list[str] = []
    for label, text in (("en", prose_en), ("ar", prose_ar)):
        folded = text.casefold()
        for marker in RESTRICTED_PROSE_MARKERS:
            if marker in folded:
                errors.append(
                    f"{label} prose carries restricted operational detail marker: {marker}"
                )
        if RESTRICTED_COORDINATE_PATTERN.search(text):
            errors.append(
                f"{label} prose carries an uncoarsened coordinate-like number"
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

    The invoker receives exactly the canonical serialization of the approved
    drafting context - nothing else - and the run records the SHA-256 of that
    serialization. Any violation rejects the run and clears all drafted text.
    """

    authority = context.get("authority")
    if not isinstance(authority, Mapping) or authority.get("mode") != "approved_canonical_read_only":
        raise BilingualDraftingError("drafting requires an approved read-only context")
    if (
        authority.get("canonical_mutation_authority") is not False
        or authority.get("publication_authority") is not False
    ):
        raise BilingualDraftingError("drafting context exceeded read-only authority")
    if context.get("conflicts") != []:
        raise BilingualDraftingError(
            "drafting context carries unresolved conflicts; drafting fails closed"
        )

    context_json = _canonical_json(dict(context))
    input_context_sha256 = _sha256_text(context_json)
    trace = model_trace.as_dict()

    allowed_numbers = {
        token.translate(_ARABIC_INDIC) for token in _DIGIT_RUN.findall(context_json)
    }
    claim_ids = {
        str(item["claim_id"]) for item in context.get("claims", []) if isinstance(item, Mapping)
    }
    evidence_ids = {
        str(item["evidence_id"]) for item in context.get("evidence", []) if isinstance(item, Mapping)
    }
    unknown_ids = {
        str(item["unknown_id"]) for item in context.get("unknowns", []) if isinstance(item, Mapping)
    }
    registry = load_terminology(terminology)
    if registry["version"] != context.get("terminology_version"):
        raise BilingualDraftingError(
            "terminology registry version does not match the drafting context"
        )
    terminology_terms = registry["terms"]

    started_at = clock()
    raw_output = invoke(context_json)
    completed_at = clock()
    if not isinstance(raw_output, str):
        raise BilingualDraftingError("draft invoker must return text")

    seed = {
        "drafting_context_id": context.get("id"),
        "input_context_sha256": input_context_sha256,
        "model_trace": trace,
        "started_at": started_at,
        "completed_at": completed_at,
    }
    run = {
        "id": _stable_id("SDA-AIDRAFT", seed),
        "drafting_context_id": context.get("id"),
        "started_at": started_at,
        "completed_at": completed_at,
        "model_trace": trace,
        "input_context_sha256": input_context_sha256,
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
        return {
            **run,
            "validation": {"status": "rejected", "errors": rendered},
            "units": [],
            "undrafted_claim_ids": [],
            "unknowns_rendered": [],
            "omitted_unknown_ids": [],
        }

    payload, errors = _parse_draft_output(raw_output)
    if errors:
        return rejected(errors)

    expected_keys = {"units", "undrafted_claim_ids", "unknowns_rendered", "omitted_unknown_ids"}
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
    drafted_claims: set[str] = set()
    unit_errors: list[str] = []
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
        unit_evidence = unit.get("evidence_ids")
        if (
            not isinstance(unit_evidence, list)
            or not unit_evidence
            or len(unit_evidence) != len(set(unit_evidence))
        ):
            unit_errors.append(f"unit {unit_id} requires a non-empty unique evidence_ids array")
            continue
        for evidence_id in unit_evidence:
            if evidence_id not in evidence_ids:
                unit_errors.append(
                    f"unit {unit_id} cites evidence {evidence_id!r} outside the approved context "
                    "(orphaned citation)"
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
        unit_errors.extend(_terminology_violations(prose_en, prose_ar, terminology_terms))
        unit_errors.extend(_restricted_detail_violations(prose_en, prose_ar))
        unit_errors.extend(_prose_number_violations(prose_en, prose_ar, allowed_numbers))
        drafted_claims.update(claim_id for claim_id in unit_claims if claim_id in claim_ids)

    rendered_unknowns = payload.get("unknowns_rendered")
    if not isinstance(rendered_unknowns, list):
        return rejected(unit_errors or ["draft output unknowns_rendered must be an array"])
    rendered_ids: set[str] = set()
    for item in rendered_unknowns:
        if not isinstance(item, Mapping) or set(item) != {"unknown_id", "prose"}:
            unit_errors.append("rendered unknown requires exactly unknown_id and prose")
            continue
        unknown_id = item.get("unknown_id")
        if unknown_id not in unknown_ids:
            unit_errors.append(
                f"rendered unknown {unknown_id!r} is outside the approved context"
            )
            continue
        if unknown_id in rendered_ids:
            unit_errors.append(f"duplicate rendered unknown: {unknown_id}")
            continue
        rendered_ids.add(unknown_id)
        prose = item.get("prose")
        if not isinstance(prose, Mapping) or set(prose) != {"en", "ar"}:
            unit_errors.append(f"rendered unknown {unknown_id} requires exactly en and ar prose")
            continue
        for locale in ("en", "ar"):
            text = prose.get(locale)
            if not isinstance(text, str) or not text.strip():
                unit_errors.append(
                    f"rendered unknown {unknown_id} requires non-empty {locale} prose"
                )
        prose_en = prose.get("en") if isinstance(prose.get("en"), str) else ""
        prose_ar = prose.get("ar") if isinstance(prose.get("ar"), str) else ""
        unit_errors.extend(_restricted_detail_violations(prose_en, prose_ar))
        unit_errors.extend(_prose_number_violations(prose_en, prose_ar, allowed_numbers))

    omitted = payload.get("omitted_unknown_ids")
    if not isinstance(omitted, list) or len(omitted) != len(set(omitted)):
        return rejected(unit_errors or ["draft output omitted_unknown_ids must be a unique array"])
    for unknown_id in omitted:
        if unknown_id not in unknown_ids:
            unit_errors.append(
                f"omitted unknown {unknown_id!r} is outside the approved context"
            )
        if unknown_id in rendered_ids:
            unit_errors.append(
                f"unknown {unknown_id} is both rendered and omitted"
            )

    if unit_errors:
        return rejected(unit_errors)

    undrafted_claim_ids = payload.get("undrafted_claim_ids")
    if not isinstance(undrafted_claim_ids, list):
        return rejected(["draft output undrafted_claim_ids must be an array"])
    for claim_id in undrafted_claim_ids:
        if claim_id not in claim_ids:
            return rejected(
                [f"undrafted claim {claim_id!r} is outside the approved context"]
            )
    accounted = set(undrafted_claim_ids) | drafted_claims
    if accounted != claim_ids:
        return rejected(
            [
                "draft output does not account for every approved claim: "
                f"{sorted(claim_ids - accounted)} missing"
            ]
        )

    omitted_accounted = rendered_ids | set(omitted)
    if omitted_accounted != unknown_ids:
        return rejected(
            [
                "draft output does not account for every context unknown: "
                f"{sorted(unknown_ids - omitted_accounted)} missing"
            ]
        )

    return {
        **run,
        "validation": {"status": "accepted_for_editorial_review", "errors": []},
        "units": [dict(unit) for unit in units],
        "undrafted_claim_ids": sorted(undrafted_claim_ids),
        "unknowns_rendered": [dict(item) for item in rendered_unknowns],
        "omitted_unknown_ids": sorted(omitted),
    }

