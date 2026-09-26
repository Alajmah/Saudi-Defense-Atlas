#!/usr/bin/env python3
"""Regression tests for staleness input-collection integrity."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m2_staleness import claim  # noqa: E402
from services.presentation.staleness import (  # noqa: E402
    StalenessError,
    build_staleness_report,
)


def main() -> int:
    visible = claim(
        claim_id="SDA-CLAIM-M2-STALE-HIDDEN-DUPLICATE",
        predicate_id="equipment.service_state",
        value={"kind": "string", "value": "synthetic", "language": "en"},
        verified_at="2026-01-01T00:00:00Z",
    )
    hidden = copy.deepcopy(visible)
    hidden["claim_state"] = "withdrawn"

    try:
        build_staleness_report(
            claims=[visible, hidden],
            as_of="2026-01-10T00:00:00Z",
            default_review_days=30,
        )
    except StalenessError:
        print(
            "Validated M2 staleness input integrity: duplicate canonical IDs are rejected "
            "before withdrawn/superseded state filtering."
        )
        return 0

    print(
        "M2 staleness isolation validation failed: duplicate ID hidden by Claim-state filtering",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
