"""Deterministic M4 source-monitoring and editorial-queue routing.

This module is deliberately model-free. It converts successful M1 ingestion results
into operational observations, applies caller-owned deterministic lexical routing
rules, and creates/merges editorial queue items. Neither observations nor queue
items have canonical mutation authority.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from services.ingestion.acquisition import IngestionResult


class EditorialRoutingError(ValueError):
    """Raised when monitoring or queue routing input violates the M4 contract."""


@dataclass(frozen=True)
class RoutingPolicy:
    relevance_terms: tuple[str, ...]
    restricted_terms: tuple[str, ...] = ()
    high_priority_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class QueueRoutingResult:
    action: str  # ignored | created | merged
    item: Mapping[str, Any] | None


def _utc(value: str, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise EditorialRoutingError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EditorialRoutingError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise EditorialRoutingError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}{digest}"


def _validate_terms(terms: Sequence[str], label: str) -> tuple[str, ...]:
    rendered: list[str] = []
    seen: set[str] = set()
    for term in terms:
        if not isinstance(term, str) or not term.strip():
            raise EditorialRoutingError(f"{label} must contain non-empty strings")
        normalized = " ".join(term.casefold().split())
        if normalized in seen:
            raise EditorialRoutingError(f"{label} contains duplicate term: {term!r}")
        seen.add(normalized)
        rendered.append(normalized)
    return tuple(rendered)


def validate_policy(policy: RoutingPolicy) -> RoutingPolicy:
    relevance = _validate_terms(policy.relevance_terms, "relevance_terms")
    if not relevance:
        raise EditorialRoutingError("relevance_terms must not be empty")
    restricted = _validate_terms(policy.restricted_terms, "restricted_terms")
    priority = _validate_terms(policy.high_priority_terms, "high_priority_terms")
    return RoutingPolicy(relevance, restricted, priority)


def _matched_terms(text: str, terms: Sequence[str]) -> list[str]:
    normalized_text = " ".join(text.casefold().split())
    matched: list[str] = []
    for term in terms:
        pattern = rf"(?<!\w){re.escape(term)}(?!\w)"
        if re.search(pattern, normalized_text, flags=re.UNICODE):
            matched.append(term)
    return sorted(matched)


def build_monitoring_observation(
    *,
    ingestion: IngestionResult,
    source: Mapping[str, Any],
    canonical_text: str,
    policy: RoutingPolicy,
) -> dict[str, Any]:
    """Create a deterministic operational observation from one successful fetch."""

    checked = validate_policy(policy)
    if ingestion.status not in {"new", "changed", "unchanged"}:
        raise EditorialRoutingError(f"unsupported ingestion status: {ingestion.status!r}")
    if not isinstance(canonical_text, str):
        raise EditorialRoutingError("canonical_text must be text")

    receipt = ingestion.receipt
    source_id = source.get("id")
    source_class = source.get("source_class")
    if not isinstance(source_id, str) or not source_id:
        raise EditorialRoutingError("Source requires canonical id")
    if source_id != receipt.source_id:
        raise EditorialRoutingError("Source id does not match RetrievalReceipt source_id")
    if source_class not in {"A", "B", "C", "D", "E"}:
        raise EditorialRoutingError("Source requires valid source_class")
    if source.get("active") is False:
        raise EditorialRoutingError("inactive Source cannot produce monitoring observation")
    if receipt.status_code != 200:
        raise EditorialRoutingError("monitoring observation requires successful HTTP receipt")
    if not isinstance(receipt.document_key, str) or not receipt.document_key:
        raise EditorialRoutingError("RetrievalReceipt requires registered document_key")

    document = ingestion.document
    document_id = document.get("id")
    canonical_sha = document.get("content_sha256")
    if not isinstance(document_id, str) or not document_id:
        raise EditorialRoutingError("IngestionResult Document requires canonical id")
    if document.get("source_id") != source_id:
        raise EditorialRoutingError("Document source_id does not match Source/Receipt")
    if not isinstance(canonical_sha, str) or not re.fullmatch(r"[A-Fa-f0-9]{64}", canonical_sha):
        raise EditorialRoutingError("IngestionResult Document requires canonical content SHA-256")

    observed_at = _utc(receipt.observed_at, "RetrievalReceipt.observed_at")
    raw_sha = receipt.raw_content_sha256
    if not re.fullmatch(r"[A-Fa-f0-9]{64}", raw_sha):
        raise EditorialRoutingError("RetrievalReceipt raw_content_sha256 is invalid")

    relevant_terms = _matched_terms(canonical_text, checked.relevance_terms)
    restricted_terms = _matched_terms(canonical_text, checked.restricted_terms)
    priority_terms = _matched_terms(canonical_text, checked.high_priority_terms)

    relevant = bool(relevant_terms)
    sensitivity_lane = "RED" if restricted_terms else ("AMBER" if relevant else "GREEN")
    observation_id = _stable_id(
        "SDA-MON-",
        source_id,
        receipt.document_key,
        observed_at,
        raw_sha.lower(),
    )

    relevance_rule_ids = [f"term:{term}" for term in relevant_terms]
    relevance_rule_ids.extend(f"priority:{term}" for term in priority_terms)

    return {
        "id": observation_id,
        "source_id": source_id,
        "source_class": source_class,
        "document_key": receipt.document_key,
        "observed_at": observed_at,
        "ingestion_status": ingestion.status,
        "raw_content_sha256": raw_sha.lower(),
        "canonical_content_sha256": canonical_sha.lower(),
        "document_id": document_id,
        "relevance": {
            "classification": "relevant" if relevant else "irrelevant",
            "rule_ids": sorted(set(relevance_rule_ids)),
        },
        "sensitivity": {
            "lane": sensitivity_lane,
            "rule_ids": [f"restricted:{term}" for term in restricted_terms],
        },
        "dedupe_key": f"sha256:{canonical_sha.lower()}",
    }


def _desired_lane(observation: Mapping[str, Any]) -> str | None:
    if observation.get("ingestion_status") == "unchanged":
        return None
    relevance = observation.get("relevance")
    if not isinstance(relevance, Mapping) or relevance.get("classification") != "relevant":
        return None
    sensitivity = observation.get("sensitivity")
    if not isinstance(sensitivity, Mapping):
        raise EditorialRoutingError("observation sensitivity is malformed")
    if sensitivity.get("lane") == "RED":
        return "restricted_human"
    return "discovery_review" if observation.get("source_class") == "E" else "candidate_extraction"


def _lane_rank(lane: str) -> int:
    return {
        "discovery_review": 1,
        "candidate_extraction": 2,
        "restricted_human": 3,
    }[lane]


def _reason_codes(observation: Mapping[str, Any], lane: str) -> list[str]:
    reasons = {f"source_class:{observation['source_class']}", f"lane:{lane}"}
    relevance = observation.get("relevance")
    sensitivity = observation.get("sensitivity")
    if isinstance(relevance, Mapping):
        reasons.update(str(item) for item in relevance.get("rule_ids", []) if isinstance(item, str))
    if isinstance(sensitivity, Mapping):
        reasons.update(str(item) for item in sensitivity.get("rule_ids", []) if isinstance(item, str))
    return sorted(reasons)


def _priority(observation: Mapping[str, Any], lane: str) -> str:
    if lane == "restricted_human":
        return "high"
    relevance = observation.get("relevance")
    rules = relevance.get("rule_ids", []) if isinstance(relevance, Mapping) else []
    if any(isinstance(item, str) and item.startswith("priority:") for item in rules):
        return "high"
    return "high" if observation.get("source_class") in {"A", "B"} else "normal"


def _string_array(value: Any, label: str) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise EditorialRoutingError(f"{label} must be an array")
    rendered: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item:
            raise EditorialRoutingError(f"{label} contains invalid value")
        rendered.append(item)
    if len(rendered) != len(set(rendered)):
        raise EditorialRoutingError(f"{label} contains duplicates")
    return rendered


def route_observation(
    observation: Mapping[str, Any],
    *,
    created_at: str,
    existing_item: Mapping[str, Any] | None = None,
) -> QueueRoutingResult:
    """Route or exact-dedupe one monitoring observation into the editorial queue."""

    lane = _desired_lane(observation)
    if lane is None:
        return QueueRoutingResult("ignored", None)

    dedupe_key = observation.get("dedupe_key")
    observation_id = observation.get("id")
    source_id = observation.get("source_id")
    document_id = observation.get("document_id")
    if not isinstance(dedupe_key, str) or not re.fullmatch(r"sha256:[A-Fa-f0-9]{64}", dedupe_key):
        raise EditorialRoutingError("observation requires valid dedupe_key")
    if not all(isinstance(item, str) and item for item in (observation_id, source_id, document_id)):
        raise EditorialRoutingError("observation identity is incomplete")
    created = _utc(created_at, "created_at")

    if existing_item is None:
        item = {
            "id": _stable_id("SDA-QUEUE-", dedupe_key),
            "observation_ids": [observation_id],
            "source_ids": [source_id],
            "document_ids": [document_id],
            "dedupe_key": dedupe_key,
            "lane": lane,
            "state": "queued",
            "priority": _priority(observation, lane),
            "reason_codes": _reason_codes(observation, lane),
            "ai_extraction_allowed": lane == "candidate_extraction",
            "canonical_mutation_authority": False,
            "created_at": created,
        }
        return QueueRoutingResult("created", item)

    if existing_item.get("dedupe_key") != dedupe_key:
        raise EditorialRoutingError("existing queue item dedupe_key does not match observation")
    state = existing_item.get("state")
    if state not in {"queued", "claimed"}:
        raise EditorialRoutingError("completed/dismissed queue item cannot absorb new observation")
    existing_lane = existing_item.get("lane")
    if existing_lane not in {"candidate_extraction", "discovery_review", "restricted_human"}:
        raise EditorialRoutingError("existing queue item lane is invalid")
    if existing_item.get("canonical_mutation_authority") is not False:
        raise EditorialRoutingError("editorial queue item must not have canonical mutation authority")
    if existing_item.get("ai_extraction_allowed") is not (existing_lane == "candidate_extraction"):
        raise EditorialRoutingError("existing queue item extraction authority is inconsistent with lane")

    existing_observations = _string_array(existing_item.get("observation_ids"), "observation_ids")
    existing_sources = _string_array(existing_item.get("source_ids"), "source_ids")
    existing_documents = _string_array(existing_item.get("document_ids"), "document_ids")
    existing_reasons = _string_array(existing_item.get("reason_codes"), "reason_codes")

    merged_lane = lane if _lane_rank(lane) > _lane_rank(existing_lane) else existing_lane
    if state == "claimed" and merged_lane != existing_lane:
        raise EditorialRoutingError(
            "claimed queue item cannot change routing lane; coordination/cancellation is required"
        )

    observations = sorted(set([*existing_observations, observation_id]))
    sources = sorted(set([*existing_sources, source_id]))
    documents = sorted(set([*existing_documents, document_id]))
    reasons = {item for item in existing_reasons if not item.startswith("lane:")}
    reasons.update(item for item in _reason_codes(observation, lane) if not item.startswith("lane:"))
    reasons.add(f"lane:{merged_lane}")

    item = dict(existing_item)
    item.update(
        {
            "observation_ids": observations,
            "source_ids": sources,
            "document_ids": documents,
            "lane": merged_lane,
            "priority": "high"
            if existing_item.get("priority") == "high" or _priority(observation, lane) == "high"
            else "normal",
            "reason_codes": sorted(reasons),
            "ai_extraction_allowed": merged_lane == "candidate_extraction",
            "canonical_mutation_authority": False,
        }
    )
    return QueueRoutingResult("merged", item)
