"""Deterministic M4 editorial audit and daily-brief projections.

The auditor consumes already-accepted operational signals: Claim staleness,
registered-feed acquisition freshness, and a contemporaneously captured
EditorialQueueItem snapshot. It does not re-evaluate factual truth, approve
proposals, mutate canonical knowledge, or publish.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class EditorialAuditError(ValueError):
    """Raised when operational audit inputs are inconsistent or incomplete."""


_FINDING_KINDS = {
    "claim_review_required",
    "source_monitoring_required",
    "queue_action_required",
}
_PRIORITIES = {"high", "normal"}
_AUTHORITY_KEYS = {
    "mode",
    "truth_authority",
    "approval_authority",
    "canonical_mutation_authority",
    "publication_authority",
}
_AUDIT_AUTHORITY = {
    "mode": "operational_audit_only",
    "truth_authority": False,
    "approval_authority": False,
    "canonical_mutation_authority": False,
    "publication_authority": False,
}
_BRIEF_AUTHORITY = {
    "mode": "editorial_brief_only",
    "truth_authority": False,
    "approval_authority": False,
    "canonical_mutation_authority": False,
    "publication_authority": False,
}
_AUDIT_REPORT_KEYS = {"id", "as_of", "input_sha256", "summary", "findings", "authority"}
_FINDING_KEYS = {"id", "kind", "priority", "subject_id", "reason_codes", "context"}
_CLAIM_CONTEXT_KEYS = {
    "claim_id",
    "subject_id",
    "predicate_id",
    "claim_state",
    "confidence",
    "staleness_status",
    "verified_at",
    "review_due_at",
}
_SOURCE_CONTEXT_KEYS = {
    "source_id",
    "feed_key",
    "source_class",
    "freshness_status",
    "latest_observed_at",
    "next_check_due_at",
}
_QUEUE_CONTEXT_KEYS = {
    "queue_item_id",
    "lane",
    "state",
    "priority",
    "source_ids",
    "document_ids",
    "created_at",
}
_SHA256_RE = re.compile(r"^[A-Fa-f0-9]{64}$")


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_sha256(value)[:24].upper()}"


def _canonical_id(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 128:
        raise EditorialAuditError(f"{label} must be a non-empty canonical ID <= 128 characters")
    return value


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


def _optional_utc(value: Any, label: str) -> datetime | None:
    if value is None:
        return None
    return _parse_utc(value, label)


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


def _validate_authority(value: Any, *, mode: str, label: str) -> None:
    if not isinstance(value, Mapping) or set(value) != _AUTHORITY_KEYS:
        raise EditorialAuditError(f"{label} authority fields do not match the contract")
    if value.get("mode") != mode:
        raise EditorialAuditError(f"{label} authority mode is invalid")
    for key in (
        "truth_authority",
        "approval_authority",
        "canonical_mutation_authority",
        "publication_authority",
    ):
        if value.get(key) is not False:
            raise EditorialAuditError(f"{label} {key} must be false")


def _validate_finding_context(
    *,
    kind: str,
    subject_id: str,
    priority: str,
    reasons: Sequence[str],
    context: Mapping[str, Any],
    as_of_dt: datetime,
) -> None:
    """Validate the actionable semantics retained in one audit finding."""

    if kind == "claim_review_required":
        if set(context) != _CLAIM_CONTEXT_KEYS:
            raise EditorialAuditError("claim-review context fields do not match the contract")
        claim_id = _canonical_id(context.get("claim_id"), "claim-review context claim_id")
        if claim_id != subject_id:
            raise EditorialAuditError("claim-review context does not match finding subject")
        _canonical_id(context.get("subject_id"), "claim-review context subject_id")
        predicate_id = context.get("predicate_id")
        if not isinstance(predicate_id, str) or not predicate_id:
            raise EditorialAuditError("claim-review context predicate_id is invalid")
        state = context.get("claim_state")
        confidence = context.get("confidence")
        status = context.get("staleness_status")
        if state not in {"active", "disputed"}:
            raise EditorialAuditError("claim-review context claim_state is invalid")
        if confidence not in {"verified", "high", "medium", "low", "unverified"}:
            raise EditorialAuditError("claim-review context confidence is invalid")
        if status not in {"fresh", "due", "unverified"}:
            raise EditorialAuditError("claim-review context staleness_status is invalid")
        verified_at = _optional_utc(context.get("verified_at"), "claim-review context verified_at")
        review_due_at = _optional_utc(
            context.get("review_due_at"), "claim-review context review_due_at"
        )
        if verified_at is not None and verified_at > as_of_dt:
            raise EditorialAuditError("claim-review verified_at is newer than audit as_of")
        if status == "unverified":
            if verified_at is not None or review_due_at is not None:
                raise EditorialAuditError("unverified claim-review context has verification dates")
        elif verified_at is None or review_due_at is None:
            raise EditorialAuditError("verified claim-review context requires verification dates")

        expected_reasons: list[str] = []
        if status == "due":
            expected_reasons.append("review:due")
        elif status == "unverified":
            expected_reasons.append("review:never_verified")
        if state == "disputed":
            expected_reasons.append("claim_state:disputed")
        if confidence == "unverified":
            expected_reasons.append("confidence:unverified")
        if sorted(reasons) != sorted(expected_reasons) or not expected_reasons:
            raise EditorialAuditError("claim-review reasons do not match context")
        expected_priority = (
            "high"
            if state == "disputed" or status == "unverified" or confidence == "unverified"
            else "normal"
        )
        if priority != expected_priority:
            raise EditorialAuditError("claim-review priority does not match context")
        return

    if kind == "source_monitoring_required":
        if set(context) != _SOURCE_CONTEXT_KEYS:
            raise EditorialAuditError("source-monitoring context fields do not match the contract")
        source_id = _canonical_id(context.get("source_id"), "source-monitoring context source_id")
        if source_id != subject_id:
            raise EditorialAuditError("source-monitoring context does not match finding subject")
        feed_key = context.get("feed_key")
        source_class = context.get("source_class")
        status = context.get("freshness_status")
        if not isinstance(feed_key, str) or not feed_key:
            raise EditorialAuditError("source-monitoring context feed_key is invalid")
        if source_class not in {"A", "B", "C", "D", "E"}:
            raise EditorialAuditError("source-monitoring context source_class is invalid")
        if status not in {"due", "never_retrieved"}:
            raise EditorialAuditError("source-monitoring context freshness_status is invalid")
        latest = _optional_utc(
            context.get("latest_observed_at"), "source-monitoring context latest_observed_at"
        )
        next_due = _optional_utc(
            context.get("next_check_due_at"), "source-monitoring context next_check_due_at"
        )
        if latest is not None and latest > as_of_dt:
            raise EditorialAuditError("source-monitoring latest observation is newer than audit as_of")
        if status == "never_retrieved":
            if latest is not None or next_due is not None:
                raise EditorialAuditError("never-retrieved source context has acquisition dates")
        elif latest is None or next_due is None or next_due > as_of_dt:
            raise EditorialAuditError("due source-monitoring context requires due acquisition dates")

        acquisition_reason = (
            "acquisition:never_retrieved" if status == "never_retrieved" else "acquisition:poll_due"
        )
        expected_reasons = sorted([acquisition_reason, f"source_class:{source_class}"])
        if sorted(reasons) != expected_reasons:
            raise EditorialAuditError("source-monitoring reasons do not match context")
        expected_priority = (
            "high" if status == "never_retrieved" and source_class in {"A", "B"} else "normal"
        )
        if priority != expected_priority:
            raise EditorialAuditError("source-monitoring priority does not match context")
        return

    if kind == "queue_action_required":
        if set(context) != _QUEUE_CONTEXT_KEYS:
            raise EditorialAuditError("queue-action context fields do not match the contract")
        queue_id = _canonical_id(context.get("queue_item_id"), "queue-action context queue_item_id")
        if queue_id != subject_id:
            raise EditorialAuditError("queue-action context does not match finding subject")
        lane = context.get("lane")
        state = context.get("state")
        item_priority = context.get("priority")
        if lane not in {"candidate_extraction", "discovery_review", "restricted_human"}:
            raise EditorialAuditError("queue-action context lane is invalid")
        if state not in {"queued", "claimed"}:
            raise EditorialAuditError("queue-action context state is invalid")
        if item_priority not in _PRIORITIES:
            raise EditorialAuditError("queue-action context priority is invalid")
        source_ids = _string_list(context.get("source_ids"), "queue-action context source_ids")
        document_ids = _string_list(
            context.get("document_ids"), "queue-action context document_ids"
        )
        if not source_ids or not document_ids:
            raise EditorialAuditError("queue-action context requires source/document provenance")
        for source_id in source_ids:
            _canonical_id(source_id, "queue-action context source_id")
        for document_id in document_ids:
            _canonical_id(document_id, "queue-action context document_id")
        created_at = _parse_utc(context.get("created_at"), "queue-action context created_at")
        if created_at > as_of_dt:
            raise EditorialAuditError("queue-action created_at is newer than audit as_of")

        expected_reasons = sorted(
            [f"lane:{lane}", f"state:{state}", f"queue_priority:{item_priority}"]
        )
        if sorted(reasons) != expected_reasons:
            raise EditorialAuditError("queue-action reasons do not match context")
        expected_priority = (
            "high" if item_priority == "high" or lane == "restricted_human" else "normal"
        )
        if priority != expected_priority:
            raise EditorialAuditError("queue-action priority does not match context")
        return

    raise EditorialAuditError("finding kind is invalid")


def _finding(
    *,
    kind: str,
    priority: str,
    subject_id: str,
    reason_codes: Sequence[str],
    context: Mapping[str, Any],
) -> dict[str, Any]:
    if kind not in _FINDING_KINDS:
        raise EditorialAuditError("finding kind is invalid")
    if priority not in _PRIORITIES:
        raise EditorialAuditError("finding priority is invalid")
    _canonical_id(subject_id, "finding subject_id")
    reasons = sorted({str(reason) for reason in reason_codes if isinstance(reason, str) and reason})
    if not reasons or any(len(reason) > 128 for reason in reasons):
        raise EditorialAuditError("finding requires reason codes <= 128 characters")
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
    queue_snapshot_as_of: str,
    as_of: str,
) -> dict[str, Any]:
    """Build one deterministic operational attention report.

    `queue_snapshot_as_of` is the capture time of the supplied current queue
    snapshot. This contract does not reconstruct historical queue state from
    later mutable records.
    """

    if not isinstance(staleness_report, Mapping):
        raise EditorialAuditError("staleness_report must be an object")
    if not isinstance(source_freshness_report, Mapping):
        raise EditorialAuditError("source_freshness_report must be an object")
    if not isinstance(queue_items, Sequence) or isinstance(queue_items, (str, bytes)):
        raise EditorialAuditError("queue_items must be an array")

    normalized_as_of = _utc(as_of, "as_of")
    for report, label in (
        (staleness_report, "staleness_report"),
        (source_freshness_report, "source_freshness_report"),
    ):
        if _utc(report.get("as_of"), f"{label}.as_of") != normalized_as_of:
            raise EditorialAuditError(f"{label} is not aligned to audit as_of")

    normalized_queue_snapshot_as_of = _utc(queue_snapshot_as_of, "queue_snapshot_as_of")
    if normalized_queue_snapshot_as_of != normalized_as_of:
        raise EditorialAuditError("queue snapshot is not aligned to audit as_of")

    findings: list[dict[str, Any]] = []
    seen_claim_ids: set[str] = set()
    for item in _items(staleness_report, "staleness_report"):
        claim_id = _canonical_id(item.get("claim_id"), "staleness claim_id")
        if claim_id in seen_claim_ids:
            raise EditorialAuditError(f"duplicate Claim staleness item: {claim_id}")
        seen_claim_ids.add(claim_id)
        status = item.get("status")
        state = item.get("claim_state")
        confidence = item.get("confidence")
        subject_id = _canonical_id(item.get("subject_id"), f"Claim {claim_id} subject_id")
        predicate_id = item.get("predicate_id")
        if status not in {"fresh", "due", "unverified"}:
            raise EditorialAuditError(f"Claim {claim_id} has invalid staleness status")
        if state not in {"active", "disputed"}:
            raise EditorialAuditError(f"Claim {claim_id} has invalid visible state")
        if confidence not in {"verified", "high", "medium", "low", "unverified"}:
            raise EditorialAuditError(f"Claim {claim_id} has invalid confidence")
        if not isinstance(predicate_id, str) or not predicate_id:
            raise EditorialAuditError(f"Claim {claim_id} has invalid predicate_id")

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
                    "subject_id": subject_id,
                    "predicate_id": predicate_id,
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
        source_id = _canonical_id(item.get("source_id"), "source freshness source_id")
        feed_key = item.get("feed_key")
        status = item.get("status")
        source_class = item.get("source_class")
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
        queue_id = _canonical_id(item.get("id"), "queue item id")
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
        if item_priority not in _PRIORITIES:
            raise EditorialAuditError(f"queue item {queue_id} has invalid priority")
        if item.get("ai_extraction_allowed") is not (lane == "candidate_extraction"):
            raise EditorialAuditError(
                f"queue item {queue_id} extraction authority is inconsistent with lane"
            )
        if item.get("canonical_mutation_authority") is not False:
            raise EditorialAuditError("editorial queue item cannot have canonical mutation authority")
        created_at = _parse_utc(item.get("created_at"), f"queue item {queue_id} created_at")
        if created_at > as_of_dt:
            raise EditorialAuditError(f"queue item {queue_id} is newer than audit as_of")
        if state in {"completed", "dismissed"}:
            continue

        source_ids = _string_list(item.get("source_ids"), f"queue item {queue_id} source_ids")
        document_ids = _string_list(item.get("document_ids"), f"queue item {queue_id} document_ids")
        if not source_ids or not document_ids:
            raise EditorialAuditError(f"queue item {queue_id} requires source/document provenance")
        for source_id in source_ids:
            _canonical_id(source_id, f"queue item {queue_id} source_id")
        for document_id in document_ids:
            _canonical_id(document_id, f"queue item {queue_id} document_id")
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
        "queue_snapshot": {
            "as_of": normalized_queue_snapshot_as_of,
            "items": sorted((dict(item) for item in queue_items), key=lambda item: str(item.get("id"))),
        },
    }
    report: dict[str, Any] = {
        "as_of": normalized_as_of,
        "input_sha256": _sha256(input_payload),
        "summary": _summary(findings),
        "findings": findings,
        "authority": dict(_AUDIT_AUTHORITY),
    }
    report["id"] = _stable_id("SDA-EDITORIAL-AUDIT", report)
    return report


def _validate_audit_report_integrity(audit_report: Mapping[str, Any]) -> tuple[str, list[Mapping[str, Any]]]:
    if not isinstance(audit_report, Mapping) or set(audit_report) != _AUDIT_REPORT_KEYS:
        raise EditorialAuditError("audit report fields do not match the contract")

    report_id = _canonical_id(audit_report.get("id"), "audit report id")
    as_of_dt = _parse_utc(audit_report.get("as_of"), "audit report as_of")
    input_sha256 = audit_report.get("input_sha256")
    if not isinstance(input_sha256, str) or not _SHA256_RE.fullmatch(input_sha256):
        raise EditorialAuditError("audit report input_sha256 is invalid")
    _validate_authority(
        audit_report.get("authority"), mode="operational_audit_only", label="audit report"
    )

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
        if set(finding) != _FINDING_KEYS:
            raise EditorialAuditError("audit finding fields do not match the contract")
        finding_id = _canonical_id(finding.get("id"), "audit finding id")
        if finding_id in seen_ids:
            raise EditorialAuditError("audit findings require unique IDs")
        seen_ids.add(finding_id)
        kind = finding.get("kind")
        priority = finding.get("priority")
        if kind not in _FINDING_KINDS:
            raise EditorialAuditError("audit finding kind is invalid")
        if priority not in _PRIORITIES:
            raise EditorialAuditError("audit finding priority is invalid")
        subject_id = _canonical_id(finding.get("subject_id"), "audit finding subject_id")
        reasons = _string_list(finding.get("reason_codes"), "audit finding reason_codes")
        if not reasons or any(len(reason) > 128 for reason in reasons):
            raise EditorialAuditError("audit finding requires reason_codes <= 128 characters")
        context = finding.get("context")
        if not isinstance(context, Mapping):
            raise EditorialAuditError("audit finding context must be an object")
        _validate_finding_context(
            kind=str(kind),
            subject_id=subject_id,
            priority=str(priority),
            reasons=reasons,
            context=context,
            as_of_dt=as_of_dt,
        )
        body = {key: value for key, value in finding.items() if key != "id"}
        if finding_id != _stable_id("SDA-AUDIT-FINDING", body):
            raise EditorialAuditError("audit finding content does not match its ID")
        findings.append(finding)

    expected_summary = _summary(findings)
    if set(summary) != set(expected_summary):
        raise EditorialAuditError("audit report summary fields do not match findings")
    if any(isinstance(value, bool) or not isinstance(value, int) or value < 0 for value in summary.values()):
        raise EditorialAuditError("audit report summary values must be non-negative integers")
    if dict(summary) != expected_summary:
        raise EditorialAuditError("audit report summary does not match findings")

    report_body = {key: value for key, value in audit_report.items() if key != "id"}
    if report_id != _stable_id("SDA-EDITORIAL-AUDIT", report_body):
        raise EditorialAuditError("audit report content does not match its ID")
    return report_id, findings


def build_daily_editorial_brief(*, audit_report: Mapping[str, Any]) -> dict[str, Any]:
    """Project one semantically and content-integrity checked audit report."""

    report_id, findings = _validate_audit_report_integrity(audit_report)
    refs = [
        {
            "finding_id": str(finding["id"]),
            "kind": finding["kind"],
            "priority": finding["priority"],
            "subject_id": finding["subject_id"],
            "reason_codes": list(finding["reason_codes"]),
            "context": dict(finding["context"]),
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
        "authority": dict(_BRIEF_AUTHORITY),
    }
    brief["id"] = _stable_id("SDA-EDITORIAL-BRIEF", brief)
    return brief


__all__ = [
    "EditorialAuditError",
    "build_editorial_audit_report",
    "build_daily_editorial_brief",
]
