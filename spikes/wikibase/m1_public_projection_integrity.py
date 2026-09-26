"""Integrity helpers for the bounded M1 public read projection.

Canonical payload hashes and public-read projection hashes answer different
questions. The former identify the admitted SDA payload; the latter identify the
exact subset reconstructed by the public read adapter. This module keeps those
contracts separate and independently verifiable.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from services.governance.mutation_guard import EffectInspection
from services.governance.proposal_auth import canonical_sha256

from m1_public_projection_backend import (
    READ_PROJECTION_VERSION,
    WikibaseM1PublicProjectionBackend,
)
from m1_read_adapter import ReadProjectionError, WikibaseM1ReadAdapter


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
    """Return the exact Entity subset the public read adapter reconstructs."""
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
    """Return the exact Event subset the public read adapter reconstructs."""
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


class WikibaseM1IntegrityBackend(WikibaseM1PublicProjectionBackend):
    """Add explicit read-projection hashes to governed Entity/Event metadata."""

    def _entity_inspection(self, mutation: Mapping[str, Any]) -> EffectInspection:
        payload = mutation["payload"]
        canonical_id = str(payload["id"])
        matches = self._domain_item_matches(canonical_id)
        if len(matches) != 1:
            return EffectInspection(
                "unknown" if not matches else "conflict",
                detail=f"entity metadata target {canonical_id!r} resolved to {len(matches)} items",
            )
        qid = matches[0]
        entity = self.api.get_entity(qid)
        read_versions = self._main_values(entity, "read_projection_version")
        record_types = self._main_values(entity, "record_type")
        read_hashes = self._main_values(entity, "read_projection_sha256")

        if not read_versions and "entity" not in record_types and not read_hashes:
            return EffectInspection("absent", receipt=f"item={qid}")

        expected_hash = canonical_sha256(entity_read_projection(payload))
        expected_subtype = [] if payload.get("subtype") is None else [payload["subtype"]]
        expected_created = [] if not payload.get("created_at") else [payload["created_at"]]
        expected_updated = [] if not payload.get("updated_at") else [payload["updated_at"]]
        structured_match = (
            read_versions == [READ_PROJECTION_VERSION]
            and record_types == ["entity"]
            and read_hashes == [expected_hash]
            and self._main_values(entity, "entity_type") == [payload["entity_type"]]
            and self._main_values(entity, "record_status") == [payload["record_status"]]
            and self._main_values(entity, "entity_subtype") == expected_subtype
            and self._main_values(entity, "created_at_iso") == expected_created
            and self._main_values(entity, "updated_at_iso") == expected_updated
        )
        native_match = (
            self._language_map(entity, "labels") == dict(payload["names"])
            and self._alias_pairs(entity) == self._payload_alias_pairs(payload)
            and self._language_map(entity, "descriptions")
            == dict(payload.get("descriptions") or {})
        )
        if structured_match and native_match:
            return EffectInspection("equivalent", receipt=f"item={qid}")
        return EffectInspection(
            "conflict",
            receipt=f"item={qid}",
            detail="entity public-read projection differs from the governed projection payload",
        )

    def _entity_statements(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        statements = super()._entity_statements(payload)
        payload_property = self.props["payload_sha256"]
        statements = [
            statement
            for statement in statements
            if statement.get("mainsnak", {}).get("property") != payload_property
        ]
        statements.append(
            self._simple_statement(
                self.props["read_projection_sha256"],
                "external-id",
                canonical_sha256(entity_read_projection(payload)),
            )
        )
        return statements

    def _event_read_inspection(self, mutation: Mapping[str, Any]) -> EffectInspection:
        base = self._item_inspection(mutation)
        if base.state != "equivalent":
            return base
        payload = mutation["payload"]
        qid = self._domain_item_matches(str(payload["id"]))[0]
        entity = self.api.get_entity(qid)
        read_versions = self._main_values(entity, "read_projection_version")
        confidences = [
            self._main_value(statement)
            for statement in entity.get("claims", {}).get(self.base_props["confidence"], [])
        ]
        read_hashes = self._main_values(entity, "read_projection_sha256")
        if not read_versions and not confidences and not read_hashes:
            return EffectInspection("absent", receipt=f"item={qid}")
        expected_hash = canonical_sha256(event_read_projection(payload))
        if (
            read_versions == [READ_PROJECTION_VERSION]
            and confidences == [payload["confidence"]]
            and read_hashes == [expected_hash]
        ):
            return EffectInspection("equivalent", receipt=f"item={qid}")
        return EffectInspection(
            "conflict",
            receipt=f"item={qid}",
            detail=(
                "event public-read metadata mismatch: "
                f"read_versions={read_versions}; confidences={confidences}; read_hashes={read_hashes}"
            ),
        )

    def _apply_event_read_metadata(self, payload: Mapping[str, Any]) -> str:
        qid = self._resolve_domain_item(str(payload["id"]))
        statements = [
            self._simple_statement(
                self.props["read_projection_version"], "string", READ_PROJECTION_VERSION
            ),
            self._simple_statement(
                self.props["read_projection_sha256"],
                "external-id",
                canonical_sha256(event_read_projection(payload)),
            ),
            self._simple_statement(
                self.base_props["confidence"], "string", payload["confidence"]
            ),
        ]
        result = self.api.post(
            action="wbeditentity",
            id=qid,
            data=json.dumps({"claims": statements}, ensure_ascii=False),
            token=self.api._token(),
            summary=f"SDA M1 public read: complete Event {payload['id']}",
        )
        entity = result["entity"]
        return f"item={entity['id']};revision={entity.get('lastrevid')}"


class WikibaseM1IntegrityReadAdapter(WikibaseM1ReadAdapter):
    """Verify public projection hashes while reconstructing SDA read records."""

    def _read_entity_item(self, qid: str) -> dict[str, Any]:
        entity = self._entity(qid)
        if not self._has_projection(entity, record_type="entity", read=True):
            raise ReadProjectionError(f"{qid} is not a current SDA public Entity projection")
        record: dict[str, Any] = {
            "id": self._canonical_id(qid),
            "entity_type": self._single(entity, self.props["entity_type"], f"{qid} entity_type"),
            "subtype": self._optional_single(entity, self.props["entity_subtype"], f"{qid} subtype"),
            "names": self._localized(entity, "labels"),
            "record_status": self._single(entity, self.props["record_status"], f"{qid} record_status"),
        }
        aliases = self._aliases(entity)
        if aliases:
            record["aliases"] = aliases
        descriptions = self._localized(entity, "descriptions")
        if descriptions:
            record["descriptions"] = descriptions
        created = self._optional_single(entity, self.props["created_at_iso"], f"{qid} created_at")
        updated = self._optional_single(entity, self.props["updated_at_iso"], f"{qid} updated_at")
        if created:
            record["created_at"] = created
        if updated:
            record["updated_at"] = updated
        expected_hash = self._single(
            entity,
            self.props["read_projection_sha256"],
            f"{qid} Entity public read projection hash",
        )
        if expected_hash != canonical_sha256(entity_read_projection(record)):
            raise ReadProjectionError(f"{qid} reconstructed Entity public projection hash mismatch")
        return record

    def _read_events(self) -> list[dict[str, Any]]:
        records = super()._read_events()
        qids_by_id: dict[str, str] = {}
        for qid in self.api.item_ids():
            try:
                qids_by_id[self._canonical_id(qid)] = qid
            except ReadProjectionError:
                continue
        for record in records:
            qid = qids_by_id.get(str(record["id"]))
            if qid is None:
                raise ReadProjectionError(f"Event {record['id']} lost backend identity during readback")
            entity = self._entity(qid)
            expected_hash = self._single(
                entity,
                self.props["read_projection_sha256"],
                f"{qid} Event public read projection hash",
            )
            if expected_hash != canonical_sha256(event_read_projection(record)):
                raise ReadProjectionError(
                    f"{qid} reconstructed Event public projection hash mismatch"
                )
        return records
