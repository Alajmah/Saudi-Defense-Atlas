"""Pure normalization helpers for public read-projection integrity hashes."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def _aliases(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return []
    aliases: list[dict[str, str]] = []
    for alias in value:
        if not isinstance(alias, Mapping):
            continue
        language = alias.get("language")
        text = alias.get("value")
        if language in {"ar", "en"} and isinstance(text, str) and text:
            aliases.append({"value": text, "language": str(language)})
    return sorted(aliases, key=lambda item: (item["language"], item["value"]))


def entity_read_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact Entity subset reconstructed by the public read adapter."""
    projected: dict[str, Any] = {
        "id": record["id"],
        "entity_type": record["entity_type"],
        "subtype": record.get("subtype"),
        "names": dict(record["names"]),
        "record_status": record["record_status"],
    }
    aliases = _aliases(record.get("aliases"))
    if aliases:
        projected["aliases"] = aliases
    descriptions = record.get("descriptions")
    if isinstance(descriptions, Mapping) and descriptions:
        projected["descriptions"] = dict(descriptions)
    if record.get("created_at"):
        projected["created_at"] = record["created_at"]
    if record.get("updated_at"):
        projected["updated_at"] = record["updated_at"]
    return projected


def event_read_projection(record: Mapping[str, Any]) -> dict[str, Any]:
    """Return the exact Event subset reconstructed by the public read adapter."""
    participants = [
        {"entity_id": str(item["entity_id"]), "role": str(item["role"])}
        for item in record.get("participants", [])
        if isinstance(item, Mapping)
    ]
    participants.sort(key=lambda item: (item["role"], item["entity_id"]))

    evidence_links = [
        {"evidence_id": str(item["evidence_id"]), "role": str(item["role"])}
        for item in record.get("evidence_links", [])
        if isinstance(item, Mapping)
    ]
    evidence_links.sort(key=lambda item: (item["evidence_id"], item["role"]))

    return {
        "id": record["id"],
        "event_type": record["event_type"],
        "names": dict(record.get("names") or {}),
        "occurred_at": dict(record["occurred_at"]),
        "participants": participants,
        "related_entity_ids": sorted(str(value) for value in record.get("related_entity_ids", [])),
        "related_claim_ids": sorted(str(value) for value in record.get("related_claim_ids", [])),
        "confidence": record["confidence"],
        "evidence_links": evidence_links,
        "created_at": record["created_at"],
    }
