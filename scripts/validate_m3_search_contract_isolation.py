#!/usr/bin/env python3
"""Adversarial checks for M3 search-contract fail-closed boundaries."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.presentation.search_contract import (  # noqa: E402
    SearchContractError,
    build_search_document,
    execute_reference_lexical_search,
)


def expect_raises(label: str, fn, failures: list[str]) -> None:
    try:
        fn()
        failures.append(f"{label} was accepted")
    except SearchContractError:
        pass


def entity(
    entity_id: str = "SDA-EQUIP-SEARCH-BOUNDARY",
    *,
    entity_type: str = "equipment",
    aliases: list[dict[str, Any]] | None = None,
    names: dict[str, str] | None = None,
    descriptions: dict[str, str] | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": None,
        "names": names or {"en": "Chair System"},
        "aliases": aliases or [],
        "external_identifiers": [],
        "backend_identifiers": [{"backend": "wikibase", "value": "Q42"}],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-10T00:00:00Z",
    }
    if descriptions is not None:
        result["descriptions"] = descriptions
    return result


def query(text: str = "chair") -> dict[str, Any]:
    return {
        "query": text,
        "locale": "en",
        "limit": 20,
        "filters": {
            "entity_types": [],
            "service_ids": [],
            "manufacturer_ids": [],
            "country_ids": [],
            "equipment_classes": [],
            "status_values": [],
        },
    }


def main() -> int:
    failures: list[str] = []
    base_entity = entity(
        descriptions={
            "en": "A fighter description with several words that must remain tokenizable."
        }
    )
    document = build_search_document(
        entity=base_entity,
        facets={},
        projected_at="2026-01-12T00:00:00Z",
        revision_ids=["SDA-REV-M3-BOUNDARY"],
    )

    # Token quality must mean whole normalized tokens, not arbitrary substrings.
    air_result = execute_reference_lexical_search(
        documents=[document], query=query("air")
    )
    if air_result["total"] != 0:
        failures.append("token search matched substring 'air' inside unrelated words")

    exact_result = execute_reference_lexical_search(
        documents=[document], query=query("Chair System")
    )
    if not exact_result["hits"] or exact_result["hits"][0]["match_quality"] != "exact_name":
        failures.append("exact full-name boundary fixture did not resolve as exact_name")

    # Description normalization must not manufacture giant compact no-space variants.
    description_terms = document["normalized_terms"]["en"]
    if any("fighterdescriptionwithseveralwords" in term for term in description_terms):
        failures.append("description text was compacted into an invented designation-like term")

    # Schema-optional SearchDocument fields must also be optional at runtime.
    optional_omitted = copy.deepcopy(document)
    optional_omitted.pop("subtype", None)
    optional_omitted.pop("descriptions", None)
    optional_result = execute_reference_lexical_search(
        documents=[optional_omitted], query=query("Chair System")
    )
    if not optional_result["hits"] or optional_result["hits"][0]["id"] != document["id"]:
        failures.append("schema-valid document without optional fields was not searchable")

    bad_filter_key = query()
    bad_filter_key["filters"]["unknown"] = []
    expect_raises(
        "unknown query filter",
        lambda: execute_reference_lexical_search(documents=[document], query=bad_filter_key),
        failures,
    )

    string_filter = query()
    string_filter["filters"]["manufacturer_ids"] = "SDA-ORG-BOEING"
    expect_raises(
        "string-valued query filter",
        lambda: execute_reference_lexical_search(documents=[document], query=string_filter),
        failures,
    )

    duplicate_filter = query()
    duplicate_filter["filters"]["country_ids"] = ["SDA-COUNTRY-SA", "SDA-COUNTRY-SA"]
    expect_raises(
        "duplicate query facet value",
        lambda: execute_reference_lexical_search(documents=[document], query=duplicate_filter),
        failures,
    )

    extra_query_key = query()
    extra_query_key["semantic"] = True
    expect_raises(
        "undeclared semantic query option",
        lambda: execute_reference_lexical_search(documents=[document], query=extra_query_key),
        failures,
    )

    too_long = query("x" * 257)
    expect_raises(
        "overlong query",
        lambda: execute_reference_lexical_search(documents=[document], query=too_long),
        failures,
    )

    expect_raises(
        "unsupported Entity type",
        lambda: build_search_document(
            entity=entity(entity_type="weapon_of_massive_guessing"),
            facets={},
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-M3-BAD-TYPE"],
        ),
        failures,
    )

    expect_raises(
        "unsupported alias kind",
        lambda: build_search_document(
            entity=entity(aliases=[{"value": "Chair", "language": "en", "kind": "generated"}]),
            facets={},
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-M3-BAD-ALIAS"],
        ),
        failures,
    )

    malformed_document = copy.deepcopy(document)
    malformed_document["backend_identifiers"] = [{"backend": "wikibase", "value": "Q42"}]
    expect_raises(
        "search document with backend identifier extension",
        lambda: execute_reference_lexical_search(documents=[malformed_document], query=query()),
        failures,
    )

    missing_terms = copy.deepcopy(document)
    del missing_terms["normalized_terms"]
    expect_raises(
        "search document missing normalized terms",
        lambda: execute_reference_lexical_search(documents=[missing_terms], query=query()),
        failures,
    )

    # Stored SearchDocuments must preserve the complete facet shape from schema.
    missing_facets = copy.deepcopy(document)
    missing_facets["facets"] = {}
    expect_raises(
        "search document missing required facet keys",
        lambda: execute_reference_lexical_search(documents=[missing_facets], query=query()),
        failures,
    )

    null_facets = copy.deepcopy(document)
    null_facets["facets"] = None
    expect_raises(
        "search document null facets",
        lambda: execute_reference_lexical_search(documents=[null_facets], query=query()),
        failures,
    )

    # Declared normalized terms must exactly equal the deterministic projection.
    stale_terms = copy.deepcopy(document)
    stale_terms["normalized_terms"]["en"] = []
    expect_raises(
        "stale normalized terms",
        lambda: execute_reference_lexical_search(documents=[stale_terms], query=query("Chair System")),
        failures,
    )

    invented_term = copy.deepcopy(document)
    invented_term["normalized_terms"]["neutral"].append("invented-term")
    expect_raises(
        "invented normalized term",
        lambda: execute_reference_lexical_search(documents=[invented_term], query=query("invented-term")),
        failures,
    )

    if failures:
        print("M3 search isolation validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M3 search fail-closed boundaries: optional document fields, exact token "
        "semantics, strict query/filter/facet shape, normalized-term integrity, bounded "
        "normalization, Entity/alias vocabulary checks, and identity leakage rejection."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
