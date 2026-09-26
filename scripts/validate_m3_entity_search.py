#!/usr/bin/env python3
"""Validate the M3 backend-neutral Arabic/English entity-search contract."""

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

from scripts.validate_m1_equipment_view import canonical_records  # noqa: E402
from scripts.validate_schemas import build_registry  # noqa: E402
from services.search.entity_search import (  # noqa: E402
    SearchContractError,
    build_entity_search_documents,
    fold_search_text,
    search_entity_documents,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(schema_name: str, instance: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(
            f"{schema_name} failed: " + "; ".join(error.message for error in errors)
        )


def top_id(response: dict[str, Any]) -> str | None:
    return response["results"][0]["id"] if response["results"] else None


def main() -> int:
    failures: list[str] = []
    entities = copy.deepcopy(canonical_records()["entities"])

    # A non-active record and backend mapping must never become public search truth.
    deprecated = copy.deepcopy(entities[0])
    deprecated["id"] = "SDA-EQUIP-F15SA-DEPRECATED-TEST"
    deprecated["record_status"] = "deprecated"
    deprecated["names"] = {"en": "Deprecated Search Fixture"}
    deprecated["backend_identifiers"] = [{"backend": "wikibase", "value": "Q999"}]
    entities.append(deprecated)
    entities[0]["backend_identifiers"] = [{"backend": "wikibase", "value": "Q3"}]

    for entity in entities:
        validate_instance("entity.schema.json", entity, failures)

    documents = build_entity_search_documents(entities)
    for document in documents:
        validate_instance("entity-search-document.schema.json", document, failures)

    expect(
        {document["id"] for document in documents}
        == {"SDA-EQUIP-F15SA", "SDA-ORG-BOEING", "SDA-ORG-RSAF"},
        "search projection did not include exactly the active canonical Entities",
        failures,
    )
    serialized_documents = json.dumps(documents, ensure_ascii=False, sort_keys=True)
    expect("Q3" not in serialized_documents and "Q999" not in serialized_documents,
           "backend identifiers leaked into search documents", failures)
    expect("backend_identifiers" not in serialized_documents,
           "backend mapping field leaked into search documents", failures)

    cases = [
        ("F-15SA", "en", "SDA-EQUIP-F15SA", "exact"),
        ("F15SA", "en", "SDA-EQUIP-F15SA", "normalized_exact"),
        ("إف-١٥ إس إيه", "ar", "SDA-EQUIP-F15SA", "normalized_exact"),
        ("اف 15 اس ايه", "ar", "SDA-EQUIP-F15SA", "normalized_exact"),
        ("Saudi Advanced Eagle", "en", "SDA-EQUIP-F15SA", "exact"),
        ("RSAF", "en", "SDA-ORG-RSAF", "exact"),
        ("القُوّات الجوية الملكية السعودية", "ar", "SDA-ORG-RSAF", "normalized_exact"),
        ("royal saud", "en", "SDA-ORG-RSAF", "token_prefix"),
        ("بوينغ", "ar", "SDA-ORG-BOEING", "exact"),
    ]
    for query, locale, expected_id, expected_match in cases:
        response = search_entity_documents(documents, text=query, locale=locale)
        validate_instance("entity-search-response.schema.json", response, failures)
        expect(top_id(response) == expected_id, f"query {query!r} resolved to wrong Entity", failures)
        if response["results"]:
            expect(
                response["results"][0]["match"]["type"] == expected_match,
                f"query {query!r} produced unexpected match class",
                failures,
            )
        expect(
            all("score" not in result for result in response["results"]),
            "baseline search must not expose pseudo-probabilistic numeric scores",
            failures,
        )

    # Entity-type filters must constrain results without changing canonical identity.
    filtered = search_entity_documents(
        documents,
        text="F15SA",
        locale="auto",
        entity_types=["organization"],
    )
    expect(filtered["results"] == [], "entity-type filter was ignored", failures)
    organization = search_entity_documents(
        documents,
        text="Royal Saudi",
        locale="auto",
        entity_types=["organization"],
    )
    expect(top_id(organization) == "SDA-ORG-RSAF", "organization filter lost RSAF", failures)

    # Query normalization is deterministic and search-only.
    expect(
        fold_search_text("  إِفـ-١٥   إس إيه  ") == "اف 15 اس ايه",
        "Arabic folding contract changed",
        failures,
    )
    expect(
        entities[0]["names"]["ar"] == "إف-15 إس إيه",
        "search folding mutated canonical Arabic naming",
        failures,
    )

    # Reordering input Entities/documents cannot change result order or match reason.
    reversed_documents = build_entity_search_documents(list(reversed(entities)))
    expect(documents == reversed_documents, "search document projection depends on Entity order", failures)
    baseline = search_entity_documents(documents, text="F15SA", locale="auto")
    reversed_search = search_entity_documents(list(reversed(documents)), text="F15SA", locale="auto")
    expect(baseline == reversed_search, "entity search result depends on document input order", failures)

    duplicate = [entities[0], copy.deepcopy(entities[0])]
    try:
        build_entity_search_documents(duplicate)
        failures.append("duplicate canonical Entity ID was accepted")
    except SearchContractError:
        pass

    try:
        search_entity_documents(documents, text="---", locale="auto")
        failures.append("query empty after normalization was accepted")
    except SearchContractError:
        pass

    try:
        search_entity_documents(documents, text="F-15", locale="xx")
        failures.append("unsupported search locale was accepted")
    except SearchContractError:
        pass

    if failures:
        print("M3 entity-search validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M3 backend-neutral entity search: Arabic diacritic/alef/digit folding, "
        "English punctuation compaction, canonical-name/alias resolution, SDA-only identity, "
        "ordinal match classes, filters, inactive exclusion, and deterministic ordering."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
