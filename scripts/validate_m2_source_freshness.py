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
        failures.append(
            f"{schema_name} failed: " + "; ".join(error.message for error in errors)
        )


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


def document(document_id: str, source_id: str, retrieved_at: str) -> dict[str, Any]:
    return {
        "id": document_id,
        "source_id": source_id,
        "title": {"en": f"Synthetic document {document_id}"},
        "canonical_url": f"https://example.invalid/{document_id.lower()}",
        "retrieved_url": f"https://example.invalid/{document_id.lower()}",
        "published_at": None,
        "retrieved_at": retrieved_at,
        "language": "en",
        "document_type": "other",
        "media_type": "text/plain",
        "content_sha256": (document_id[-1].lower() if document_id[-1].lower() in "abcdef" else "a") * 64,
        "content_length_bytes": 100,
        "version_of": None,
        "publisher_document_id": None,
        "access_notes": "Synthetic fixture.",
        "licensing_notes": None,
    }


def main() -> int:
    failures: list[str] = []
    sources = [
        source("SDA-SOURCE-M2-FRESH"),
        source("SDA-SOURCE-M2-DUE", source_class="B"),
        source("SDA-SOURCE-M2-NEVER", source_class="C"),
        source("SDA-SOURCE-M2-INACTIVE", active=False),
    ]
    documents = [
        document("SDA-DOC-M2-FRESH-A", "SDA-SOURCE-M2-FRESH", "2026-01-09T00:00:00Z"),
        document("SDA-DOC-M2-FRESH-B", "SDA-SOURCE-M2-FRESH", "2026-01-10T00:00:00+00:00"),
        document("SDA-DOC-M2-DUE-A", "SDA-SOURCE-M2-DUE", "2026-01-01T00:00:00Z"),
        document("SDA-DOC-M2-INACTIVE-A", "SDA-SOURCE-M2-INACTIVE", "2026-01-10T00:00:00Z"),
    ]

    for item in sources:
        validate_instance("source.schema.json", item, failures)
    for item in documents:
        validate_instance("document.schema.json", item, failures)

    report = build_source_freshness_report(
        sources=sources,
        documents=documents,
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
    expect(
        "SDA-SOURCE-M2-INACTIVE" not in by_id,
        "inactive Source must not enter active acquisition workload",
        failures,
    )
    fresh = by_id["SDA-SOURCE-M2-FRESH"]
    expect(fresh["status"] == "fresh", "recent retrieval must remain fresh", failures)
    expect(
        fresh["latest_document_id"] == "SDA-DOC-M2-FRESH-B",
        "latest retrieval selection changed",
        failures,
    )
    expect(
        fresh["latest_retrieved_at"] == "2026-01-10T00:00:00Z",
        "latest retrieval timestamp was not normalized",
        failures,
    )

    due = by_id["SDA-SOURCE-M2-DUE"]
    expect(due["status"] == "due", "retrieval at polling deadline must be due", failures)
    expect(
        due["next_retrieval_due_at"] == "2026-01-11T00:00:00Z",
        "source polling deadline changed",
        failures,
    )
    expect(
        "does not imply factual staleness" in due["reason"],
        "due status must not imply stale/false source content",
        failures,
    )

    never = by_id["SDA-SOURCE-M2-NEVER"]
    expect(
        never["status"] == "never_retrieved" and never["latest_retrieved_at"] is None,
        "unretrieved Source must remain explicit",
        failures,
    )

    reversed_report = build_source_freshness_report(
        sources=list(reversed(sources)),
        documents=list(reversed(documents)),
        as_of="2026-01-11T00:00:00+00:00",
        default_poll_days=7,
        source_poll_days={"SDA-SOURCE-M2-DUE": 10},
    )
    expect(report == reversed_report, "source freshness output must be order-independent", failures)

    future_documents = copy.deepcopy(documents)
    future_documents[0]["retrieved_at"] = "2026-01-12T00:00:00Z"
    try:
        build_source_freshness_report(
            sources=sources,
            documents=future_documents,
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
        )
        failures.append("future Document retrieval was accepted")
    except SourceFreshnessError:
        pass

    try:
        build_source_freshness_report(
            sources=sources,
            documents=documents,
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
            source_poll_days={"SDA-SOURCE-M2-UNKNOWN": 1},
        )
        failures.append("poll policy for unknown Source was accepted")
    except SourceFreshnessError:
        pass

    duplicate_sources = [sources[0], copy.deepcopy(sources[0])]
    try:
        build_source_freshness_report(
            sources=duplicate_sources,
            documents=[],
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
        )
        failures.append("duplicate Source ID was accepted")
    except SourceFreshnessError:
        pass

    orphan_document = [document("SDA-DOC-M2-ORPHAN", "SDA-SOURCE-M2-UNKNOWN", "2026-01-10T00:00:00Z")]
    try:
        build_source_freshness_report(
            sources=sources,
            documents=orphan_document,
            as_of="2026-01-11T00:00:00Z",
            default_poll_days=7,
        )
        failures.append("Document with unknown Source was accepted")
    except SourceFreshnessError:
        pass

    try:
        build_source_freshness_report(
            sources=sources,
            documents=documents,
            as_of="2026-01-11T00:00:00",
            default_poll_days=7,
        )
        failures.append("timezone-naive as_of was accepted")
    except SourceFreshnessError:
        pass

    if failures:
        print("M2 source freshness validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M2 source acquisition freshness: explicit polling policy, exact deadline "
        "semantics, latest-retrieval selection, never-retrieved state, active-source filtering, "
        "order independence, and no inference from monitoring health to factual truth."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
