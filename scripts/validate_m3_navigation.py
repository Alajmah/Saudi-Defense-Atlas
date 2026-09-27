#!/usr/bin/env python3
"""Validate M3 public timeline and filter navigation."""

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
from services.presentation.navigation import build_navigation_view  # noqa: E402
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
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(
            f"{schema_name} failed: " + "; ".join(error.message for error in errors)
        )


def search_document(
    document_id: str,
    entity_type: str,
    name_en: str,
    *,
    name_ar: str | None = None,
    service_ids: list[str] | None = None,
    manufacturer_ids: list[str] | None = None,
    country_ids: list[str] | None = None,
    equipment_classes: list[str] | None = None,
    status_values: list[str] | None = None,
) -> dict[str, Any]:
    names = {"en": name_en}
    if name_ar:
        names["ar"] = name_ar
    return {
        "id": document_id,
        "entity_type": entity_type,
        "subtype": None,
        "names": names,
        "aliases": [],
        "descriptions": None,
        "normalized_terms": {"ar": [], "en": [name_en.lower()], "neutral": []},
        "facets": {
            "service_ids": service_ids or [],
            "manufacturer_ids": manufacturer_ids or [],
            "country_ids": country_ids or [],
            "equipment_classes": equipment_classes or [],
            "status_values": status_values or [],
        },
        "projected_at": "2026-09-27T00:00:00Z",
        "revision_ids": [f"SDA-REV-{document_id}"],
    }


def citation(event_id: str, role: str = "supports") -> dict[str, Any]:
    return {
        "evidence_id": f"SDA-EVID-{event_id}",
        "evidence_role": role,
        "document_id": f"SDA-DOC-{event_id}",
        "source_id": f"SDA-SOURCE-{event_id}",
        "source_class": "A",
        "publisher": {"en": "Synthetic Authority"},
        "document_title": {"en": "Synthetic event source"},
        "url": "https://example.invalid/event",
        "published_at": {"value": "2026-01-01", "precision": "day"},
        "retrieved_at": "2026-01-02T00:00:00Z",
        "locator": {"section": "event"},
    }


def timeline_event(
    event_id: str,
    event_type: str,
    value: str,
    precision: str,
    *,
    name_en: str,
) -> dict[str, Any]:
    return {
        "event_id": event_id,
        "event_type": event_type,
        "names": {"en": name_en},
        "occurred_at": {"value": value, "precision": precision},
        "ended_at": None,
        "confidence": "verified",
        "citations": [citation(event_id)],
    }


def graph(
    *,
    root: str,
    domain: str,
    events: list[dict[str, Any]],
    suffix: str,
) -> dict[str, Any]:
    return {
        "scope": {
            "root_entity_ids": [root],
            "domains": [domain],
            "expansion": "bounded_single_pass",
        },
        "nodes": [
            {
                "id": root,
                "node_kind": "entity",
                "entity_type": "equipment_variant",
                "subtype": "fighter",
                "names": {"en": root},
            }
        ],
        "edges": [],
        "timeline": events,
        "provenance": {
            "projected_at": "2026-09-27T00:00:00Z",
            "record_ids": [root, *[event["event_id"] for event in events]],
            "revision_ids": [f"SDA-REV-GRAPH-{suffix}"],
        },
    }


def fixtures() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents = [
        search_document(
            "SDA-EQUIP-F15SA",
            "equipment_variant",
            "F-15SA",
            name_ar="إف-15 إس إيه",
            service_ids=["SDA-ORG-RSAF"],
            manufacturer_ids=["SDA-ORG-BOEING"],
            country_ids=["SDA-COUNTRY-SA"],
            equipment_classes=["fighter"],
            status_values=["operational"],
        ),
        search_document(
            "SDA-EQUIP-TYPHOON",
            "equipment_variant",
            "Eurofighter Typhoon",
            name_ar="يوروفايتر تايفون",
            service_ids=["SDA-ORG-RSAF"],
            manufacturer_ids=["SDA-ORG-EUROFIGHTER"],
            country_ids=["SDA-COUNTRY-UK"],
            equipment_classes=["fighter"],
            status_values=["operational"],
        ),
        search_document("SDA-ORG-RSAF", "organization", "Royal Saudi Air Force", name_ar="القوات الجوية الملكية السعودية"),
        search_document("SDA-ORG-BOEING", "organization", "Boeing"),
        search_document("SDA-ORG-EUROFIGHTER", "organization", "Eurofighter"),
        search_document("SDA-COUNTRY-SA", "country", "Saudi Arabia", name_ar="المملكة العربية السعودية"),
        search_document("SDA-COUNTRY-UK", "country", "United Kingdom", name_ar="المملكة المتحدة"),
    ]

    delivery = timeline_event(
        "SDA-EVENT-F15-DELIVERY",
        "delivery",
        "2020-12-10",
        "day",
        name_en="F-15SA delivery milestone",
    )
    exercise = timeline_event(
        "SDA-EVENT-EXERCISE-2025",
        "exercise",
        "2025-05",
        "month",
        name_en="Synthetic exercise",
    )
    unknown = timeline_event(
        "SDA-EVENT-UNKNOWN-DATE",
        "contract_update",
        "unknown",
        "unknown",
        name_en="Undated synthetic update",
    )
    graphs = [
        graph(root="SDA-EQUIP-F15SA", domain="procurement", events=[delivery, unknown], suffix="PROC"),
        graph(root="SDA-EQUIP-TYPHOON", domain="exercise", events=[exercise], suffix="EXERCISE"),
    ]
    return documents, graphs


