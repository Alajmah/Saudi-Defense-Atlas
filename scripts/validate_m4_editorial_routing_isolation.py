#!/usr/bin/env python3
"""Adversarial isolation checks for M4 monitoring/editorial routing."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.ingestion.acquisition import IngestionResult, RetrievalReceipt  # noqa: E402
from services.intelligence.editorial_routing import (  # noqa: E402
    EditorialRoutingError,
    RoutingPolicy,
    build_monitoring_observation,
    route_observation,
)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except EditorialRoutingError:
        return
    failures.append(f"{label} did not fail closed")


def source() -> dict[str, Any]:
    return {
        "id": "SDA-SOURCE-A",
        "publisher": {"en": "Official Authority"},
        "source_class": "A",
        "publisher_type": "government",
        "active": True,
    }


def ingestion(*, document_source_id: str = "SDA-SOURCE-A", status_code: int = 200) -> IngestionResult:
    receipt = RetrievalReceipt(
        source_id="SDA-SOURCE-A",
        document_key="feed:test",
        observed_at="2026-09-28T00:00:00Z",
        requested_url="https://example.invalid/item",
        retrieved_url="https://example.invalid/item",
        status_code=status_code,
        media_type="text/html",
        raw_content_sha256="1" * 64,
        raw_content_length_bytes=100,
        etag=None,
        last_modified=None,
    )
    return IngestionResult(
        status="new",
        document={
            "id": "SDA-DOC-A",
            "source_id": document_source_id,
            "content_sha256": "2" * 64,
        },
        receipt=receipt,
    )


def main() -> int:
    failures: list[str] = []
    policy = RoutingPolicy(
        relevance_terms=("exercise",),
        restricted_terms=("live unit movement",),
    )

    expect_raises(
        "Document/Source mismatch",
        lambda: build_monitoring_observation(
            ingestion=ingestion(document_source_id="SDA-SOURCE-B"),
            source=source(),
            canonical_text="exercise",
            policy=policy,
        ),
        failures,
    )
    expect_raises(
        "non-success retrieval receipt",
        lambda: build_monitoring_observation(
            ingestion=ingestion(status_code=503),
            source=source(),
            canonical_text="exercise",
            policy=policy,
        ),
        failures,
    )

    base_observation = build_monitoring_observation(
        ingestion=ingestion(), source=source(), canonical_text="exercise", policy=policy
    )
    base_item = dict(
        route_observation(base_observation, created_at="2026-09-28T00:01:00Z").item or {}
    )

    authority_corruption = copy.deepcopy(base_item)
    authority_corruption["canonical_mutation_authority"] = True
    expect_raises(
        "queue authority corruption",
        lambda: route_observation(
            base_observation,
            created_at="2026-09-28T00:02:00Z",
            existing_item=authority_corruption,
        ),
        failures,
    )

    extraction_corruption = copy.deepcopy(base_item)
    extraction_corruption["ai_extraction_allowed"] = False
    expect_raises(
        "queue extraction/lane inconsistency",
        lambda: route_observation(
            base_observation,
            created_at="2026-09-28T00:02:00Z",
            existing_item=extraction_corruption,
        ),
        failures,
    )

    claimed = copy.deepcopy(base_item)
    claimed["state"] = "claimed"
    restricted_observation = build_monitoring_observation(
        ingestion=ingestion(),
        source=source(),
        canonical_text="exercise with live unit movement",
        policy=policy,
    )
    expect_raises(
        "claimed item lane escalation",
        lambda: route_observation(
            restricted_observation,
            created_at="2026-09-28T00:03:00Z",
            existing_item=claimed,
        ),
        failures,
    )

    if failures:
        print("M4 editorial routing isolation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 routing isolation: cross-record source integrity, successful receipt requirement, "
        "queue authority invariants, and claimed-item escalation all fail closed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
