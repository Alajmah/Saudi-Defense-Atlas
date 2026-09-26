#!/usr/bin/env python3
"""Validate the first backend-neutral M1 public equipment projection contract."""

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
from services.presentation.equipment_view import (  # noqa: E402
    ProjectionError,
    build_equipment_view,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(
    schema_name: str, instance: dict[str, Any], failures: list[str]
) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(
            f"{schema_name} failed: "
            + "; ".join(error.message for error in errors)
        )


def canonical_records() -> dict[str, list[dict[str, Any]]]:
    source = json.loads(
        (ROOT / "data" / "sources" / "usaf.json").read_text(encoding="utf-8")
    )
    document = {
        "id": "SDA-DOC-M1-PUBLIC-VIEW-F15SA",
        "source_id": source["id"],
        "title": {"en": "AFLCMC delivers final F-15SA to Royal Saudi Air Force"},
        "canonical_url": (
            "https://www.af.mil/News/Article-Display/Article/2444558/"
            "aflcmc-delivers-final-f-15sa-to-royal-saudi-air-force/"
        ),
        "retrieved_url": (
            "https://www.af.mil/News/Article-Display/Article/2444558/"
            "aflcmc-delivers-final-f-15sa-to-royal-saudi-air-force/"
        ),
        "published_at": {"value": "2020-12-11", "precision": "day"},
        "retrieved_at": "2026-01-07T00:00:00Z",
        "language": "en",
        "document_type": "press_release",
        "media_type": "text/html",
        "content_sha256": "a" * 64,
        "content_length_bytes": 4096,
    }
    manufacturer_evidence = {
        "id": "SDA-EVID-M1-PUBLIC-MANUFACTURER",
        "document_id": document["id"],
        "locator": {
            "paragraph": 2,
            "fragment": "manufacturer-context",
            "selector": "article-body:p[2]",
        },
        "language": "en",
        "captured_at": "2026-01-07T00:00:00Z",
        "capture_method": "deterministic_parser",
    }
    delivery_evidence = {
        "id": "SDA-EVID-M1-PUBLIC-DELIVERY",
        "document_id": document["id"],
        "locator": {
            "paragraph": 1,
            "fragment": "final-delivery",
            "selector": "article-body:p[1]",
        },
        "language": "en",
        "captured_at": "2026-01-07T00:00:00Z",
        "capture_method": "deterministic_parser",
    }

    f15sa = {
        "id": "SDA-EQUIP-F15SA",
        "entity_type": "equipment_variant",
        "subtype": "fighter_aircraft_variant",
        "names": {"en": "F-15SA", "ar": "إف-15 إس إيه"},
        "aliases": [
            {"value": "Saudi Advanced Eagle", "language": "en", "kind": "common"}
        ],
        "descriptions": {
            "en": "Saudi F-15 variant",
            "ar": "نسخة سعودية من مقاتلة إف-15",
        },
        "record_status": "active",
        "created_at": "2026-01-07T00:00:00Z",
        "updated_at": "2026-01-07T00:00:00Z",
    }
    boeing = {
        "id": "SDA-ORG-BOEING",
        "entity_type": "organization",
        "subtype": "manufacturer",
        "names": {"en": "Boeing", "ar": "بوينغ"},
        "aliases": [],
        "record_status": "active",
        "created_at": "2026-01-07T00:00:00Z",
        "updated_at": "2026-01-07T00:00:00Z",
    }
    rsaf = {
        "id": "SDA-ORG-RSAF",
        "entity_type": "organization",
        "subtype": "military_service",
        "names": {
            "en": "Royal Saudi Air Force",
            "ar": "القوات الجوية الملكية السعودية",
        },
        "aliases": [
            {"value": "RSAF", "language": "en", "kind": "abbreviation"}
        ],
        "record_status": "active",
        "created_at": "2026-01-07T00:00:00Z",
        "updated_at": "2026-01-07T00:00:00Z",
    }

    manufacturer_claim = {
        "id": "SDA-CLAIM-M1-PUBLIC-MANUFACTURER",
        "subject_id": boeing["id"],
        "predicate_id": "manufacturer.manufactures.equipment",
        "value": {"kind": "entity", "entity_id": f15sa["id"]},
        "scope": {"entity_ids": [f15sa["id"]], "quantity_type": None, "note": None},
        "validity": {"point_in_time": {"value": "2020-12-11", "precision": "day"}},
        "confidence": "high",
        "evidence_links": [
            {"evidence_id": manufacturer_evidence["id"], "role": "supports"}
        ],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": None,
        "created_at": "2026-01-07T00:00:01Z",
    }
    delivery_event = {
        "id": "SDA-EVENT-2020-12-10-M1-PUBLIC-DELIVERY",
        "event_type": "delivery",
        "names": {
            "en": "Final F-15SA delivery reported by official source",
            "ar": "إبلاغ مصدر رسمي عن التسليم النهائي لطائرات F-15SA",
        },
        "occurred_at": {"value": "2020-12-10", "precision": "day"},
        "ended_at": None,
        "participants": [
            {"entity_id": rsaf["id"], "role": "recipient"},
            {"entity_id": boeing["id"], "role": "manufacturer"},
        ],
        "related_entity_ids": [f15sa["id"]],
        "related_claim_ids": [manufacturer_claim["id"]],
        "confidence": "high",
        "evidence_links": [
            {"evidence_id": delivery_evidence["id"], "role": "supports"},
            {"evidence_id": manufacturer_evidence["id"], "role": "contextualizes"},
        ],
        "notes": "Dated delivery event only; no current inventory/readiness implication.",
        "created_at": "2026-01-07T00:00:01Z",
    }
    return {
        "entities": [f15sa, boeing, rsaf],
        "claims": [manufacturer_claim],
        "events": [delivery_event],
        "evidence": [manufacturer_evidence, delivery_evidence],
        "documents": [document],
        "sources": [source],
    }


def main() -> int:
    failures: list[str] = []
    records = canonical_records()

    for schema_name, key in (
        ("entity.schema.json", "entities"),
        ("claim.schema.json", "claims"),
        ("event.schema.json", "events"),
        ("evidence.schema.json", "evidence"),
        ("document.schema.json", "documents"),
        ("source.schema.json", "sources"),
    ):
        for instance in records[key]:
            validate_instance(schema_name, instance, failures)

    view = build_equipment_view(
        entity_id="SDA-EQUIP-F15SA",
        **records,
        projected_at="2026-01-07T00:03:00Z",
        revision_ids=["SDA-REVISION-M1-PUBLIC-VIEW-TEST"],
    )
    validate_instance("equipment-view.schema.json", view, failures)

    expect(view["id"] == "SDA-EQUIP-F15SA", "view must retain SDA canonical ID", failures)
    expect(
        view["names"] == {"en": "F-15SA", "ar": "إف-15 إس إيه"},
        "Arabic and English names must project from one canonical Entity",
        failures,
    )
    expect(
        view["aliases"]["en"] == ["Saudi Advanced Eagle"],
        "English alias projection changed",
        failures,
    )
    expect(len(view["facts"]) == 1, "view must expose exactly one admitted M1 Claim", failures)
    if view["facts"]:
        fact = view["facts"][0]
        expect(fact["direction"] == "inbound", "manufacturer Claim must project inbound", failures)
        expect(
            fact["predicate_id"] == "manufacturer.manufactures.equipment",
            "unexpected public Claim predicate",
            failures,
        )
        expect(len(fact["citations"]) == 1, "material Claim must retain citation", failures)
        if fact["citations"]:
            citation = fact["citations"][0]
            expect(
                citation["source_id"] == "SDA-SOURCE-USAF",
                "Claim citation must resolve Source",
                failures,
            )
            expect(
                citation["document_id"] == "SDA-DOC-M1-PUBLIC-VIEW-F15SA",
                "Claim citation must resolve Document",
                failures,
            )
            expect(
                citation["evidence_id"] == "SDA-EVID-M1-PUBLIC-MANUFACTURER",
                "Claim citation must resolve Evidence",
                failures,
            )

    expect(len(view["events"]) == 1, "dated delivery Event must project separately", failures)
    if view["events"]:
        event = view["events"][0]
        roles = sorted(participant["role"] for participant in event["participants"])
        expect(roles == ["manufacturer", "recipient"], "delivery participant roles changed", failures)
        expect(event["occurred_at"]["value"] == "2020-12-10", "delivery date changed", failures)
        expect(len(event["citations"]) == 2, "delivery Event must retain both Evidence links", failures)

    expect(view["field_states"]["manufacturer"]["state"] == "known", "manufacturer must be known", failures)
    for field in ("operator", "inventory_quantity", "service_state"):
        expect(
            view["field_states"][field]["state"] == "unknown",
            f"{field} must remain unknown without an admitted Claim",
            failures,
        )
        expect(
            view["field_states"][field]["claim_ids"] == [],
            f"{field} unknown state must not invent Claim IDs",
            failures,
        )

    related_ids = [entity["id"] for entity in view["related_entities"]]
    expect(
        related_ids == ["SDA-ORG-BOEING", "SDA-ORG-RSAF"],
        "related Entity projection changed",
        failures,
    )
    serialized = json.dumps(view, ensure_ascii=False, sort_keys=True)
    expect(
        '"backend_identifiers"' not in serialized,
        "public view must not leak backend identifier mappings",
        failures,
    )

    broken = copy.deepcopy(records)
    broken["evidence"] = [
        record
        for record in broken["evidence"]
        if record["id"] != "SDA-EVID-M1-PUBLIC-MANUFACTURER"
    ]
    try:
        build_equipment_view(
            entity_id="SDA-EQUIP-F15SA",
            **broken,
            projected_at="2026-01-07T00:03:00Z",
        )
        failures.append("projector published a material record with unresolved Evidence")
    except ProjectionError:
        pass

    withdrawn = copy.deepcopy(records)
    withdrawn["claims"][0]["claim_state"] = "withdrawn"
    withdrawn_view = build_equipment_view(
        entity_id="SDA-EQUIP-F15SA",
        **withdrawn,
        projected_at="2026-01-07T00:03:00Z",
    )
    expect(withdrawn_view["facts"] == [], "withdrawn Claim must not be publicly presented", failures)
    expect(
        withdrawn_view["field_states"]["manufacturer"]["state"] == "unknown",
        "withdrawn manufacturer Claim must not fill the manufacturer field",
        failures,
    )

    disputed = copy.deepcopy(records)
    disputed["claims"][0]["claim_state"] = "disputed"
    disputed_view = build_equipment_view(
        entity_id="SDA-EQUIP-F15SA",
        **disputed,
        projected_at="2026-01-07T00:03:00Z",
    )
    expect(
        disputed_view["field_states"]["manufacturer"]["state"] == "disputed",
        "disputed Claim must be visible as disputed rather than flattened to known",
        failures,
    )

    if failures:
        print("M1 equipment-view validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated backend-neutral F-15SA EquipmentView: bilingual canonical identity, "
        "strict Evidence->Document->Source citations, dated Event separation, explicit "
        "unknown fields, disputed/withdrawn behavior, and no backend-ID leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
