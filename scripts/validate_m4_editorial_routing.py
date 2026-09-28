#!/usr/bin/env python3
"""Validate M4 deterministic source monitoring and editorial queue routing."""

from __future__ import annotations

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
    RoutingPolicy,
    build_monitoring_observation,
    route_observation,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(schema_name: str, instance: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    errors = list(
        Draft202012Validator(
            schemas[schema_name], registry=registry, format_checker=FormatChecker()
        ).iter_errors(instance)
    )
    if errors:
        failures.append(
            f"{schema_name} failed: " + "; ".join(error.message for error in errors)
        )


def source(source_id: str, source_class: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "publisher": {"en": source_id},
        "source_class": source_class,
        "publisher_type": "government" if source_class == "A" else "social",
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
    return IngestionResult(
        status=status,
        document={
            "id": document_id or f"SDA-DOC-{source_id.removeprefix('SDA-SOURCE-')}",
            "source_id": source_id,
            "content_sha256": canonical_sha,
        },
        receipt=RetrievalReceipt(
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
        ),
    )


def main() -> int:
    failures: list[str] = []
    policy = RoutingPolicy(
        policy_id="M4-ROUTING-v0.1",
        relevance_terms=("contract award", "exercise", "f-15sa"),
        restricted_terms=("live unit movement", "readiness status"),
        high_priority_terms=("contract award",),
        ai_extraction_feed_keys=("SDA-SOURCE-OFFICIAL|feed:test",),
    )
    official = source("SDA-SOURCE-OFFICIAL", "A")
    lead = source("SDA-SOURCE-LEAD", "E")

    obs = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL"),
        source=official,
        canonical_text="Official contract award for F-15SA support.",
        policy=policy,
    )
    validate_instance("monitoring-observation.schema.json", obs, failures)
    expect(obs["routing_policy_id"] == "M4-ROUTING-v0.1", "routing policy identity missing", failures)
    expect(obs["ai_extraction_eligible"] is True, "explicitly allowlisted feed was not extraction eligible", failures)
    route = route_observation(obs, created_at="2026-09-28T00:01:00Z")
    item = dict(route.item or {})
    validate_instance("editorial-queue-item.schema.json", item, failures)
    expect(route.action == "created", "relevant new content did not create queue item", failures)
    expect(item.get("lane") == "candidate_extraction", "allowlisted A-class feed did not enter candidate extraction", failures)
    expect(item.get("canonical_mutation_authority") is False, "queue item acquired mutation authority", failures)

    unchanged = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", status="unchanged", observed_at="2026-09-28T01:00:00Z"),
        source=official,
        canonical_text="Official contract award for F-15SA support.",
        policy=policy,
    )
    expect(route_observation(unchanged, created_at="2026-09-28T01:01:00Z").action == "ignored", "unchanged content re-entered queue", failures)

    irrelevant = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", canonical_sha="c" * 64),
        source=official,
        canonical_text="Administrative holiday notice.",
        policy=policy,
    )
    expect(route_observation(irrelevant, created_at="2026-09-28T00:02:00Z").action == "ignored", "irrelevant content entered queue", failures)

    substring = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", canonical_sha="d" * 64),
        source=official,
        canonical_text="Exercising administrative discretion.",
        policy=policy,
    )
    expect(substring["relevance"]["classification"] == "irrelevant", "whole-term matching regressed", failures)

    e_obs = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-LEAD", canonical_sha="9" * 64, raw_sha="1" * 64, document_id="SDA-DOC-LEAD"),
        source=lead,
        canonical_text="F-15SA exercise notice.",
        policy=policy,
    )
    expect(e_obs["ai_extraction_eligible"] is False, "E-class source became extraction eligible", failures)
    e_item = dict(route_observation(e_obs, created_at="2026-09-28T00:03:00Z").item or {})
    expect(e_item.get("lane") == "discovery_review", "E-class lead escaped discovery review", failures)

    a_copy = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-OFFICIAL",
            canonical_sha="9" * 64,
            raw_sha="2" * 64,
            observed_at="2026-09-28T00:04:00Z",
            document_id="SDA-DOC-OFFICIAL-DUP",
        ),
        source=official,
        canonical_text="F-15SA exercise notice.",
        policy=policy,
    )
    promoted = route_observation(a_copy, created_at="2026-09-28T00:05:00Z", existing_item=e_item)
    promoted_item = dict(promoted.item or {})
    validate_instance("editorial-queue-item.schema.json", promoted_item, failures)
    expect(promoted_item.get("lane") == "candidate_extraction", "authoritative duplicate did not promote exact-content group", failures)
    expect(set(promoted_item.get("source_ids", [])) == {"SDA-SOURCE-LEAD", "SDA-SOURCE-OFFICIAL"}, "dedupe group lost source provenance", failures)

    red = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-OFFICIAL",
            canonical_sha="9" * 64,
            raw_sha="3" * 64,
            observed_at="2026-09-28T00:06:00Z",
            document_id="SDA-DOC-RED-DUP",
        ),
        source=official,
        canonical_text="F-15SA exercise with live unit movement details.",
        policy=policy,
    )
    red_item = dict(
        route_observation(red, created_at="2026-09-28T00:07:00Z", existing_item=promoted_item).item or {}
    )
    validate_instance("editorial-queue-item.schema.json", red_item, failures)
    expect(red_item.get("lane") == "restricted_human", "RED observation did not dominate dedupe group", failures)
    expect(red_item.get("ai_extraction_allowed") is False, "RED group allowed automated extraction", failures)

    non_allowlisted_policy = RoutingPolicy(
        policy_id="M4-ROUTING-v0.1",
        relevance_terms=("exercise",),
        restricted_terms=("live unit movement",),
        ai_extraction_feed_keys=(),
    )
    non_allowlisted = build_monitoring_observation(
        ingestion=ingestion("SDA-SOURCE-OFFICIAL", canonical_sha="8" * 64),
        source=official,
        canonical_text="Exercise announcement.",
        policy=non_allowlisted_policy,
    )
    expect(non_allowlisted["ai_extraction_eligible"] is False, "non-allowlisted feed became extraction eligible", failures)
    expect(
        (route_observation(non_allowlisted, created_at="2026-09-28T00:08:00Z").item or {}).get("lane") == "discovery_review",
        "non-allowlisted relevant feed bypassed discovery review",
        failures,
    )

    if failures:
        print("M4 editorial routing validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 deterministic monitoring/editorial routing: policy identity is retained; AI extraction is feed-opt-in; "
        "unchanged/irrelevant content is suppressed; E-class leads remain discovery-only; exact duplicates preserve provenance; "
        "RED dominates and disables extraction; queue records never gain canonical mutation authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
