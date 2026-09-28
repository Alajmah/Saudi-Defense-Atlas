#!/usr/bin/env python3
"""Validate M4 deterministic source monitoring and editorial queue routing."""

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
from services.ingestion.acquisition import IngestionResult, RetrievalReceipt  # noqa: E402
from services.intelligence.editorial_routing import (  # noqa: E402
    EditorialRoutingError,
    RoutingPolicy,
    build_monitoring_observation,
    route_observation,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except EditorialRoutingError:
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


def source(source_id: str, source_class: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "publisher": {"en": f"Publisher {source_id}"},
        "source_class": source_class,
        "publisher_type": "government" if source_class == "A" else "specialist_media",
        "homepage": "https://example.invalid/",
        "jurisdiction": "Saudi Arabia",
        "notes": None,
        "active": True,
    }


def ingestion(
    source_id: str,
    *,
    status: str = "new",
    canonical_sha: str = "a" * 64,
    raw_sha: str = "b" * 64,
    observed_at: str = "2026-09-28T00:00:00Z",
    document_id: str | None = None,
) -> IngestionResult:
    doc_id = document_id or f"SDA-DOC-{source_id.removeprefix('SDA-SOURCE-')}"
    document = {
        "id": doc_id,
        "source_id": source_id,
        "retrieved_at": observed_at,
        "content_sha256": canonical_sha,
        "language": "en",
        "canonical_url": "https://example.invalid/item",
    }
    receipt = RetrievalReceipt(
        source_id=source_id,
        document_key="feed:test",
        observed_at=observed_at,
        requested_url="https://example.invalid/item",
        retrieved_url="https://example.invalid/item",
        status_code=200,
        media_type="text/html",
        raw_content_sha256=raw_sha,
        raw_content_length_bytes=100,
        etag=None,
        last_modified=None,
    )
    return IngestionResult(status=status, document=document, receipt=receipt)


def main() -> int:
    failures: list[str] = []
    policy = RoutingPolicy(
        relevance_terms=("contract award", "exercise", "f-15sa"),
        restricted_terms=("live unit movement", "readiness status"),
        high_priority_terms=("contract award",),
    )

    official_source = source("SDA-SOURCE-OFFICIAL", "A")
    lead_source = source("SDA-SOURCE-LEAD", "E")

    official_obs = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL"),
        source=official_source,
        canonical_text="Official contract award for F-15SA support.",
        policy=policy,
    )
    validate_instance("monitoring-observation.schema.json", official_obs, failures)
    expect(official_obs["relevance"]["classification"] == "relevant", "official relevant content was not classified relevant", failures)
    expect(official_obs["sensitivity"]["lane"] == "AMBER", "material relevant content should route through AMBER", failures)
    expect(official_obs["dedupe_key"] == f"sha256:{'a' * 64}", "canonical dedupe key changed", failures)

    official_route = route_observation(official_obs, created_at="2026-09-28T00:01:00Z")
    expect(official_route.action == "created", "official observation did not create queue item", failures)
    official_item = dict(official_route.item or {})
    validate_instance("editorial-queue-item.schema.json", official_item, failures)
    expect(official_item.get("lane") == "candidate_extraction", "A-class relevant document did not enter candidate extraction lane", failures)
    expect(official_item.get("ai_extraction_allowed") is True, "candidate extraction lane did not allow extraction", failures)
    expect(official_item.get("canonical_mutation_authority") is False, "queue item acquired canonical mutation authority", failures)
    expect(official_item.get("priority") == "high", "official/high-priority routing was not high priority", failures)

    unchanged_obs = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", status="unchanged", observed_at="2026-09-28T01:00:00Z"),
        source=official_source,
        canonical_text="Official contract award for F-15SA support.",
        policy=policy,
    )
    expect(route_observation(unchanged_obs, created_at="2026-09-28T01:01:00Z").action == "ignored", "unchanged content re-entered editorial queue", failures)

    irrelevant_obs = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", canonical_sha="c" * 64),
        source=official_source,
        canonical_text="Administrative office holiday notice.",
        policy=policy,
    )
    expect(route_observation(irrelevant_obs, created_at="2026-09-28T00:02:00Z").action == "ignored", "irrelevant content entered editorial queue", failures)

    # Whole-term matching: `exercise` must not match an unrelated longer token.
    substring_obs = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", canonical_sha="d" * 64),
        source=official_source,
        canonical_text="A document about exercising administrative discretion.",
        policy=policy,
    )
    expect(substring_obs["relevance"]["classification"] == "irrelevant", "relevance term matched inside a larger word", failures)

    lead_obs = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-LEAD",
            canonical_sha="e" * 64,
            raw_sha="f" * 64,
            document_id="SDA-DOC-LEAD",
        ),
        source=lead_source,
        canonical_text="Exercise announcement lead.",
        policy=policy,
    )
    lead_route = route_observation(lead_obs, created_at="2026-09-28T00:03:00Z")
    lead_item = dict(lead_route.item or {})
    validate_instance("editorial-queue-item.schema.json", lead_item, failures)
    expect(lead_item.get("lane") == "discovery_review", "E-class source escaped discovery-only lane", failures)
    expect(lead_item.get("ai_extraction_allowed") is False, "E-class discovery lead enabled AI extraction", failures)

    # Exact canonical-content duplicate across sources preserves all provenance and
    # may be promoted when an authoritative copy independently appears.
    first_e = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-LEAD",
            canonical_sha="9" * 64,
            raw_sha="1" * 64,
            document_id="SDA-DOC-LEAD-DUP",
        ),
        source=lead_source,
        canonical_text="F-15SA exercise notice.",
        policy=policy,
    )
    e_item = dict(route_observation(first_e, created_at="2026-09-28T00:04:00Z").item or {})
    authoritative_copy = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-OFFICIAL",
            canonical_sha="9" * 64,
            raw_sha="2" * 64,
            observed_at="2026-09-28T00:05:00Z",
            document_id="SDA-DOC-OFFICIAL-DUP",
        ),
        source=official_source,
        canonical_text="F-15SA exercise notice.",
        policy=policy,
    )
    promoted = route_observation(
        authoritative_copy,
        created_at="2026-09-28T00:06:00Z",
        existing_item=e_item,
    )
    promoted_item = dict(promoted.item or {})
    validate_instance("editorial-queue-item.schema.json", promoted_item, failures)
    expect(promoted.action == "merged", "cross-source exact duplicate did not merge", failures)
    expect(promoted_item.get("lane") == "candidate_extraction", "authoritative duplicate did not promote discovery group", failures)
    expect(promoted_item.get("source_ids") == ["SDA-SOURCE-LEAD", "SDA-SOURCE-OFFICIAL"], "duplicate group lost source provenance", failures)
    expect(len(promoted_item.get("document_ids", [])) == 2, "duplicate group lost document provenance", failures)

    restricted_obs = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-OFFICIAL",
            canonical_sha="9" * 64,
            raw_sha="3" * 64,
            observed_at="2026-09-28T00:07:00Z",
            document_id="SDA-DOC-RESTRICTED-DUP",
        ),
        source=official_source,
        canonical_text="F-15SA exercise includes live unit movement details.",
        policy=policy,
    )
    restricted = route_observation(
        restricted_obs,
        created_at="2026-09-28T00:08:00Z",
        existing_item=promoted_item,
    )
    restricted_item = dict(restricted.item or {})
    validate_instance("editorial-queue-item.schema.json", restricted_item, failures)
    expect(restricted_item.get("lane") == "restricted_human", "RED duplicate did not dominate queue routing", failures)
    expect(restricted_item.get("ai_extraction_allowed") is False, "RED queue item allowed AI extraction", failures)
    expect(restricted_item.get("priority") == "high", "RED queue item was not high priority", failures)

    mismatched_source = copy.deepcopy(official_source)
    mismatched_source["id"] = "SDA-SOURCE-WRONG"
    expect_raises(
        "receipt/source mismatch",
        lambda: build_monitoring_observation(
            ingestion=ingestion("SDA-SOURCE-OFFICIAL"),
            source=mismatched_source,
            canonical_text="F-15SA exercise",
            policy=policy,
        ),
        failures,
    )

    closed_item = dict(official_item)
    closed_item["state"] = "completed"
    expect_raises(
        "closed queue absorption",
        lambda: route_observation(
            official_obs,
            created_at="2026-09-28T00:09:00Z",
            existing_item=closed_item,
        ),
        failures,
    )

    if failures:
        print("M4 editorial routing validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 deterministic monitoring/editorial routing: unchanged and irrelevant observations are ignored; "
        "E-class material remains discovery-only; A-D relevant material may enter candidate extraction; exact-content "
        "duplicates retain multi-source provenance; RED routing dominates and disables AI extraction; queue records have "
        "no canonical mutation authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
