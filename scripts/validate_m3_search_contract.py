#!/usr/bin/env python3
"""Validate M3 engine-neutral public search and Arabic-aware lexical semantics."""

from __future__ import annotations

import copy
import re
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.presentation.search_contract import (  # noqa: E402
    SearchContractError,
    build_search_document,
    execute_reference_lexical_search,
    normalize_search_text,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


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


def entity(
    entity_id: str,
    entity_type: str,
    *,
    names: dict[str, str],
    aliases: list[dict[str, Any]] | None = None,
    descriptions: dict[str, str] | None = None,
    subtype: str | None = None,
    record_status: str = "active",
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": subtype,
        "names": names,
        "aliases": aliases or [],
        "external_identifiers": [],
        "backend_identifiers": [{"backend": "wikibase", "value": "Q999"}],
        "record_status": record_status,
        "merged_into": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-10T00:00:00Z",
    }
    if descriptions is not None:
        result["descriptions"] = descriptions
    return result


def query(
    text: str,
    *,
    locale: str = "auto",
    limit: int = 20,
    entity_types: list[str] | None = None,
    service_ids: list[str] | None = None,
    manufacturer_ids: list[str] | None = None,
    country_ids: list[str] | None = None,
    equipment_classes: list[str] | None = None,
    status_values: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "query": text,
        "locale": locale,
        "limit": limit,
        "filters": {
            "entity_types": entity_types or [],
            "service_ids": service_ids or [],
            "manufacturer_ids": manufacturer_ids or [],
            "country_ids": country_ids or [],
            "equipment_classes": equipment_classes or [],
            "status_values": status_values or [],
        },
    }


def main() -> int:
    failures: list[str] = []

    f15 = entity(
        "SDA-EQUIP-F15SA",
        "equipment_variant",
        names={"ar": "إف-15 إس إيه", "en": "F-15SA"},
        aliases=[
            {"value": "F15SA", "language": "en", "kind": "designation"},
            {"value": "Saudi Advanced Eagle", "language": "en", "kind": "common"},
            {"value": "إف 15 إس إيه", "language": "ar", "kind": "search"},
        ],
        descriptions={
            "ar": "نسخة مقاتلة مرتبطة بالقوات الجوية الملكية السعودية.",
            "en": "Fighter variant associated with the Royal Saudi Air Force.",
        },
        subtype="fighter",
    )
    typhoon = entity(
        "SDA-EQUIP-TYPHOON",
        "equipment",
        names={"ar": "تايفون", "en": "Eurofighter Typhoon"},
        aliases=[
            {"value": "يوروفايتر تايفون", "language": "ar", "kind": "common"},
            {"value": "Typhoon", "language": "en", "kind": "common"},
        ],
        descriptions={
            "ar": "مقاتلة متعددة المهام ضمن الخدمة السعودية.",
            "en": "Multirole fighter represented in the Saudi public atlas.",
        },
        subtype="fighter",
    )
    rsaf = entity(
        "SDA-ORG-RSAF",
        "organization",
        names={
            "ar": "القوات الجوية الملكية السعودية",
            "en": "Royal Saudi Air Force",
        },
        aliases=[
            {"value": "RSAF", "language": "en", "kind": "abbreviation"},
            {"value": "القوات الجوية السعودية", "language": "ar", "kind": "common"},
        ],
        descriptions={
            "ar": "فرع جوي عسكري سعودي.",
            "en": "Saudi military air service.",
        },
    )

    for item in (f15, typhoon, rsaf):
        validate_instance("entity.schema.json", item, failures)

    documents = [
        build_search_document(
            entity=f15,
            facets={
                "service_ids": ["SDA-ORG-RSAF"],
                "manufacturer_ids": ["SDA-ORG-BOEING"],
                "country_ids": ["SDA-COUNTRY-SA"],
                "equipment_classes": ["fighter"],
                "status_values": ["operational"],
            },
            projected_at="2026-01-12T00:00:00+03:00",
            revision_ids=["SDA-REV-M3-F15"],
        ),
        build_search_document(
            entity=typhoon,
            facets={
                "service_ids": ["SDA-ORG-RSAF"],
                "manufacturer_ids": ["SDA-ORG-EUROFIGHTER"],
                "country_ids": ["SDA-COUNTRY-SA"],
                "equipment_classes": ["fighter"],
                "status_values": ["operational"],
            },
            projected_at="2026-01-11T21:00:00Z",
            revision_ids=["SDA-REV-M3-TYPHOON"],
        ),
        build_search_document(
            entity=rsaf,
            facets={"country_ids": ["SDA-COUNTRY-SA"]},
            projected_at="2026-01-11T21:00:00Z",
            revision_ids=["SDA-REV-M3-RSAF"],
        ),
    ]

    for document in documents:
        validate_instance("search-document.schema.json", document, failures)
        expect(
            "backend_identifiers" not in document and "Q999" not in repr(document),
            "search projection leaked backend/store identity",
            failures,
        )
        expect(
            document["projected_at"] == "2026-01-11T21:00:00Z",
            "search projected_at must normalize to UTC",
            failures,
        )

    expect(normalize_search_text("تَايْفُون") == "تايفون", "Arabic diacritics were not removed deterministically", failures)
    expect(normalize_search_text("ٱلقُوَّات") == "القوات", "Arabic alef variants/diacritics were not normalized", failures)
    expect(normalize_search_text("اف-۱۵") == "اف-15", "Eastern Arabic/Persian digits were not normalized", failures)
    expect(normalize_search_text("القوة") != normalize_search_text("القوه"), "normalizer over-collapsed taa marbuta/haa", failures)
    expect(normalize_search_text("القوات") != normalize_search_text("قوات"), "normalizer silently applied Arabic article stemming", failures)

    test_queries = [
        query("F-15SA", locale="en"),
        query("F15SA", locale="auto"),
        query("تَايْفُون", locale="auto"),
        query("ٱلقوات الجوية الملكية السعودية", locale="auto"),
        query(
            "fighter",
            locale="en",
            entity_types=["equipment_variant"],
            manufacturer_ids=["SDA-ORG-BOEING", "SDA-ORG-NOT-PRESENT"],
            country_ids=["SDA-COUNTRY-SA"],
        ),
    ]
    for item in test_queries:
        validate_instance("search-query.schema.json", item, failures)

    result_f15 = execute_reference_lexical_search(documents=documents, query=test_queries[0])
    validate_instance("search-result.schema.json", result_f15, failures)
    expect(result_f15["hits"] and result_f15["hits"][0]["id"] == "SDA-EQUIP-F15SA", "exact English equipment name did not resolve F-15SA first", failures)
    expect(result_f15["hits"][0]["match_quality"] == "exact_name", "exact name match quality changed", failures)

    compact = execute_reference_lexical_search(documents=documents, query=test_queries[1])
    validate_instance("search-result.schema.json", compact, failures)
    expect(compact["hits"] and compact["hits"][0]["id"] == "SDA-EQUIP-F15SA", "compact equipment designation did not resolve through explicit alias", failures)

    arabic = execute_reference_lexical_search(documents=documents, query=test_queries[2])
    validate_instance("search-result.schema.json", arabic, failures)
    expect(arabic["locale"] == "ar" and arabic["hits"] and arabic["hits"][0]["id"] == "SDA-EQUIP-TYPHOON", "Arabic auto-locale/diacritic folding did not resolve Typhoon", failures)

    rsaf_result = execute_reference_lexical_search(documents=documents, query=test_queries[3])
    validate_instance("search-result.schema.json", rsaf_result, failures)
    expect(rsaf_result["hits"] and rsaf_result["hits"][0]["id"] == "SDA-ORG-RSAF", "Arabic alef-variant query did not resolve RSAF", failures)

    filtered = execute_reference_lexical_search(documents=documents, query=test_queries[4])
    validate_instance("search-result.schema.json", filtered, failures)
    expect([hit["id"] for hit in filtered["hits"]] == ["SDA-EQUIP-F15SA"], "facet semantics changed: OR within manufacturer facet / AND across facets expected", failures)

    reverse_result = execute_reference_lexical_search(documents=list(reversed(documents)), query=query("fighter", locale="en"))
    forward_result = execute_reference_lexical_search(documents=documents, query=query("fighter", locale="en"))
    expect(forward_result == reverse_result, "reference lexical ranking depends on input document order", failures)

    arabic_only = entity(
        "SDA-EQUIP-ARABIC-ONLY",
        "equipment",
        names={"ar": "منظومة تجريبية"},
        aliases=[],
    )
    validate_instance("entity.schema.json", arabic_only, failures)
    arabic_only_doc = build_search_document(
        entity=arabic_only,
        facets={},
        projected_at="2026-01-12T00:00:00Z",
        revision_ids=["SDA-REV-M3-ARABIC-ONLY"],
    )
    validate_instance("search-document.schema.json", arabic_only_doc, failures)
    expect(arabic_only_doc.get("descriptions") is None, "optional Entity description was not preserved as unknown/absent in search projection", failures)
    no_transliteration = execute_reference_lexical_search(
        documents=[arabic_only_doc], query=query("experimental system", locale="en")
    )
    expect(no_transliteration["total"] == 0, "search contract invented cross-script transliteration not present in canonical aliases", failures)

    merged = copy.deepcopy(f15)
    merged["record_status"] = "merged"
    merged["merged_into"] = "SDA-EQUIP-F15SA-NEW"
    try:
        build_search_document(
            entity=merged,
            facets={},
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-M3-MERGED"],
        )
        failures.append("merged/non-active Entity entered the public search index")
    except SearchContractError:
        pass

    try:
        execute_reference_lexical_search(documents=documents, query=query("   ", locale="auto"))
        failures.append("whitespace-only search query was accepted")
    except SearchContractError:
        pass

    serialized = repr(documents) + repr(forward_result)
    if re.search(r"(?<![A-Za-z0-9_-])Q\d+(?![A-Za-z0-9_-])", serialized):
        failures.append("backend Q identifier leaked into search document/result")

    if failures:
        print("M3 search contract validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M3 search contract: SDA identity, conservative Arabic orthographic folding, "
        "explicit aliases, UTC projection metadata, deterministic lexical ranking, explicit "
        "facet semantics, active-record boundary, optional descriptions, and no backend-ID or "
        "invented transliteration leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
