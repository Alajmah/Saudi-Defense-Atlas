#!/usr/bin/env python3
"""Validate deterministic PublicMapView -> GeoJSON renderer adaptation."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.presentation.map_geojson import build_map_renderer_payload  # noqa: E402
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


def citation(evidence_id: str) -> dict[str, Any]:
    return {
        "evidence_id": evidence_id,
        "evidence_role": "supports",
        "document_id": f"SDA-DOC-{evidence_id}",
        "source_id": f"SDA-SOURCE-{evidence_id}",
        "source_class": "A",
        "publisher": {"en": "Synthetic Authority"},
        "document_title": {"en": "Synthetic fixture"},
        "url": "https://example.invalid/reference",
        "published_at": {"value": "2026-09-01", "precision": "day"},
        "retrieved_at": "2026-09-02T00:00:00Z",
        "locator": {"section": "location"},
    }


def feature(feature_id: str, entity_id: str, latitude: float, longitude: float) -> dict[str, Any]:
    return {
        "id": feature_id,
        "entity_id": entity_id,
        "entity_type": "facility",
        "category": "training_center",
        "names": {"ar": f"منشأة {feature_id}", "en": f"Facility {feature_id}"},
        "location_label": {"ar": "منطقة عامة", "en": "Public area"},
        "coordinate": {
            "latitude": latitude,
            "longitude": longitude,
            "precision_class": "coarsened_2dp",
            "publication_policy": "fixed_public_reference_only",
        },
        "coordinate_claim_ids": [f"SDA-CLAIM-{feature_id}-LAT", f"SDA-CLAIM-{feature_id}-LON"],
        "associated_organization_ids": ["SDA-ORG-TEST"],
        "citations": [citation(f"SDA-EVID-{feature_id}")],
    }


def view() -> dict[str, Any]:
    return {
        "scope": "public_non_operational_fixed_facilities",
        "projected_at": "2026-09-27T00:00:00Z",
        "features": [
            feature("SDA-MAP-B", "SDA-FAC-B", 24.71, 46.68),
            feature("SDA-MAP-A", "SDA-FAC-A", 21.49, 39.19),
        ],
        "provenance": {
            "record_ids": ["SDA-FAC-A", "SDA-FAC-B"],
            "revision_ids": ["SDA-REV-MAP"],
        },
    }


def main() -> int:
    failures: list[str] = []
    baseline = build_map_renderer_payload(view())
    expect(baseline["renderer_contract"] == "sda-public-map-v0.1", "renderer contract changed", failures)
    expect(baseline["geojson"]["type"] == "FeatureCollection", "GeoJSON type changed", failures)
    ids = [item["id"] for item in baseline["geojson"]["features"]]
    expect(ids == ["SDA-MAP-A", "SDA-MAP-B"], "GeoJSON ordering is not deterministic", failures)
    expect(
        baseline["geojson"]["features"][0]["geometry"]["coordinates"] == [39.19, 21.49],
        "GeoJSON coordinate order/precision changed",
        failures,
    )
    expect(
        baseline["fallback_items"][0]["names"]["ar"].startswith("منشأة"),
        "Arabic fallback label missing",
        failures,
    )
    expect(
        baseline["fallback_items"][0]["citations"][0]["evidence_id"].startswith("SDA-EVID-"),
        "supporting Evidence missing from fallback",
        failures,
    )

    reordered = view()
    reordered["features"] = list(reversed(reordered["features"]))
    expect(
        build_map_renderer_payload(reordered) == baseline,
        "renderer payload depends on input feature order",
        failures,
    )

    precise = view()
    precise["features"][0]["coordinate"]["latitude"] = 24.7136
    expect_raises("precision leakage", lambda: build_map_renderer_payload(precise), failures)

    wrong_scope = view()
    wrong_scope["scope"] = "operational_map"
    expect_raises("non-public map scope", lambda: build_map_renderer_payload(wrong_scope), failures)

    no_support = view()
    no_support["features"][0]["citations"][0]["evidence_role"] = "contextualizes"
    expect_raises("feature without supporting Evidence", lambda: build_map_renderer_payload(no_support), failures)

    backend = view()
    backend["features"][0]["names"]["en"] = "Backend Q123 leak"
    expect_raises("backend ID leakage", lambda: build_map_renderer_payload(backend), failures)

    restricted = view()
    restricted["features"][0]["category"] = "air_defense_site"
    expect_raises("restricted category", lambda: build_map_renderer_payload(restricted), failures)

    if failures:
        print("M3 map renderer payload validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated deterministic PublicMapView -> GeoJSON/fallback adaptation: public scope only, "
        "2dp coordinates, supporting Evidence, deterministic order, bilingual fallback, and no backend-ID leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
