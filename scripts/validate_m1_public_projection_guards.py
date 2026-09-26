#!/usr/bin/env python3
"""Regression checks for M1 public projection admission and integrity guards."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m1_equipment_view import canonical_records  # noqa: E402
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from services.presentation.equipment_view import ProjectionError, build_equipment_view  # noqa: E402
from services.presentation.read_projection_hash import (  # noqa: E402
    entity_read_projection,
    event_read_projection,
)


def expect_projection_error(records: dict, label: str) -> None:
    try:
        build_equipment_view(
            entity_id="SDA-EQUIP-F15SA",
            **records,
            projected_at="2026-01-07T00:03:00Z",
        )
    except ProjectionError:
        return
    raise AssertionError(f"{label}: projector admitted material record without supporting Evidence")


def main() -> int:
    records = canonical_records()

    claim_without_support = copy.deepcopy(records)
    claim_without_support["claims"][0]["evidence_links"][0]["role"] = "contextualizes"
    expect_projection_error(claim_without_support, "context-only Claim")

    event_without_support = copy.deepcopy(records)
    for link in event_without_support["events"][0]["evidence_links"]:
        link["role"] = "contradicts"
    expect_projection_error(event_without_support, "contradiction-only Event")

    entity = copy.deepcopy(records["entities"][0])
    entity_projection_hash = canonical_sha256(entity_read_projection(entity))
    entity["external_identifiers"] = [{"scheme": "example", "value": "ignored-by-public-view"}]
    if canonical_sha256(entity) == canonical_sha256(records["entities"][0]):
        raise AssertionError("canonical Entity hash fixture did not change")
    if canonical_sha256(entity_read_projection(entity)) != entity_projection_hash:
        raise AssertionError("Entity public read hash changed for an unprojected canonical field")

    event = copy.deepcopy(records["events"][0])
    event_projection_hash = canonical_sha256(event_read_projection(event))
    event["notes"] = "Changed canonical note that is intentionally outside the public read subset."
    if canonical_sha256(event_read_projection(event)) != event_projection_hash:
        raise AssertionError("Event public read hash changed for an unprojected canonical field")

    print(
        "Validated M1 public projection guards: supporting Evidence is mandatory and "
        "canonical payload hashes remain distinct from public read-projection hashes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