def main() -> int:
    failures: list[str] = []
    documents, graphs = fixtures()
    view = build_navigation_view(
        search_documents=documents,
        relationship_graphs=graphs,
        projected_at="2026-09-27T12:00:00+03:00",
    )
    validate_instance("navigation-view.schema.json", view, failures)

    expect(view["projected_at"] == "2026-09-27T09:00:00Z", "projected_at was not normalized to UTC", failures)
    entity_type_counts = {item["value"]: item["count"] for item in view["filters"]["entity_types"]}
    expect(entity_type_counts.get("equipment_variant") == 2, "entity-type count changed", failures)
    fighter = {item["value"]: item["count"] for item in view["filters"]["equipment_classes"]}
    expect(fighter.get("fighter") == 2, "equipment-class count changed", failures)
    services = {item["id"]: item for item in view["filters"]["service_ids"]}
    expect(services["SDA-ORG-RSAF"]["count"] == 2, "service filter count changed", failures)
    expect(services["SDA-ORG-RSAF"]["names"].get("ar") == "القوات الجوية الملكية السعودية", "Arabic service label missing", failures)

    timeline_ids = [item["event_id"] for item in view["timeline"]]
    expect(
        timeline_ids == ["SDA-EVENT-F15-DELIVERY", "SDA-EVENT-EXERCISE-2025", "SDA-EVENT-UNKNOWN-DATE"],
        "timeline deterministic chronological order changed",
        failures,
    )
    expect(all("current_state" not in item and "status" not in item for item in view["timeline"]), "timeline inferred current state", failures)
    expect(all(any(citation["evidence_role"] == "supports" for citation in item["citations"]) for item in view["timeline"]), "timeline supporting Evidence missing", failures)

    # Same Event appearing in another public graph may broaden navigation context,
    # but it must not create a duplicate timeline event.
    duplicate_graphs = copy.deepcopy(graphs)
    duplicate_graphs.append(
        graph(
            root="SDA-EQUIP-TYPHOON",
            domain="procurement",
            events=[copy.deepcopy(graphs[0]["timeline"][0])],
            suffix="DUP",
        )
    )
    merged = build_navigation_view(
        search_documents=documents,
        relationship_graphs=duplicate_graphs,
        projected_at="2026-09-27T00:00:00Z",
    )
    merged_delivery = next(item for item in merged["timeline"] if item["event_id"] == "SDA-EVENT-F15-DELIVERY")
    expect(merged_delivery["domains"] == ["procurement"], "duplicate Event domain merge changed", failures)
    expect(merged_delivery["root_entity_ids"] == ["SDA-EQUIP-F15SA", "SDA-EQUIP-TYPHOON"], "duplicate Event root context was not merged", failures)

    conflicting = copy.deepcopy(duplicate_graphs)
    conflicting[-1]["timeline"][0]["event_type"] = "contract_award"
    expect_raises(
        "conflicting duplicate Event",
        lambda: build_navigation_view(
            search_documents=documents,
            relationship_graphs=conflicting,
            projected_at="2026-09-27T00:00:00Z",
        ),
        failures,
    )

    unresolved = copy.deepcopy(documents)
    unresolved[0]["facets"]["manufacturer_ids"] = ["SDA-ORG-MISSING"]
    expect_raises(
        "unresolved entity facet",
        lambda: build_navigation_view(
            search_documents=unresolved,
            relationship_graphs=graphs,
            projected_at="2026-09-27T00:00:00Z",
        ),
        failures,
    )

    context_only = copy.deepcopy(graphs)
    context_only[0]["timeline"][0]["citations"][0]["evidence_role"] = "contextualizes"
    expect_raises(
        "timeline event without supporting Evidence",
        lambda: build_navigation_view(
            search_documents=documents,
            relationship_graphs=context_only,
            projected_at="2026-09-27T00:00:00Z",
        ),
        failures,
    )

    backend = copy.deepcopy(documents)
    backend[0]["names"]["en"] = "Leaked Q123"
    expect_raises(
        "backend identity leakage",
        lambda: build_navigation_view(
            search_documents=backend,
            relationship_graphs=graphs,
            projected_at="2026-09-27T00:00:00Z",
        ),
        failures,
    )

    if failures:
        print("M3 navigation validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M3 timeline/filter navigation: deterministic facet counts, bilingual entity facets, "
        "chronological Event navigation with supporting Evidence, duplicate-event context merging, "
        "fail-closed conflicts/references, explicit unknown dates, and no inferred current state."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
