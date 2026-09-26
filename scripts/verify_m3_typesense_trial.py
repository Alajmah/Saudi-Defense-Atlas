#!/usr/bin/env python3
"""Verify the bounded M3 Typesense candidate-index trial against a live server."""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.presentation.search_contract import (  # noqa: E402
    build_search_document,
    execute_reference_lexical_search,
)
from services.presentation.typesense_search import (  # noqa: E402
    TypesenseTrialClient,
    to_typesense_document,
    trial_collection_schema,
)


def entity(
    entity_id: str,
    entity_type: str,
    *,
    names: dict[str, str],
    aliases: list[dict[str, Any]] | None = None,
    descriptions: dict[str, str] | None = None,
    subtype: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": subtype,
        "names": names,
        "aliases": aliases or [],
        "external_identifiers": [],
        # This must never enter the derived search index.
        "backend_identifiers": [{"backend": "wikibase", "value": "Q999"}],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-12T00:00:00Z",
    }
    if descriptions is not None:
        record["descriptions"] = descriptions
    return record


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


def fixtures() -> list[dict[str, Any]]:
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

    return [
        build_search_document(
            entity=f15,
            facets={
                "service_ids": ["SDA-ORG-RSAF"],
                "manufacturer_ids": ["SDA-ORG-BOEING"],
                "country_ids": ["SDA-COUNTRY-SA"],
                "equipment_classes": ["fighter"],
                "status_values": ["operational"],
            },
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-M3-TS-F15"],
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
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-M3-TS-TYPHOON"],
        ),
        build_search_document(
            entity=rsaf,
            facets={"country_ids": ["SDA-COUNTRY-SA"]},
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-M3-TS-RSAF"],
        ),
    ]


def wait_for_health(client: TypesenseTrialClient) -> None:
    deadline = time.time() + 45
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            if client.health():
                return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
        time.sleep(1)
    raise AssertionError(f"Typesense did not become healthy: {last_error}")


def assert_same_as_reference(
    *,
    client: TypesenseTrialClient,
    collection: str,
    documents: list[dict[str, Any]],
    search_query: dict[str, Any],
    label: str,
) -> dict[str, Any]:
    expected = execute_reference_lexical_search(documents=documents, query=search_query)
    actual = client.search(
        collection_name=collection,
        documents=documents,
        query=search_query,
    )
    if actual != expected:
        raise AssertionError(
            f"{label} diverged from SDA reference contract:\n"
            f"expected={json.dumps(expected, ensure_ascii=False, sort_keys=True)}\n"
            f"actual={json.dumps(actual, ensure_ascii=False, sort_keys=True)}"
        )
    return actual


def main() -> int:
    base_url = os.environ.get("TYPESENSE_URL", "http://127.0.0.1:8108")
    api_key = os.environ.get("TYPESENSE_API_KEY", "m3-typesense-trial-key")
    client = TypesenseTrialClient(base_url=base_url, api_key=api_key)
    wait_for_health(client)

    documents = fixtures()
    engine_documents = [to_typesense_document(document) for document in documents]
    serialized = json.dumps(engine_documents, ensure_ascii=False, sort_keys=True)
    if "backend_identifiers" in serialized or re.search(
        r'(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])', serialized
    ):
        raise AssertionError("Typesense projection leaked backend/store identity")
    if any("names" in item or "descriptions" in item or "aliases" in item for item in engine_documents):
        raise AssertionError("candidate index stores more public prose than the bounded trial requires")

    schema = trial_collection_schema("unused-name")
    search_fields = {field["name"]: field for field in schema["fields"]}
    if search_fields["search_ar"].get("locale") != "ar":
        raise AssertionError("Arabic candidate field lost explicit ar locale")
    if any(field.get("stem") for field in schema["fields"]):
        raise AssertionError("Typesense trial unexpectedly enabled stemming")

    physical_v1 = "sda_search_m3_trial_v1"
    physical_v2 = "sda_search_m3_trial_v2"
    alias = "sda_search_m3_trial"

    # Best effort cleanup makes the script replayable locally.
    for name in (physical_v1, physical_v2):
        try:
            client.delete_collection(name)
        except Exception:  # noqa: BLE001
            pass

    client.create_collection(physical_v1)
    client.import_documents(physical_v1, documents)
    client.point_alias(alias, physical_v1)
    if client.alias_target(alias) != physical_v1:
        raise AssertionError("Typesense alias did not point to v1 collection")

    core_queries = [
        (query("F-15SA", locale="en"), "English designation"),
        (query("F15SA", locale="auto"), "compact designation alias"),
        (query("تَايْفُون", locale="auto"), "Arabic diacritic fold"),
        (query("ٱلقوات الجوية الملكية السعودية", locale="auto"), "Arabic alef fold"),
        (
            query(
                "fighter",
                locale="en",
                entity_types=["equipment_variant"],
                manufacturer_ids=["SDA-ORG-BOEING", "SDA-ORG-NOT-PRESENT"],
                country_ids=["SDA-COUNTRY-SA"],
            ),
            "OR-within / AND-across facets",
        ),
    ]
    baseline: dict[str, dict[str, Any]] = {}
    for search_query, label in core_queries:
        baseline[label] = assert_same_as_reference(
            client=client,
            collection=alias,
            documents=documents,
            search_query=search_query,
            label=label,
        )

    typo = client.search(
        collection_name=alias,
        documents=documents,
        query=query("F15SB", locale="en"),
    )
    if typo["total"] != 0:
        raise AssertionError("Typesense trial widened SDA semantics through typo tolerance")

    dropped = client.search(
        collection_name=alias,
        documents=documents,
        query=query("fighter impossible", locale="en"),
    )
    if dropped["total"] != 0:
        raise AssertionError("Typesense trial widened SDA semantics through token dropping")

    # Rebuild from canonical projections in reversed order and atomically repoint alias.
    client.create_collection(physical_v2)
    client.import_documents(physical_v2, list(reversed(documents)))
    client.point_alias(alias, physical_v2)
    if client.alias_target(alias) != physical_v2:
        raise AssertionError("Typesense alias did not cut over to rebuilt v2 collection")

    for search_query, label in core_queries:
        rebuilt = assert_same_as_reference(
            client=client,
            collection=alias,
            documents=list(reversed(documents)),
            search_query=search_query,
            label=f"rebuilt {label}",
        )
        if rebuilt != baseline[label]:
            raise AssertionError(f"rebuild changed public result for {label}")

    client.delete_collection(physical_v1)

    print(
        "PASS: Typesense 30.2 bounded M3 trial preserved SDA lexical search semantics, "
        "Arabic/English entity retrieval, exact facets, disabled typo/token-drop expansion, "
        "canonical identity isolation, deterministic project-owned ranking, and alias-based rebuild."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
