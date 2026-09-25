#!/usr/bin/env python3
"""Validate M1 deterministic acquisition/idempotency invariants without network IO."""

from __future__ import annotations

import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.ingestion.acquisition import FetchResponse, classify_fetch  # noqa: E402
from services.ingestion.document_identity import (  # noqa: E402
    IngestionContractError,
    SourceAcquisitionPolicy,
    document_id,
    validate_policy,
    validate_retrieved_url,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    policy = SourceAcquisitionPolicy(
        source_id="SDA-SOURCE-TEST-OFFICIAL",
        document_key="official-test-article-1",
        canonical_url="https://official.example.test/articles/1",
        allowed_hosts=("official.example.test",),
        language="en",
        document_type="press_release",
        publisher_document_id="1",
    )

    try:
        validate_policy(policy)
    except Exception as exc:  # noqa: BLE001
        failures.append(f"valid acquisition policy rejected: {exc}")

    content_v1 = b"<html><body><p>fixture version one</p></body></html>"
    response_v1 = FetchResponse(
        content=content_v1,
        retrieved_url=policy.canonical_url,
        status_code=200,
        media_type="text/html",
        etag='"v1"',
        last_modified="Thu, 01 Jan 2026 00:00:00 GMT",
    )

    first = classify_fetch(
        policy=policy,
        response=response_v1,
        observed_at="2026-01-01T00:00:00Z",
        title={"en": "Synthetic official fixture"},
        published_at={"value": "2026-01-01", "precision": "day"},
    )
    expect(first.status == "new", "first observation must be new", failures)

    same = classify_fetch(
        policy=policy,
        response=response_v1,
        observed_at="2026-01-02T00:00:00Z",
        previous_document=first.document,
    )
    expect(same.status == "unchanged", "identical bytes must be unchanged", failures)
    expect(
        same.document["id"] == first.document["id"],
        "identical bytes must retain the same Document ID",
        failures,
    )
    expect(
        same.document["retrieved_at"] == first.document["retrieved_at"],
        "an unchanged re-fetch must not silently rewrite immutable Document retrieval metadata",
        failures,
    )

    response_v2 = FetchResponse(
        content=b"<html><body><p>fixture version two</p></body></html>",
        retrieved_url=policy.canonical_url,
        status_code=200,
        media_type="text/html",
        etag='"v2"',
        last_modified="Fri, 02 Jan 2026 00:00:00 GMT",
    )
    changed = classify_fetch(
        policy=policy,
        response=response_v2,
        observed_at="2026-01-03T00:00:00Z",
        previous_document=first.document,
    )
    expect(changed.status == "changed", "changed bytes must create a new version", failures)
    expect(
        changed.document["id"] != first.document["id"],
        "changed bytes must produce a different content-derived Document ID",
        failures,
    )
    expect(
        changed.document["version_of"] == first.document["id"],
        "changed content must point to the previous Document version",
        failures,
    )

    deterministic = document_id(
        policy.document_key, first.document["content_sha256"]
    )
    expect(
        deterministic == first.document["id"],
        "Document ID derivation must be deterministic",
        failures,
    )

    try:
        validate_retrieved_url(policy, "https://redirected.example.test/articles/1")
        failures.append("non-allowlisted redirect host was accepted")
    except IngestionContractError:
        pass

    try:
        validate_policy(
            SourceAcquisitionPolicy(
                source_id="SDA-SOURCE-BAD",
                document_key="bad-http-source",
                canonical_url="http://official.example.test/articles/1",
                allowed_hosts=("official.example.test",),
                language="en",
                document_type="press_release",
            )
        )
        failures.append("non-HTTPS canonical URL was accepted")
    except IngestionContractError:
        pass

    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas["document.schema.json"],
        registry=registry,
        format_checker=FormatChecker(),
    )
    for label, record in (("first", first.document), ("changed", changed.document)):
        errors = list(validator.iter_errors(record))
        if errors:
            failures.append(
                f"{label} generated Document failed schema: "
                + "; ".join(error.message for error in errors)
            )

    if failures:
        print("M1 ingestion validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("Validated deterministic M1 acquisition, idempotency, versioning, and URL policy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
