#!/usr/bin/env python3
"""Validate M2 source acquisition-freshness semantics and failure boundaries."""

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
from services.ingestion.acquisition import FetchResponse, classify_fetch  # noqa: E402
from services.ingestion.document_identity import SourceAcquisitionPolicy, content_sha256  # noqa: E402
from services.presentation.source_freshness import (  # noqa: E402
    SourceFreshnessError,
    build_source_freshness_report,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(schema_name: str, instance: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(f"{schema_name} failed: " + "; ".join(error.message for error in errors))


def source(source_id: str, *, source_class: str = "A", active: bool = True) -> dict[str, Any]:
    return {
        "id": source_id,
        "publisher": {"en": f"Synthetic publisher {source_id}"},
        "source_class": source_class,
        "publisher_type": "government",
        "homepage": "https://example.invalid/",
        "jurisdiction": None,
        "notes": "Synthetic validation fixture only.",
        "active": active,
    }


def receipt(source_id: str, observed_at: str, *, status_code: int = 200) -> dict[str, Any]:
    return {
        "source_id": source_id,
        "observed_at": observed_at,
        "status_code": status_code,
    }


def main() -> int:
    failures: list[str] = []
    sources = [
        source("SDA-SOURCE-M2-FRESH"),
        source("SDA-SOURCE-M2-DUE", source_class="B"),
        source("SDA-SOURCE-M2-NEVER", source_class="C"),
        source("SDA-SOURCE-M2-INACTIVE", active=False),
    ]
    receipts = [
        receipt("SDA-SOURCE-M2-FRESH", "2026-01-09T00:00:00Z"),
        receipt("SDA-SOURCE-M2-FRESH", "2026-01-10T00:00:00+00:00"),
        receipt("SDA-SOURCE-M2-DUE", "2026-01-01T00:00:00Z"),
        receipt("SDA-SOURCE-M2-INACTIVE", "2026-01-10T00:00:00Z"),
    ]

    for item in sources:
        validate_instance("source.schema.json", item, failures)

    report = build_source_freshness_report(
        sources=sources,
        retrieval_receipts=receipts,
        as_of="2026-01-11T00:00:00Z",
        default_poll_days=7,
        source_poll_days={"SDA-SOURCE-M2-DUE": 10},
    )
    validate_instance("source-freshness-report.schema.json", report, failures)

    expect(
        report["summary"] == {"total": 3, "fresh": 1, "due": 1, "never_retrieved": 1},
        "source freshness summary changed",
        failures,
    )
    by_id = {item["source_id"]: item for item in report["items"]}
    expect("SDA-SOURCE-M2-INACTIVE" not in by_id, "inactive Source entered workload", failures)
    fresh = by_id["SDA-SOURCE-M2-FRESH"]
    expect(fresh["status"] == "fresh", "recent retrieval must remain fresh", failures)
    expect(fresh["receipt_count"] == 2, "successful receipt count changed", failures)
    expect(
        fresh["latest_observed_at"] == "2026-01-10T00:00:00Z",
        "latest receipt timestamp was not normalized",
        failures,
    )

    due = by_id["SDA-SOURCE-M2-DUE"]
    expect(due["status"] == "due", "receipt at polling deadline must be due", failures)
    expect(due["next_check_due_at"] == "2026-01-11T00:00:00Z", "poll deadline changed", failures)
    expect(
        "does not imply factual staleness" in due["reason"],
        "due status must not imply factual staleness",
        failures,
    )

    never = by_id["SDA-SOURCE-M2-NEVER"]
    expect(
        never["status"] == "never_retrieved" and never["latest_observed_at"] is None,
        "unretrieved Source must remain explicit",
        failures,
    )

    reversed_report = build_source_freshness_report(
        sources=list(reversed(sources)),
        retrieval_receipts=list(reversed(receipts)),
        as_of="2026-01-11T00:00:00+00:00",
        default_poll_days=7,
        source_poll_days={"SDA-SOURCE-M2-DUE": 10},
    )
    expect(report == reversed_report, "source freshness output must be order-independent", failures)

    # Prove unchanged canonical content still refreshes acquisition health via receipt.
    policy = SourceAcquisitionPolicy(
        source_id="SDA-SOURCE-M2-FRESH",
        document_key="m2-source-freshness-fixture",
        canonical_url="https://official.example.test/source-freshness",
        allowed_hosts=("official.example.test",),
        language="en",
        document_type="press_release",
    )
    content = b"<article>same canonical content</article>"
    response = FetchResponse(
        content=content,
        retrieved_url=policy.canonical_url,
        status_code=200,
        media_type="text/html",
        etag=None,
        last_modified=None,
    )
    first = classify_fetch(
        policy=policy,
        response=response,
        observed_at="2026-01-01T00:00:00Z",
        canonical_content_sha256=content_sha256(content),
        canonical_content_length_bytes=len(content),
    )
    unchanged = classify_fetch(
        policy=policy,
        response=response,
        observed_at="2026-01-10T00:00:00Z",
        canonical_content_sha256=content_sha256(content),
        canonical_content_length_bytes=len(content),
        previous_document=first.document,
    )
    expect(unchanged.status == "unchanged", "integration fixture must remain unchanged", failures)
    expect(
        unchanged.document["retrieved_at"] == first.document["retrieved_at"],
        "unchanged fetch must not rewrite immutable Document retrieval metadata",
        failures,
    )
    expect(
        unchanged.receipt.source_id == policy.source_id
        and unchanged.receipt.observed_at == "2026-01-10T00:00:00Z",
        "retrieval receipt must preserve source identity and latest observation time",
        failures,
    )
    integration_report = build_source_freshness_report(
        sources=[sources[0]],
        retrieval_receipts=[first.receipt, unchanged.receipt],
        as_of="2026-01-11T00:00:00Z",
        default_poll_days=7,
    )
    expect(
        integration_report["items"][0]["status"] == "fresh"
        and integration_report["items"][0]["latest_observed_at"] == "2026-01-10T00:00:00Z",
        "unchanged re-fetch must refresh source monitoring health without new Document",
        failures,
    )

    future_receipts = copy.deepcopy(receipts)
    future_receipts[0]["observed_at"] = "2026-01-12T00:00:00Z"
    try:
        build_source_freshness_report(
            sources=sources,
            retrieval_receipts=future_receipts,
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
        )
        failures.append("future retrieval receipt was accepted")
    except SourceFreshnessError:
        pass

    try:
        build_source_freshness_report(
            sources=sources,
            retrieval_receipts=receipts,
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
            source_poll_days={"SDA-SOURCE-M2-UNKNOWN": 1},
        )
        failures.append("poll policy for unknown Source was accepted")
    except SourceFreshnessError:
        pass

    try:
        build_source_freshness_report(
            sources=sources,
            retrieval_receipts=[receipt("SDA-SOURCE-M2-UNKNOWN", "2026-01-10T00:00:00Z")],
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
        )
        failures.append("receipt with unknown Source was accepted")
    except SourceFreshnessError:
        pass

    try:
        build_source_freshness_report(
            sources=sources,
            retrieval_receipts=[receipt("SDA-SOURCE-M2-FRESH", "2026-01-10T00:00:00Z", status_code=500)],
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
        )
        failures.append("failed HTTP receipt was accepted as successful freshness evidence")
    except SourceFreshnessError:
        pass

    if failures:
        print("M2 source freshness validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M2 source acquisition freshness from retrieval receipts: unchanged re-fetches "
        "refresh monitoring health without new Documents, polling deadlines are explicit, and "
        "monitoring health never becomes a factual-truth judgment."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
