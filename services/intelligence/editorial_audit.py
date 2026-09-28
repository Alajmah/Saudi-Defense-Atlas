"""Deterministic M4 editorial audit and daily-brief projections.

The auditor consumes already-accepted operational signals: Claim staleness,
registered-feed acquisition freshness, and EditorialQueueItem state. It does not
re-evaluate factual truth, approve proposals, mutate canonical knowledge, or publish.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class EditorialAuditError(ValueError):
    """Raised when operational audit inputs are inconsistent or incomplete."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_sha256(value)[:24].upper()}"


def _parse_utc(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EditorialAuditError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EditorialAuditError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise EditorialAuditError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _utc(value: Any, label: str) -> str:
    return _parse_utc(value, label).isoformat().replace("+00:00", "Z")


def _items(report: Mapping[str, Any], label: str) -> list[Mapping[str, Any]]:
    raw = report.get("items")
    if not isinstance(raw, Sequence) or isinstance(raw, (str, bytes)):
        raise EditorialAuditError(f"{label}.items must be an array")
    result: list[Mapping[str, Any]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise EditorialAuditError(f"{label}.items must contain objects")
        result.append(item)
    return result


def _string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditorialAuditError(f"{label} must be an array")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise EditorialAuditError(f"{label} contains invalid identity")
        result.append(item)
    if len(result) != len(set(result)):
        raise EditorialAuditError(f"{label} contains duplicates")
    return result


def _finding(
    *,
    kind: str,
    priority: str,
    subject_id: str,
    reason_codes: Sequence[str],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    if kind not in {"claim_review_required", "source_monitoring_required", "queue_action_required"}:
        raise EditorialAuditError("finding kind is invalid")
    if priority not in {"high", "normal"}:
        raise EditorialAuditError("finding priority is invalid")
    if not isinstance(subject_id, str) or not subject_id:
        raise EditorialAuditError("finding subject_id is required")
    reasons = sorted({str(reason) for reason in reason_codes if isinstance(reason, str) and reason})
    if not reasons:
        raise EditorialAuditError("finding requires reason codes")
    body = {
        "kind": kind,
        "priority": priority,
        "subject_id": subject_id,
        "reason_codes": reasons,
        "context": dict(context),
    }
    return {"id": _stable_id("SDA-AUDIT-FINDING", body), **body}


def _summary(findings: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "total": len(findings),
        "high": sum(item.get("priority") == "high" for item in findings),
        "normal": sum(item.get("priority") == "normal" for item in findings),
        "claim_review_required": sum(item.get("kind") == "claim_review_required" for item in findings),
        "source_monitoring_required": sum(item.get("kind") == "source_monitoring_required" for item in findings),
        "queue_action_required": sum(item.get("kind") == "queue_action_required" for item in findings),
    }


def build_editorial_audit_report(
    *,
    staleness_report: Mapping[str, Any],
    source_freshness_report: Mapping[str, Any],
    queue_items: Sequence[Mapping[str, Any]],
    as_of: str,
) -> dict[str, Any]:
    """Build one deterministic operational attention report."""

    normalized_as_of = _utc(as_of, "as_of")
    for report, label in (
        (staleness_report, "staleness_report"),
        (source_freshness_report, "source_freshness_report"),
    ):
        if _utc(report.get("as_of"), f"{label}.as_of") != normalized_as_of:
            raise EditorialAuditError(f"{label} is not aligned to audit as_of")

    findings: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for item in _items(staleness_report, "staleness_report"):
        claim_id = item.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise EditorialAuditError("staleness item requires claim_id")
        if claim_id in seen_claim_ids:
            raise EditorialAuditError(f"duplicate Claim staleness item: {claim_id}")
        seen_claim_ids.add(claim_id)
        status = item.get("status")
        state = item.get("claim_state")
        confidence = item.get("confidence")
        if status not in {"fresh", "due", "unverified"}:
            raise EditorialAuditError(f"Claim {claim_id} has invalid staleness status")
        if state not in {"active", "disputed"}:
            raise EditorialAuditError(f"Claim {claim_id} has invalid visible state")

        reasons: list[str] = []
        if status == "due":
            reasons.append("review:due")
        elif status == "unverified":
            reasons.append("review:never_verified")
        if state == "disputed":
            reasons.append("claim_state:disputed")
        if confidence == "unverified":
            reasons.append("confidence:unverified")
        if not reasons:
            continue

        priority = "high" if (
            state == "disputed" or status == "unverified" or confidence == "unverified"
        ) else "normal"
        findings.append(
            _finding(
                kind="claim_review_required",
                priority=priority,
                subject_id=claim_id,
                reason_codes=reasons,
                context={
                    "claim_id": claim_id,
                    "subject_id": item.get("subject_id"),
                    "predicate_id": item.get("predicate_id"),
                    "claim_state": state,
                    "confidence": confidence,
                    "staleness_status": status,
                    "verified_at": item.get("verified_at"),
                    "review_due_at": item.get("review_due_at"),
                },
            )
        )

    seen_feeds: set[str] = set()
    for item in _items(source_freshness_report, "source_freshness_report"):
        source_id = item.get("source_id")
        feed_key = item.get("feed_key")
        status = item.get("status")
        source_class = item.get("source_class")
        if not isinstance(source_id, str) or not source_id:
            raise EditorialAuditError("source freshness item requires source_id")
        if not isinstance(feed_key, str) or not feed_key:
            raise EditorialAuditError("source freshness item requires feed_key")
        if feed_key in seen_feeds:
            raise EditorialAuditError(f"duplicate source freshness feed: {feed_key}")
        seen_feeds.add(feed_key)
        if status not in {"fresh", "due", "never_retrieved"}:
            raise EditorialAuditError(f"feed {feed_key} has invalid freshness status")
        if source_class not in {"A", "B", "C", "D", "E"}:
            raise EditorialAuditError(f"feed {feed_key} has invalid source_class")
        if status == "fresh":
            continue

        reason = "acquisition:never_retrieved" if status == "never_retrieved" else "acquisition:poll_due"
        priority = "high" if status == "never_retrieved" and source_class in {"A", "B"} else "normal"
        findings.append(
            _finding(
                kind="source_monitoring_required",
                priority=priority,
                subject_id=source_id,
                reason_codes=[reason, f"source_class:{source_class}"],
                context={
                    "source_id": source_id,
                    "feed_key": feed_key,
                    "source_class": source_class,
                    "freshness_status": status,
                    "latest_observed_at": item.get("latest_observed_at"),
                    "next_check_due_at": item.get("next_check_due_at"),
                },
            )
        )

    seen_queue_ids: set[str] = set()
    as_of_dt = _parse_utc(normalized_as_of, "as_of")
    for item in queue_items:
        if not isinstance(item, Mapping):
            raise EditorialAuditError("queue_items must contain objects")
        queue_id = item.get("id")
        if not isinstance(queue_id, str) or not queue_id:
            raise EditorialAuditError("queue item requires id")
        if queue_id in seen_queue_ids:
            raise EditorialAuditError(f"duplicate editorial queue item: {queue_id}")
        seen_queue_ids.add(queue_id)
        state = item.get("state")
        lane = item.get("lane")
        item_priority = item.get("priority")
        if state not in {"queued", "claimed", "completed", "dismissed"}:
            raise EditorialAuditError(f"queue item {queue_id} has invalid state")
        if lane not in {"candidate_extraction", "discovery_review", "restricted_human"}:
            raise EditorialAuditError(f"queue item {queue_id} has invalid lane")
        if item_priority not in {"normal", "high"}:
            raise EditorialAuditError(f"queue item {queue_id} has invalid priority")
        if item.get("canonical_mutation_authority") is not False:
            raise EditorialAuditError("editorial queue item cannot have canonical mutation authority")
        created_at = _parse_utc(item.get("created_at"), f"queue item {queue_id} created_at")
        if created_at > as_of_dt:
            raise EditorialAuditError(f"queue item {queue_id} is newer than audit as_of")
        if state in {"completed", "dismissed"}:
            continue

        source_ids = _string_list(item.get("source_ids"), f"queue item {queue_id} source_ids")
        document_ids = _string_list(item.get("document_ids"), f"queue item {queue_id} document_ids")
        priority = "high" if item_priority == "high" or lane == "restricted_human" else "normal"
        findings.append(
            _finding(
                kind="queue_action_required",
                priority=priority,
                subject_id=queue_id,
                reason_codes=[f"lane:{lane}", f"state:{state}", f"queue_priority:{item_priority}"],
                context={
                    "queue_item_id": queue_id,
                    "lane": lane,
                    "state": state,
                    "priority": item_priority,
                    "source_ids": sorted(source_ids),
                    "document_ids": sorted(document_ids),
                    "created_at": _utc(item.get("created_at"), f"queue item {queue_id} created_at"),
                },
            )
        )

    findings.sort(
        key=lambda item: (
            0 if item["priority"] == "high" else 1,
            item["kind"],
            item["subject_id"],
            item["id"],
        )
    )
    input_payload = {
        "as_of": normalized_as_of,
        "staleness_report": staleness_report,
        "source_freshness_report": source_freshness_report,
        "queue_items": sorted((dict(item) for item in queue_items), key=lambda item: str(item.get("id"))),
    }
    report: dict[str, Any] = {
        "as_of": normalized_as_of,
        "input_sha256": _sha256(input_payload),
        "summary": _summary(findings),
        "findings": findings,
        "authority": {
            "mode": "operational_audit_only",
            "truth_authority": False,
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }
    report["id"] = _stable_id("SDA-EDITORIAL-AUDIT", report)
    return report


def _validate_audit_report_integrity(audit_report: Mapping[str, Any]) -> tuple[str, list[Mapping[str, Any]]]:
    report_id = audit_report.get("id")
    if not isinstance(report_id, str) or not report_id:
        raise EditorialAuditError("audit report requires id")
    if audit_report.get("authority") != {
        "mode": "operational_audit_only",
        "truth_authority": False,
        "approval_authority": False,
        "canonical_mutation_authority": False,
        "publication_authority": False,
    }:
        raise EditorialAuditError("audit report authority boundary is invalid")

    findings_raw = audit_report.get("findings")
    summary = audit_report.get("summary")
    if not isinstance(findings_raw, Sequence) or isinstance(findings_raw, (str, bytes)):
        raise EditorialAuditError("audit report findings must be an array")
    if not isinstance(summary, Mapping):
        raise EditorialAuditError("audit report summary must be an object")

    findings: list[Mapping[str, Any]] = []
    seen_ids: set[str] = set()
    for finding in findings_raw:
        if not isinstance(finding, Mapping):
            raise EditorialAuditError("audit findings must contain objects")
        finding_id = finding.get("id")
        if not isinstance(finding_id, str) or not finding_id or finding_id in seen_ids:
            raise EditorialAuditError("audit findings require unique IDs")
        seen_ids.add(finding_id)
        body = {key: value for key, value in finding.items() if key != "id"}
        if finding_id != _stable_id("SDA-AUDIT-FINDING", body):
            raise EditorialAuditError("audit finding content does not match its ID")
        findings.append(finding)

    expected_summary = _summary(findings)
    if dict(summary) != expected_summary:
        raise EditorialAuditError("audit report summary does not match findings")

    report_body = {key: value for key, value in audit_report.items() if key != "id"}
    if report_id != _stable_id("SDA-EDITORIAL-AUDIT", report_body):
        raise EditorialAuditError("audit report content does not match its ID")
    return report_id, findings


def build_daily_editorial_brief(*, audit_report: Mapping[str, Any]) -> dict[str, Any]:
    """Project one integrity-checked audit report into editor-facing sections."""

    report_id, findings = _validate_audit_report_integrity(audit_report)
    refs = [
        {
            "finding_id": str(finding["id"]),
            "kind": finding.get("kind"),
            "priority": finding.get("priority"),
            "subject_id": finding.get("subject_id"),
            "reason_codes": list(finding.get("reason_codes", [])),
        }
        for finding in findings
    ]
    refs.sort(
        key=lambda item: (
            0 if item["priority"] == "high" else 1,
            str(item["kind"]),
            str(item["subject_id"]),
            item["finding_id"],
        )
    )
    brief: dict[str, Any] = {
        "as_of": _utc(audit_report.get("as_of"), "audit report as_of"),
        "audit_report_id": report_id,
        "audit_report_sha256": _sha256(audit_report),
        "summary": {
            "total_actions": len(refs),
            "high_priority_actions": sum(item["priority"] == "high" for item in refs),
        },
        "sections": {
            "high_priority": [item for item in refs if item["priority"] == "high"],
            "claim_review": [item for item in refs if item["kind"] == "claim_review_required"],
            "source_monitoring": [item for item in refs if item["kind"] == "source_monitoring_required"],
            "editorial_queue": [item for item in refs if item["kind"] == "queue_action_required"],
        },
        "authority": {
            "mode": "editorial_brief_only",
            "truth_authority": False,
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }
    brief["id"] = _stable_id("SDA-EDITORIAL-BRIEF", brief)
    return brief


__all__ = [
    "EditorialAuditError",
    "build_editorial_audit_report",
    "build_daily_editorial_brief",
]
