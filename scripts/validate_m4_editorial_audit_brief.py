#!/usr/bin/env python3
"""Validate deterministic M4 editorial audit and daily brief projections."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.intelligence.editorial_audit import (  # noqa: E402
    EditorialAuditError,
    build_daily_editorial_brief,
    build_editorial_audit_report,
)
from services.presentation.source_freshness import build_source_freshness_report  # noqa: E402
from services.presentation.staleness import build_staleness_report  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except EditorialAuditError:
        return
    failures.append(f"{label} did not fail closed")


def validate(schema_name: str, value: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    errors = list(
        Draft202012Validator(
            schemas[schema_name], registry=registry, format_checker=FormatChecker()
        ).iter_errors(value)
    )
    if errors:
        failures.append(
            f"{schema_name}: " + "; ".join(error.message for error in errors)
        )


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, value: Any) -> str:
    digest = hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()
    return f"{prefix}-{digest[:24].upper()}"


def claim(
    claim_id: str,
    *,
    state: str = "active",
    confidence: str = "verified",
    verified_at: str | None,
) -> dict[str, Any]:
    return {
        "id": claim_id,
        "subject_id": "SDA-EQUIP-AUDIT",
        "predicate_id": "equipment.service_state",
        "value": {"kind": "string", "value": "operational", "language": None},
        "confidence": confidence,
        "evidence_links": [{"evidence_id": "SDA-EVID-AUDIT", "role": "supports"}],
        "claim_state": state,
        "supersedes_claim_ids": [],
        "verified_at": verified_at,
        "created_at": "2026-01-01T00:00:00Z",
    }


def source(source_id: str, source_class: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "publisher": {"en": source_id},
        "source_class": source_class,
        "publisher_type": "government",
        "homepage": None,
        "jurisdiction": "Saudi Arabia",
        "notes": None,
        "active": True,
    }


def queue_item(
    queue_id: str,
    *,
    lane: str,
    state: str,
    priority: str,
    created_at: str = "2026-01-15T00:00:00Z",
) -> dict[str, Any]:
    return {
        "id": queue_id,
        "observation_ids": [f"SDA-MON-{queue_id}"],
        "source_ids": ["SDA-SOURCE-AUDIT-A"],
        "document_ids": [f"SDA-DOC-{queue_id}"],
        "dedupe_key": "sha256:" + ("a" if queue_id.endswith("1") else "b") * 64,
        "lane": lane,
        "state": state,
        "priority": priority,
        "reason_codes": [f"lane:{lane}"],
        "ai_extraction_allowed": lane == "candidate_extraction",
        "canonical_mutation_authority": False,
        "created_at": created_at,
    }


def fixtures() -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    as_of = "2026-02-01T00:00:00Z"
    claims = [
        claim("SDA-CLAIM-AUDIT-FRESH", verified_at="2026-01-25T00:00:00Z"),
        claim("SDA-CLAIM-AUDIT-DUE", verified_at="2025-12-01T00:00:00Z"),
        claim(
            "SDA-CLAIM-AUDIT-DISPUTED",
            state="disputed",
            confidence="unverified",
            verified_at=None,
        ),
    ]
    staleness = build_staleness_report(
        claims=claims,
        as_of=as_of,
        default_review_days=30,
    )

    sources = [source("SDA-SOURCE-AUDIT-A", "A"), source("SDA-SOURCE-AUDIT-C", "C")]
    feeds = [
        {"source_id": "SDA-SOURCE-AUDIT-A", "document_key": "feed:a"},
        {"source_id": "SDA-SOURCE-AUDIT-A", "document_key": "feed:a-secondary"},
        {"source_id": "SDA-SOURCE-AUDIT-C", "document_key": "feed:c"},
    ]
    receipts = [
        {
            "source_id": "SDA-SOURCE-AUDIT-C",
            "document_key": "feed:c",
            "observed_at": "2026-01-01T00:00:00Z",
            "status_code": 200,
        }
    ]
    freshness = build_source_freshness_report(
        sources=sources,
        feeds=feeds,
        retrieval_receipts=receipts,
        as_of=as_of,
        default_poll_days=7,
    )
    queue = [
        queue_item(
            "SDA-QUEUE-AUDIT-1",
            lane="candidate_extraction",
            state="queued",
            priority="high",
        ),
        queue_item(
            "SDA-QUEUE-AUDIT-2",
            lane="discovery_review",
            state="claimed",
            priority="normal",
        ),
        {
            **queue_item(
                "SDA-QUEUE-AUDIT-3",
                lane="candidate_extraction",
                state="completed",
                priority="normal",
            ),
            "dedupe_key": "sha256:" + "c" * 64,
        },
    ]
    return staleness, freshness, queue


def build_report(
    *,
    staleness: dict[str, Any],
    freshness: dict[str, Any],
    queue: list[dict[str, Any]],
    as_of: str,
    queue_snapshot_as_of: str | None = None,
) -> dict[str, Any]:
    return build_editorial_audit_report(
        staleness_report=staleness,
        source_freshness_report=freshness,
        queue_items=queue,
        queue_snapshot_as_of=queue_snapshot_as_of or as_of,
        as_of=as_of,
    )


def main() -> int:
    failures: list[str] = []
    staleness, freshness, queue = fixtures()
    as_of = "2026-02-01T00:00:00Z"

    report = build_report(
        staleness=staleness,
        freshness=freshness,
        queue=queue,
        as_of=as_of,
    )
    validate("editorial-audit-report.schema.json", report, failures)
    expect(report["summary"] == {
        "total": 7,
        "high": 4,
        "normal": 3,
        "claim_review_required": 2,
        "source_monitoring_required": 3,
        "queue_action_required": 2,
    }, "editorial audit summary changed", failures)
    expect(
        all(item["subject_id"] != "SDA-CLAIM-AUDIT-FRESH" for item in report["findings"]),
        "fresh Claim leaked into audit findings",
        failures,
    )
    expect(
        all(item["subject_id"] != "SDA-QUEUE-AUDIT-3" for item in report["findings"]),
        "completed queue item leaked into audit findings",
        failures,
    )
    expect(
        any(
            item["subject_id"] == "SDA-SOURCE-AUDIT-A"
            and item["priority"] == "high"
            and "acquisition:never_retrieved" in item["reason_codes"]
            for item in report["findings"]
        ),
        "unmonitored authoritative feed was not high priority",
        failures,
    )

    brief = build_daily_editorial_brief(audit_report=report)
    validate("editorial-daily-brief.schema.json", brief, failures)
    expect(brief["audit_report_id"] == report["id"], "daily brief lost audit report identity", failures)
    expect(brief["summary"] == {"total_actions": 7, "high_priority_actions": 4}, "daily brief summary changed", failures)
    expect(len(brief["sections"]["claim_review"]) == 2, "claim-review section count changed", failures)
    expect(len(brief["sections"]["source_monitoring"]) == 3, "source-monitoring section count changed", failures)
    expect(len(brief["sections"]["editorial_queue"]) == 2, "queue section count changed", failures)
    authoritative_feed_keys = {
        item["context"].get("feed_key")
        for item in brief["sections"]["source_monitoring"]
        if item["subject_id"] == "SDA-SOURCE-AUDIT-A"
    }
    expect(
        authoritative_feed_keys == {"feed:a", "feed:a-secondary"},
        "daily brief collapsed multiple feeds for one Source",
        failures,
    )

    reordered = build_report(
        staleness=staleness,
        freshness=freshness,
        queue=list(reversed(queue)),
        as_of=as_of,
    )
    expect(reordered == report, "queue input order changed deterministic audit output", failures)

    stale_time = copy.deepcopy(freshness)
    stale_time["as_of"] = "2026-02-02T00:00:00Z"
    expect_raises(
        "misaligned operational report as_of",
        lambda: build_report(
            staleness=staleness,
            freshness=stale_time,
            queue=queue,
            as_of=as_of,
        ),
        failures,
    )
    expect_raises(
        "misaligned queue snapshot as_of",
        lambda: build_report(
            staleness=staleness,
            freshness=freshness,
            queue=queue,
            as_of=as_of,
            queue_snapshot_as_of="2026-02-02T00:00:00Z",
        ),
        failures,
    )

    duplicate_queue = [queue[0], copy.deepcopy(queue[0])]
    expect_raises(
        "duplicate editorial queue IDs",
        lambda: build_report(
            staleness=staleness,
            freshness=freshness,
            queue=duplicate_queue,
            as_of=as_of,
        ),
        failures,
    )

    future_queue = [
        queue_item(
            "SDA-QUEUE-AUDIT-FUTURE",
            lane="candidate_extraction",
            state="queued",
            priority="normal",
            created_at="2026-02-02T00:00:00Z",
        )
    ]
    expect_raises(
        "future queue item",
        lambda: build_report(
            staleness=staleness,
            freshness=freshness,
            queue=future_queue,
            as_of=as_of,
        ),
        failures,
    )

    invalid_queue_authority = [copy.deepcopy(queue[1])]
    invalid_queue_authority[0]["ai_extraction_allowed"] = True
    expect_raises(
        "queue extraction/lane inconsistency",
        lambda: build_report(
            staleness=staleness,
            freshness=freshness,
            queue=invalid_queue_authority,
            as_of=as_of,
        ),
        failures,
    )

    tampered_authority = copy.deepcopy(report)
    tampered_authority["authority"]["canonical_mutation_authority"] = True
    expect_raises(
        "audit report with widened authority",
        lambda: build_daily_editorial_brief(audit_report=tampered_authority),
        failures,
    )

    tampered_finding = copy.deepcopy(report)
    tampered_finding["findings"][0]["priority"] = "normal"
    expect_raises(
        "tampered content-addressed audit finding",
        lambda: build_daily_editorial_brief(audit_report=tampered_finding),
        failures,
    )

    tampered_summary = copy.deepcopy(report)
    tampered_summary["summary"]["high"] = 0
    expect_raises(
        "audit summary inconsistent with findings",
        lambda: build_daily_editorial_brief(audit_report=tampered_summary),
        failures,
    )

    self_consistent_invalid = copy.deepcopy(report)
    invalid_finding = self_consistent_invalid["findings"][0]
    invalid_finding["subject_id"] = ""
    finding_body = {key: value for key, value in invalid_finding.items() if key != "id"}
    invalid_finding["id"] = _stable_id("SDA-AUDIT-FINDING", finding_body)
    report_body = {key: value for key, value in self_consistent_invalid.items() if key != "id"}
    self_consistent_invalid["id"] = _stable_id("SDA-EDITORIAL-AUDIT", report_body)
    expect_raises(
        "self-consistent invalid audit finding semantics",
        lambda: build_daily_editorial_brief(audit_report=self_consistent_invalid),
        failures,
    )

    if failures:
        print("M4 editorial audit/brief validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 deterministic editorial audit + daily brief: aligned staleness/acquisition/current-queue snapshot inputs, "
        "action-only findings, deterministic priority/grouping, completed-item suppression, multi-feed action identity, semantic/content integrity, and zero truth/approval/mutation authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
