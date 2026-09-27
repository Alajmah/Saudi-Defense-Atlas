#!/usr/bin/env python3
"""Adversarial cross-record integrity checks for the M3 public map contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m3_public_map import build, claim, entity, fixtures  # noqa: E402
from services.presentation.projection_support import ProjectionError  # noqa: E402


def expect_raises(label: str, fn, failures: list[str]) -> None:
    try:
        fn()
    except ProjectionError:
        return
    failures.append(f"{label} did not fail closed")


def main() -> int:
    failures: list[str] = []
    entities, claims, evidence, documents, sources = fixtures()

    # A facility-only relationship predicate on a non-facility subject is malformed
    # canonical data and must not disappear silently from publication checks.
    malformed_entities = copy.deepcopy(entities)
    malformed_entities.append(
        entity(
            "SDA-ORG-BAD-ASSOC-SUBJECT",
            "organization",
            subtype=None,
            names={"en": "Bad Association Subject"},
        )
    )
    malformed_claims = copy.deepcopy(claims)
    malformed_claims.append(
        claim(
            "SDA-CLAIM-BAD-ASSOC-SUBJECT",
            "SDA-ORG-BAD-ASSOC-SUBJECT",
            "facility.associated_with.organization",
            {"kind": "entity", "entity_id": "SDA-ORG-RSAF"},
        )
    )
    expect_raises(
        "facility association on non-facility subject",
        lambda: build(malformed_entities, malformed_claims, evidence, documents, sources),
        failures,
    )

    # Association targets must remain active organizations at projection time.
    inactive_entities = copy.deepcopy(entities)
    for item in inactive_entities:
        if item["id"] == "SDA-ORG-RSAF":
            item["record_status"] = "deprecated"
            break
    expect_raises(
        "association to inactive organization",
        lambda: build(inactive_entities, copy.deepcopy(claims), evidence, documents, sources),
        failures,
    )

    if failures:
        print("M3 public map isolation validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M3 public map cross-record isolation: facility-only association subjects "
        "and active organization targets fail closed when canonical integrity is violated."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
