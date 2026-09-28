#!/usr/bin/env python3
"""Regression tests for post-merge M3 public-map review findings."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m3_public_map import build, claim, entity, fixtures  # noqa: E402
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


def main() -> int:
    failures: list[str] = []

    # Review finding 1: coordinate numbers are meaningful only with an explicit
    # supported angular unit. A range-valid radian value must never be treated as degrees.
    entities, claims, evidence, documents, sources = fixtures()
    radians = copy.deepcopy(claims)
    radians[0]["value"]["unit"] = "radians"
    expect_raises(
        "non-degree coordinate unit",
        lambda: build(entities, radians, evidence, documents, sources),
        failures,
    )

    missing_unit = copy.deepcopy(claims)
    missing_unit[0]["value"]["unit"] = None
    expect_raises(
        "missing coordinate unit",
        lambda: build(entities, missing_unit, evidence, documents, sources),
        failures,
    )

    # Review finding 2: Q/P-looking prose is legitimate display/citation content.
    # Only identity-bearing fields are subject to backend-ID leakage checks.
    prose_entities = copy.deepcopy(entities)
    prose_claims = copy.deepcopy(claims)
    prose_evidence = copy.deepcopy(evidence)
    prose_documents = copy.deepcopy(documents)
    prose_sources = copy.deepcopy(sources)
    prose_entities[0]["names"]["en"] = "Hangar Q3"
    prose_documents[0]["title"]["en"] = "Q3 2026 public facility reference"
    prose_evidence[0]["locator"]["section"] = "Page P5"
    prose_view = build(
        prose_entities,
        prose_claims,
        prose_evidence,
        prose_documents,
        prose_sources,
    )
    expect(
        prose_view["features"][0]["names"]["en"] == "Hangar Q3",
        "legitimate Q-looking facility prose was rejected or altered",
        failures,
    )
    expect(
        prose_view["features"][0]["citations"][0]["document_title"]["en"]
        == "Q3 2026 public facility reference",
        "legitimate Q-looking document prose was rejected or altered",
        failures,
    )
    expect(
        prose_view["features"][0]["citations"][0]["locator"]["section"] == "Page P5",
        "legitimate P-looking evidence locator was rejected or altered",
        failures,
    )

    backend_identity_entities = copy.deepcopy(entities)
    backend_identity_claims = copy.deepcopy(claims)
    backend_identity_entities[0]["id"] = "Q3"
    for item in backend_identity_claims:
        if item["subject_id"] == "SDA-FAC-MAP-TEST":
            item["subject_id"] = "Q3"
    expect_raises(
        "backend-native public identity",
        lambda: build(
            backend_identity_entities,
            backend_identity_claims,
            evidence,
            documents,
            sources,
        ),
        failures,
    )

    # Review finding 3: feature-ID generation must be injective for all schema-valid
    # canonical IDs. SDA-FAC-A and FAC-A must not collapse to one map feature ID.
    collision_entities, collision_claims, evidence, documents, sources = fixtures()
    collision_entities.append(
        entity(
            "FAC-MAP-TEST",
            "facility",
            subtype="training_center",
            names={"en": "Second Public Test Facility"},
        )
    )
    collision_claims.extend(
        [
            claim(
                "SDA-CLAIM-MAP-LAT-ALT",
                "FAC-MAP-TEST",
                "facility.public_latitude",
                {
                    "kind": "number",
                    "value": 24.50,
                    "unit": "degrees",
                    "precision": "source",
                    "lower_bound": None,
                    "upper_bound": None,
                },
            ),
            claim(
                "SDA-CLAIM-MAP-LON-ALT",
                "FAC-MAP-TEST",
                "facility.public_longitude",
                {
                    "kind": "number",
                    "value": 46.50,
                    "unit": "degrees",
                    "precision": "source",
                    "lower_bound": None,
                    "upper_bound": None,
                },
            ),
        ]
    )
    collision_view = build(
        collision_entities,
        collision_claims,
        evidence,
        documents,
        sources,
    )
    feature_ids = {item["id"] for item in collision_view["features"]}
    expect(
        feature_ids
        == {"SDA-MAP-SDA-FAC-MAP-TEST", "SDA-MAP-FAC-MAP-TEST"},
        "map feature-ID encoding is not injective",
        failures,
    )
    expect(
        len(feature_ids) == len(collision_view["features"]),
        "duplicate map feature IDs were emitted",
        failures,
    )

    if failures:
        print("M3 public map hardening validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M3 public-map hardening: degree-only coordinates, structural backend-ID checks, "
        "legitimate Q/P-looking prose, and injective map feature IDs."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
