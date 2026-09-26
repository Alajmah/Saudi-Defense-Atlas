#!/usr/bin/env python3
"""Validate M1 deterministic acquisition and bounded parsing without network IO."""

from __future__ import annotations

import json
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
    content_sha256,
    document_id,
    validate_policy,
    validate_retrieved_url,
)
from services.ingestion.registry import load_registered_document  # noqa: E402
from services.ingestion.usaf_f15sa_2020 import (  # noqa: E402
    SourceParseError,
    analyze_release,
    materialize_evidence,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(validator: Draft202012Validator, record: dict, label: str) -> list[str]:
    errors = list(validator.iter_errors(record))
    if not errors:
        return []
    return [
        f"{label} failed schema: " + "; ".join(error.message for error in errors)
    ]


def article_fixture(*, chrome: str, producer_phrase: str = "last delivery") -> bytes:
    return f"""
    <html><body>
      <p>Navigation {chrome}</p>
      <h1>AFLCMC delivers final F-15SA to Royal Saudi Air Force</h1>
      <div>Published Dec. 11, 2020</div>
      <p>Final F-15SA aircraft were delivered Dec. 10 to the Royal Saudi Air Force.</p>
      <p>The Boeing-produced aircraft represented the {producer_phrase} in this synthetic fixture.</p>
      <p>The F-15SA is an advanced version of the F-15S and is associated with the Royal Saudi Air Force.</p>
      <p>This article fixture also mentions associated spares, simulators, training, technical documentation and program support.</p>
      <p>Featured news {chrome}</p>
    </body></html>
    """.encode("utf-8")


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

    content_v1 = b"<article><p>fixture version one</p></article>"
    digest_v1 = content_sha256(content_v1)
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
        canonical_content_sha256=digest_v1,
        canonical_content_length_bytes=len(content_v1),
        title={"en": "Synthetic official fixture"},
        published_at={"value": "2026-01-01", "precision": "day"},
    )
    expect(first.status == "new", "first observation must be new", failures)

    same = classify_fetch(
        policy=policy,
        response=response_v1,
        observed_at="2026-01-02T00:00:00Z",
        canonical_content_sha256=digest_v1,
        canonical_content_length_bytes=len(content_v1),
        previous_document=first.document,
    )
    expect(same.status == "unchanged", "identical canonical content must be unchanged", failures)
    expect(
        same.document["id"] == first.document["id"],
        "identical canonical content must retain the same Document ID",
        failures,
    )
    expect(
        same.document["retrieved_at"] == first.document["retrieved_at"],
        "an unchanged re-fetch must not silently rewrite immutable Document retrieval metadata",
        failures,
    )

    content_v2 = b"<article><p>fixture version two</p></article>"
    digest_v2 = content_sha256(content_v2)
    response_v2 = FetchResponse(
        content=content_v2,
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
        canonical_content_sha256=digest_v2,
        canonical_content_length_bytes=len(content_v2),
        previous_document=first.document,
    )
    expect(changed.status == "changed", "changed canonical content must create a new version", failures)
    expect(
        changed.document["id"] != first.document["id"],
        "changed canonical content must produce a different Document ID",
        failures,
    )
    expect(
        changed.document["version_of"] == first.document["id"],
        "changed content must point to the previous Document version",
        failures,
    )

    deterministic = document_id(policy.document_key, first.document["content_sha256"])
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

    schemas, schema_registry = build_registry()
    document_validator = Draft202012Validator(
        schemas["document.schema.json"],
        registry=schema_registry,
        format_checker=FormatChecker(),
    )
    source_validator = Draft202012Validator(
        schemas["source.schema.json"],
        registry=schema_registry,
        format_checker=FormatChecker(),
    )
    evidence_validator = Draft202012Validator(
        schemas["evidence.schema.json"],
        registry=schema_registry,
        format_checker=FormatChecker(),
    )

    for label, record in (("first", first.document), ("changed", changed.document)):
        failures.extend(validate_instance(document_validator, dict(record), label))

    source_path = ROOT / "data" / "sources" / "usaf.json"
    with source_path.open("r", encoding="utf-8") as handle:
        source_record = json.load(handle)
    failures.extend(validate_instance(source_validator, source_record, "USAF source"))

    registered_policy: SourceAcquisitionPolicy | None = None
    try:
        registered_policy, metadata = load_registered_document(
            "USAF_F15SA_FINAL_DELIVERY_2020"
        )
        expect(
            registered_policy.source_id == source_record["id"],
            "registered document source_id must resolve to the checked-in Source record",
            failures,
        )
        expect(
            metadata.get("expected_title")
            == "AFLCMC delivers final F-15SA to Royal Saudi Air Force",
            "registered M1 document title changed unexpectedly",
            failures,
        )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"registered M1 document policy failed validation: {exc}")

    base_html = article_fixture(chrome="alpha")
    chrome_changed_html = article_fixture(chrome="beta")
    body_changed_html = article_fixture(chrome="beta", producer_phrase="final delivery")

    try:
        parsed_base = analyze_release(base_html)
        parsed_chrome = analyze_release(chrome_changed_html)
        parsed_body_change = analyze_release(body_changed_html)

        expect(parsed_base.published_date == "2020-12-11", "publication date parse drift", failures)
        expect(
            parsed_base.reported_delivery_date == "2020-12-10",
            "reported delivery date parse drift",
            failures,
        )
        expect(
            parsed_base.canonical_content_sha256
            == parsed_chrome.canonical_content_sha256,
            "page-chrome changes must not change canonical Document fingerprint",
            failures,
        )
        expect(
            content_sha256(base_html) != content_sha256(chrome_changed_html),
            "test fixture must prove raw retrieval bytes actually changed",
            failures,
        )
        expect(
            parsed_base.canonical_content_sha256
            != parsed_body_change.canonical_content_sha256,
            "article-body changes must change canonical Document fingerprint",
            failures,
        )
        expect(
            tuple(item.selector for item in parsed_base.evidence_candidates)
            == tuple(item.selector for item in parsed_chrome.evidence_candidates),
            "article-relative Evidence selectors must survive page-chrome changes",
            failures,
        )

        if registered_policy is not None:
            base_response = FetchResponse(
                content=base_html,
                retrieved_url=registered_policy.canonical_url,
                status_code=200,
                media_type="text/html",
                etag='"raw-alpha"',
                last_modified=None,
            )
            chrome_response = FetchResponse(
                content=chrome_changed_html,
                retrieved_url=registered_policy.canonical_url,
                status_code=200,
                media_type="text/html",
                etag='"raw-beta"',
                last_modified=None,
            )
            body_response = FetchResponse(
                content=body_changed_html,
                retrieved_url=registered_policy.canonical_url,
                status_code=200,
                media_type="text/html",
                etag='"body-beta"',
                last_modified=None,
            )

            base_result = classify_fetch(
                policy=registered_policy,
                response=base_response,
                observed_at="2026-01-04T00:00:00Z",
                canonical_content_sha256=parsed_base.canonical_content_sha256,
                canonical_content_length_bytes=parsed_base.canonical_content_length_bytes,
                title={"en": parsed_base.title},
                published_at={"value": parsed_base.published_date, "precision": "day"},
            )
            chrome_result = classify_fetch(
                policy=registered_policy,
                response=chrome_response,
                observed_at="2026-01-05T00:00:00Z",
                canonical_content_sha256=parsed_chrome.canonical_content_sha256,
                canonical_content_length_bytes=parsed_chrome.canonical_content_length_bytes,
                previous_document=base_result.document,
            )
            body_result = classify_fetch(
                policy=registered_policy,
                response=body_response,
                observed_at="2026-01-06T00:00:00Z",
                canonical_content_sha256=parsed_body_change.canonical_content_sha256,
                canonical_content_length_bytes=parsed_body_change.canonical_content_length_bytes,
                previous_document=base_result.document,
            )

            expect(
                chrome_result.status == "unchanged",
                "chrome-only change must not create a Document version",
                failures,
            )
            expect(
                chrome_result.document["id"] == base_result.document["id"],
                "chrome-only change must retain Document ID",
                failures,
            )
            expect(
                chrome_result.receipt.raw_content_sha256
                != base_result.receipt.raw_content_sha256,
                "raw retrieval receipts must distinguish chrome-only response changes",
                failures,
            )
            expect(
                body_result.status == "changed",
                "article-body change must create a new Document version",
                failures,
            )
            expect(
                body_result.document["version_of"] == base_result.document["id"],
                "article-body change must link to previous Document",
                failures,
            )

            evidence = materialize_evidence(
                parsed_base,
                document_id=base_result.document["id"],
                captured_at="2026-01-04T00:00:00Z",
            )
            expect(len(evidence) == 4, "parser must emit four bounded Evidence records", failures)
            for index, record in enumerate(evidence, start=1):
                failures.extend(
                    validate_instance(evidence_validator, dict(record), f"evidence {index}")
                )
                expect(
                    record["document_id"] == base_result.document["id"],
                    "Evidence must bind to the final Document ID",
                    failures,
                )
                expect(
                    record["excerpt"] is None,
                    "deterministic parser should not copy source prose by default",
                    failures,
                )

            failures.extend(
                validate_instance(
                    document_validator, dict(base_result.document), "parsed base Document"
                )
            )
            failures.extend(
                validate_instance(
                    document_validator, dict(body_result.document), "parsed changed Document"
                )
            )
    except Exception as exc:  # noqa: BLE001
        failures.append(f"bounded parser/acquisition integration failed: {exc}")

    ambiguous_fixture = base_html.replace(
        b"</body>",
        b"<p>Another F-15SA group was delivered Dec. 10 to the Royal Saudi Air Force.</p></body>",
    )
    try:
        analyze_release(ambiguous_fixture)
        failures.append("bounded parser accepted ambiguous duplicate delivery evidence")
    except SourceParseError:
        pass

    if failures:
        print("M1 ingestion validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated deterministic M1 acquisition, canonical Document fingerprinting, "
        "retrieval receipts, idempotency/versioning, source policy, bounded parsing, "
        "and Evidence materialization."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
