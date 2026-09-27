"""Backend-neutral public map projection for fixed, non-operational facilities.

This module intentionally has no movement/event input. It projects only explicitly
allowlisted fixed-facility Entity records plus approved public-location Claims.
Coordinates are coarsened to two decimal places before entering the public view.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from .projection_support import ProjectionError, index_by_id, render_citations

_LATITUDE = "facility.public_latitude"
_LONGITUDE = "facility.public_longitude"
_LOCATION_LABEL = "facility.public_location_label"
_ASSOCIATED_ORG = "facility.associated_with.organization"

_ALLOWED_CATEGORIES = {
    "air_base",
    "naval_base",
    "military_city",
    "training_center",
    "military_education",
    "defense_industry_facility",
    "administrative_facility",
}
_ALLOWED_CONFIDENCE = {"verified", "high"}
_BACKEND_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])")


def _utc(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ProjectionError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ProjectionError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise ProjectionError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _number_claim_value(claim: Mapping[str, Any], label: str) -> float:
    value = claim.get("value")
    if not isinstance(value, Mapping) or value.get("kind") != "number":
        raise ProjectionError(f"{label} must use a numeric Claim value")
    raw = value.get("value")
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise ProjectionError(f"{label} requires numeric value")
    return float(raw)


def _coarsen(value: float) -> float:
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _eligible_claims(
    claims: Sequence[Mapping[str, Any]],
    entity_id: str,
    predicate: str,
    *,
    fail_on_disputed: bool,
) -> list[Mapping[str, Any]]:
    result: list[Mapping[str, Any]] = []
    for claim in claims:
        if claim.get("subject_id") != entity_id or claim.get("predicate_id") != predicate:
            continue
        state = claim.get("claim_state")
        if state == "disputed":
            if fail_on_disputed:
                raise ProjectionError(
                    f"facility {entity_id} has disputed public-location Claim {claim.get('id')}"
                )
            # Optional metadata cannot make an otherwise safe fixed-facility
            # coordinate feature disappear merely because that metadata is disputed.
            continue
        if state != "active":
            continue
        if claim.get("confidence") not in _ALLOWED_CONFIDENCE:
            continue
        result.append(claim)
    return result


def _single_coordinate_claim(
    claims: Sequence[Mapping[str, Any]], entity_id: str, predicate: str
) -> Mapping[str, Any] | None:
    eligible = _eligible_claims(
        claims,
        entity_id,
        predicate,
        fail_on_disputed=True,
    )
    if not eligible:
        return None
    if len(eligible) != 1:
        raise ProjectionError(
            f"facility {entity_id} requires exactly one eligible {predicate} Claim"
        )
    return eligible[0]


def _localized_location_label(
    claims: Sequence[Mapping[str, Any]],
    entity_id: str,
    *,
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[dict[str, str] | None, list[dict[str, Any]], list[str]]:
    labels: dict[str, str] = {}
    citations: list[dict[str, Any]] = []
    claim_ids: list[str] = []
    for claim in _eligible_claims(
        claims,
        entity_id,
        _LOCATION_LABEL,
        fail_on_disputed=False,
    ):
        value = claim.get("value")
        if not isinstance(value, Mapping) or value.get("kind") != "string":
            raise ProjectionError("public location label must use string Claim value")
        text = value.get("value")
        language = value.get("language")
        if not isinstance(text, str) or not text:
            raise ProjectionError("public location label requires non-empty text")
        if language not in {"ar", "en"}:
            raise ProjectionError("public location label language must be ar or en")
        if language in labels and labels[language] != text:
            raise ProjectionError(
                f"facility {entity_id} has conflicting public location labels for {language}"
            )
        labels[language] = text
        claim_id = claim.get("id")
        if isinstance(claim_id, str):
            claim_ids.append(claim_id)
        citations.extend(
            render_citations(
                claim.get("evidence_links"),
                evidence_by_id=evidence_by_id,
                documents_by_id=documents_by_id,
                sources_by_id=sources_by_id,
            )
        )
    return (labels or None, citations, claim_ids)


def _associated_organizations(
    claims: Sequence[Mapping[str, Any]],
    entity_id: str,
    *,
    entity_by_id: Mapping[str, Mapping[str, Any]],
    evidence_by_id: Mapping[str, Mapping[str, Any]],
    documents_by_id: Mapping[str, Mapping[str, Any]],
    sources_by_id: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[dict[str, Any]], list[str]]:
    organization_ids: set[str] = set()
    citations: list[dict[str, Any]] = []
    claim_ids: list[str] = []
    for claim in _eligible_claims(
        claims,
        entity_id,
        _ASSOCIATED_ORG,
        fail_on_disputed=False,
    ):
        value = claim.get("value")
        if not isinstance(value, Mapping) or value.get("kind") != "entity":
            raise ProjectionError("facility association must use entity Claim value")
        organization_id = value.get("entity_id")
        if not isinstance(organization_id, str) or not organization_id:
            raise ProjectionError("facility association requires organization ID")
        organization = entity_by_id.get(organization_id)
        if (
            not isinstance(organization, Mapping)
            or organization.get("entity_type") != "organization"
            or organization.get("record_status") != "active"
        ):
            raise ProjectionError(
                f"facility association target {organization_id!r} must resolve to an active organization Entity"
            )
        organization_ids.add(organization_id)
        claim_id = claim.get("id")
        if isinstance(claim_id, str):
            claim_ids.append(claim_id)
        citations.extend(
            render_citations(
                claim.get("evidence_links"),
                evidence_by_id=evidence_by_id,
                documents_by_id=documents_by_id,
                sources_by_id=sources_by_id,
            )
        )
    return sorted(organization_ids), citations, claim_ids


def _dedupe_citations(citations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for citation in citations:
        key = (str(citation["evidence_id"]), str(citation["evidence_role"]))
        deduped[key] = dict(citation)
    return [deduped[key] for key in sorted(deduped)]


def _assert_no_backend_ids(value: Any) -> None:
    if _BACKEND_ID_RE.search(repr(value)):
        raise ProjectionError("backend Q/P identifier leaked into public map projection")


def build_public_map_view(
    *,
    entities: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
    evidence: Sequence[Mapping[str, Any]],
    documents: Sequence[Mapping[str, Any]],
    sources: Sequence[Mapping[str, Any]],
    projected_at: str,
    revision_ids: Sequence[str] = (),
) -> dict[str, Any]:
    """Build a cited, coarse public map view from canonical SDA records."""

    entity_by_id = index_by_id(entities, "Entity")
    evidence_by_id = index_by_id(evidence, "Evidence")
    documents_by_id = index_by_id(documents, "Document")
    sources_by_id = index_by_id(sources, "Source")
    projected = _utc(projected_at, "projected_at")

    # Location predicates are valid only for facility entities. A malformed
    # subject is a publication error rather than something to silently reinterpret.
    for claim in claims:
        if claim.get("predicate_id") not in {_LATITUDE, _LONGITUDE, _LOCATION_LABEL}:
            continue
        subject_id = claim.get("subject_id")
        subject = entity_by_id.get(subject_id) if isinstance(subject_id, str) else None
        if not isinstance(subject, Mapping) or subject.get("entity_type") != "facility":
            raise ProjectionError("public facility-location Claim has non-facility subject")

    features: list[dict[str, Any]] = []
    record_ids: set[str] = set()

    for entity_id in sorted(entity_by_id):
        entity = entity_by_id[entity_id]
        if entity.get("entity_type") != "facility" or entity.get("record_status") != "active":
            continue
        category = entity.get("subtype")
        if category not in _ALLOWED_CATEGORIES:
            continue
        names = entity.get("names")
        if not isinstance(names, Mapping) or not names:
            raise ProjectionError(f"facility {entity_id} requires public names")

        latitude_claim = _single_coordinate_claim(claims, entity_id, _LATITUDE)
        longitude_claim = _single_coordinate_claim(claims, entity_id, _LONGITUDE)
        if latitude_claim is None and longitude_claim is None:
            continue
        if latitude_claim is None or longitude_claim is None:
            raise ProjectionError(f"facility {entity_id} has incomplete public coordinate pair")

        latitude = _number_claim_value(latitude_claim, "public latitude")
        longitude = _number_claim_value(longitude_claim, "public longitude")
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ProjectionError(f"facility {entity_id} coordinate out of range")

        coordinate_citations: list[dict[str, Any]] = []
        coordinate_claim_ids: list[str] = []
        for claim in (latitude_claim, longitude_claim):
            claim_id = claim.get("id")
            if not isinstance(claim_id, str) or not claim_id:
                raise ProjectionError("coordinate Claim requires canonical ID")
            coordinate_claim_ids.append(claim_id)
            coordinate_citations.extend(
                render_citations(
                    claim.get("evidence_links"),
                    evidence_by_id=evidence_by_id,
                    documents_by_id=documents_by_id,
                    sources_by_id=sources_by_id,
                )
            )

        location_label, label_citations, label_claim_ids = _localized_location_label(
            claims,
            entity_id,
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )
        organization_ids, org_citations, org_claim_ids = _associated_organizations(
            claims,
            entity_id,
            entity_by_id=entity_by_id,
            evidence_by_id=evidence_by_id,
            documents_by_id=documents_by_id,
            sources_by_id=sources_by_id,
        )

        all_citations = _dedupe_citations(
            [*coordinate_citations, *label_citations, *org_citations]
        )
        feature = {
            "id": f"SDA-MAP-{entity_id.removeprefix('SDA-')}",
            "entity_id": entity_id,
            "entity_type": "facility",
            "category": category,
            "names": dict(names),
            "location_label": location_label,
            "coordinate": {
                "latitude": _coarsen(latitude),
                "longitude": _coarsen(longitude),
                "precision_class": "coarsened_2dp",
                "publication_policy": "fixed_public_reference_only",
            },
            "coordinate_claim_ids": sorted(coordinate_claim_ids),
            "associated_organization_ids": organization_ids,
            "citations": all_citations,
        }
        _assert_no_backend_ids(feature)
        features.append(feature)
        record_ids.add(entity_id)
        record_ids.update(coordinate_claim_ids)
        record_ids.update(label_claim_ids)
        record_ids.update(org_claim_ids)
        for citation in all_citations:
            record_ids.update(
                {
                    citation["evidence_id"],
                    citation["document_id"],
                    citation["source_id"],
                }
            )

    view = {
        "scope": "public_non_operational_fixed_facilities",
        "projected_at": projected,
        "features": features,
        "provenance": {
            "record_ids": sorted(record_ids),
            "revision_ids": sorted(set(revision_ids)),
        },
    }
    _assert_no_backend_ids(view)
    return view
