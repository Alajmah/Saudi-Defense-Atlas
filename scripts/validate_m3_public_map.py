#!/usr/bin/env python3
"""Validate the M3 public non-operational fixed-facility map contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.presentation.public_map import build_public_map_view  # noqa: E402
from services.presentation.projection_support import ProjectionError  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except ProjectionError:
        return
    failures.append(f"{label} did not fail closed")


def validate_instance(schema_name: str, instance: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(
            f"{schema_name} failed: " + "; ".join(error.message for error in errors)
        )


def entity(entity_id: str, entity_type: str, *, subtype: str | None, names: dict[str, str]) -> dict[str, Any]:
    return {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": subtype,
        "names": names,
        "aliases": [],
        "external_identifiers": [],
        "backend_identifiers": [{"backend": "wikibase", "value": "Q999"}],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
    }


def claim(
    claim_id: str,
    subject_id: str,
    predicate_id: str,
    value: dict[str, Any],
    *,
    evidence_id: str = "SDA-EVID-MAP",
    role: str = "supports",
    confidence: str = "verified",
    state: str = "active",
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "subject_id": subject_id,
        "predicate_id": predicate_id,
        "value": value,
        "confidence": confidence,
        "evidence_links": [{"evidence_id": evidence_id, "role": role}],
        "claim_state": state,
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-03T00:00:00Z",
        "created_at": "2026-01-03T00:00:00Z",
    }


def fixtures() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    facilities = [
        entity(
            "SDA-FAC-MAP-TEST",
            "facility",
            subtype="air_base",
            names={"ar": "منشأة اختبار عامة", "en": "Public Test Facility"},
        ),
        entity(
            "SDA-FAC-RESTRICTED-TEST",
            "facility",
            subtype="air_defense_site",
            names={"en": "Restricted Subtype Fixture"},
        ),
        entity(
            "SDA-ORG-RSAF",
            "organization",
            subtype=None,
            names={"ar": "القوات الجوية الملكية السعودية", "en": "Royal Saudi Air Force"},
        ),
    ]
    claims = [
        claim(
            "SDA-CLAIM-MAP-LAT",
            "SDA-FAC-MAP-TEST",
            "facility.public_latitude",
            {"kind": "number", "value": 24.7136, "unit": "degrees", "precision": "source", "lower_bound": None, "upper_bound": None},
        ),
        claim(
            "SDA-CLAIM-MAP-LON",
            "SDA-FAC-MAP-TEST",
            "facility.public_longitude",
            {"kind": "number", "value": 46.6753, "unit": "degrees", "precision": "source", "lower_bound": None, "upper_bound": None},
        ),
        claim(
            "SDA-CLAIM-MAP-LABEL-EN",
            "SDA-FAC-MAP-TEST",
            "facility.public_location_label",
            {"kind": "string", "value": "Riyadh area", "language": "en"},
        ),
        claim(
            "SDA-CLAIM-MAP-LABEL-AR",
            "SDA-FAC-MAP-TEST",
            "facility.public_location_label",
            {"kind": "string", "value": "منطقة الرياض", "language": "ar"},
        ),
        claim(
            "SDA-CLAIM-MAP-ASSOC",
            "SDA-FAC-MAP-TEST",
            "facility.associated_with.organization",
            {"kind": "entity", "entity_id": "SDA-ORG-RSAF"},
        ),
        # A non-allowlisted fixed/public-location-shaped record must not become a map feature.
        claim(
            "SDA-CLAIM-RESTRICTED-LAT",
            "SDA-FAC-RESTRICTED-TEST",
            "facility.public_latitude",
            {"kind": "number", "value": 25.1111, "unit": "degrees", "precision": "source", "lower_bound": None, "upper_bound": None},
        ),
        claim(
            "SDA-CLAIM-RESTRICTED-LON",
            "SDA-FAC-RESTRICTED-TEST",
            "facility.public_longitude",
            {"kind": "number", "value": 47.2222, "unit": "degrees", "precision": "source", "lower_bound": None, "upper_bound": None},
        ),
    ]
    evidence = [
        {
            "id": "SDA-EVID-MAP",
            "document_id": "SDA-DOC-MAP",
            "locator": {"section": "public location"},
            "excerpt": None,
            "excerpt_sha256": None,
            "language": "en",
            "captured_at": "2026-01-03T00:00:00Z",
            "capture_method": "human",
            "notes": None,
        }
    ]
    documents = [
        {
            "id": "SDA-DOC-MAP",
            "source_id": "SDA-SOURCE-MAP",
            "title": {"en": "Public facility reference"},
            "canonical_url": "https://example.gov.test/public-facility",
            "retrieved_url": None,
            "archival_url": None,
            "published_at": {"value": "2026-01-01", "precision": "day"},
            "retrieved_at": "2026-01-02T00:00:00Z",
            "language": "en",
            "document_type": "official_statement",
            "media_type": "text/html",
            "content_sha256": "a" * 64,
            "content_length_bytes": 100,
            "version_of": None,
            "publisher_document_id": None,
            "access_notes": None,
            "licensing_notes": None,
        }
    ]
    sources = [
        {
            "id": "SDA-SOURCE-MAP",
            "publisher": {"en": "Official Test Authority"},
            "source_class": "A",
            "publisher_type": "government",
            "homepage": "https://example.gov.test/",
            "jurisdiction": "Saudi Arabia",
            "notes": None,
            "active": True,
        }
    ]
    return facilities, claims, evidence, documents, sources


def build(
    entities: list[dict[str, Any]],
    claims: list[dict[str, Any]],
    evidence: list[dict[str, Any]],
    documents: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    return build_public_map_view(
        entities=entities,
        claims=claims,
        evidence=evidence,
        documents=documents,
        sources=sources,
        projected_at="2026-01-04T00:00:00Z",
        revision_ids=["SDA-REV-MAP-TEST"],
    )


def main() -> int:
    failures: list[str] = []
    entities, claims, evidence, documents, sources = fixtures()

    for item in entities:
        validate_instance("entity.schema.json", item, failures)
    for item in claims:
        validate_instance("claim.schema.json", item, failures)
    for item in evidence:
        validate_instance("evidence.schema.json", item, failures)
    for item in documents:
        validate_instance("document.schema.json", item, failures)
    for item in sources:
        validate_instance("source.schema.json", item, failures)

    view = build(entities, claims, evidence, documents, sources)
    validate_instance("public-map-view.schema.json", view, failures)

    expect(view["scope"] == "public_non_operational_fixed_facilities", "map scope changed", failures)
    expect(len(view["features"]) == 1, "restricted subtype leaked into public map", failures)
    feature = view["features"][0]
    expect(feature["entity_id"] == "SDA-FAC-MAP-TEST", "wrong map entity", failures)
    expect(feature["coordinate"]["latitude"] == 24.71, "latitude was not coarsened to 2dp", failures)
    expect(feature["coordinate"]["longitude"] == 46.68, "longitude was not coarsened to 2dp", failures)
    expect("24.7136" not in repr(view) and "46.6753" not in repr(view), "precise source coordinate leaked into public view", failures)
    expect("Q999" not in repr(view), "backend Wikibase ID leaked into public map", failures)
    expect(feature["location_label"] == {"ar": "منطقة الرياض", "en": "Riyadh area"}, "bilingual broad location label changed", failures)
    expect(feature["associated_organization_ids"] == ["SDA-ORG-RSAF"], "facility association missing", failures)
    expect(any(item["evidence_role"] == "supports" for item in feature["citations"]), "supporting Evidence missing", failures)

    incomplete = [item for item in claims if item["id"] != "SDA-CLAIM-MAP-LON"]
    expect_raises(
        "incomplete coordinate pair",
        lambda: build(entities, incomplete, evidence, documents, sources),
        failures,
    )

    duplicate = copy.deepcopy(claims)
    extra_lat = copy.deepcopy(claims[0])
    extra_lat["id"] = "SDA-CLAIM-MAP-LAT-2"
    extra_lat["value"]["value"] = 24.72
    duplicate.append(extra_lat)
    expect_raises(
        "duplicate eligible coordinate claim",
        lambda: build(entities, duplicate, evidence, documents, sources),
        failures,
    )

    disputed = copy.deepcopy(claims)
    disputed[0]["claim_state"] = "disputed"
    expect_raises(
        "disputed coordinate",
        lambda: build(entities, disputed, evidence, documents, sources),
        failures,
    )

    context_only = copy.deepcopy(claims)
    context_only[0]["evidence_links"][0]["role"] = "contextualizes"
    expect_raises(
        "coordinate without supporting Evidence",
        lambda: build(entities, context_only, evidence, documents, sources),
        failures,
    )

    weak = copy.deepcopy(claims)
    weak[0]["confidence"] = "medium"
    weak[1]["confidence"] = "medium"
    weak_view = build(entities, weak, evidence, documents, sources)
    expect(
        all(item["entity_id"] != "SDA-FAC-MAP-TEST" for item in weak_view["features"]),
        "medium-confidence coordinate claims were published",
        failures,
    )

    # Optional disputed metadata must not suppress an otherwise safe fixed-facility feature.
    disputed_label = copy.deepcopy(claims)
    disputed_label[2]["claim_state"] = "disputed"
    disputed_label_view = build(entities, disputed_label, evidence, documents, sources)
    disputed_label_feature = disputed_label_view["features"][0]
    expect(
        disputed_label_feature["location_label"] == {"ar": "منطقة الرياض"},
        "disputed optional location label was not omitted",
        failures,
    )

    disputed_association = copy.deepcopy(claims)
    disputed_association[4]["claim_state"] = "disputed"
    disputed_association_view = build(
        entities, disputed_association, evidence, documents, sources
    )
    expect(
        disputed_association_view["features"][0]["associated_organization_ids"] == [],
        "disputed optional organization association was not omitted",
        failures,
    )

    unresolved_association = copy.deepcopy(claims)
    unresolved_association[4]["value"]["entity_id"] = "SDA-ORG-MISSING"
    expect_raises(
        "unresolved organization association",
        lambda: build(entities, unresolved_association, evidence, documents, sources),
        failures,
    )

    mistyped_association = copy.deepcopy(claims)
    mistyped_association[4]["value"]["entity_id"] = "SDA-FAC-MAP-TEST"
    expect_raises(
        "non-organization association target",
        lambda: build(entities, mistyped_association, evidence, documents, sources),
        failures,
    )

    non_facility_entities = copy.deepcopy(entities)
    non_facility_entities.append(
        entity("SDA-ORG-BAD-MAP", "organization", subtype=None, names={"en": "Bad map subject"})
    )
    bad_subject_claims = copy.deepcopy(claims)
    bad_subject_claims.append(
        claim(
            "SDA-CLAIM-BAD-MAP-LAT",
            "SDA-ORG-BAD-MAP",
            "facility.public_latitude",
            {"kind": "number", "value": 20.0, "unit": "degrees", "precision": "source", "lower_bound": None, "upper_bound": None},
        )
    )
    expect_raises(
        "location predicate on non-facility",
        lambda: build(non_facility_entities, bad_subject_claims, evidence, documents, sources),
        failures,
    )

    if failures:
        print("M3 public map validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M3 public non-operational map contract: allowlisted fixed facilities only, "
        "supporting Evidence, high/verified coordinates, 2dp public coarsening, explicit broad labels, "
        "restricted subtype exclusion, fail-closed coordinate conflicts, optional-metadata dispute isolation, "
        "resolved active organization associations, and no backend-ID leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
