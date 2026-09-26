"""Governed metadata projection needed by the M1 public read adapter.

This layer extends the verified M1 mutation adapter only for metadata updates that
make existing domain Entities and the bounded delivery Event reconstructible by
the project-owned read path. It does not authorize mutations itself.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from services.governance.mutation_guard import DefinitiveWriteError, EffectInspection
from services.governance.proposal_auth import canonical_sha256

from m1_backend import WikibaseM1Backend

READ_PROJECTION_VERSION = "m1-public-v1"


class WikibaseM1PublicProjectionBackend(WikibaseM1Backend):
    """Add idempotent Entity/Event read-metadata updates to the M1 adapter."""

    @staticmethod
    def _language_map(entity: Mapping[str, Any], field: str) -> dict[str, str]:
        result: dict[str, str] = {}
        values = entity.get(field, {})
        if not isinstance(values, Mapping):
            return result
        for language in ("ar", "en"):
            value = values.get(language)
            if isinstance(value, Mapping) and isinstance(value.get("value"), str):
                result[language] = value["value"]
        return result

    @staticmethod
    def _alias_pairs(entity: Mapping[str, Any]) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        aliases = entity.get("aliases", {})
        if not isinstance(aliases, Mapping):
            return result
        for language in ("ar", "en"):
            values = aliases.get(language, [])
            if not isinstance(values, list):
                continue
            for value in values:
                if isinstance(value, Mapping) and isinstance(value.get("value"), str):
                    result.append((language, value["value"]))
        return sorted(result)

    @staticmethod
    def _payload_alias_pairs(payload: Mapping[str, Any]) -> list[tuple[str, str]]:
        result: list[tuple[str, str]] = []
        aliases = payload.get("aliases", [])
        if not isinstance(aliases, list):
            return result
        for alias in aliases:
            if not isinstance(alias, Mapping):
                continue
            language = alias.get("language")
            value = alias.get("value")
            if language in {"ar", "en"} and isinstance(value, str):
                result.append((str(language), value))
        return sorted(result)

    def _main_values(self, entity: Mapping[str, Any], property_key: str) -> list[Any]:
        property_id = self.props[property_key]
        return [
            self._main_value(statement)
            for statement in entity.get("claims", {}).get(property_id, [])
        ]

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
        hashes = self._main_values(entity, "payload_sha256")

        # A legacy M0 item has no SDA read projection yet; that is precisely the
        # bounded migration this metadata_update is allowed to apply.
        if not read_versions and "entity" not in record_types and not hashes:
            return EffectInspection("absent", receipt=f"item={qid}")

        expected_hash = canonical_sha256(payload)
        expected_subtype = [] if payload.get("subtype") is None else [payload["subtype"]]
        expected_created = [] if not payload.get("created_at") else [payload["created_at"]]
        expected_updated = [] if not payload.get("updated_at") else [payload["updated_at"]]
        structured_match = (
            read_versions == [READ_PROJECTION_VERSION]
            and record_types == ["entity"]
            and hashes == [expected_hash]
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
            detail="entity payload/native metadata differs from current SDA read projection",
        )

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
        if not read_versions and not confidences:
            return EffectInspection("absent", receipt=f"item={qid}")
        if read_versions == [READ_PROJECTION_VERSION] and confidences == [payload["confidence"]]:
            return EffectInspection("equivalent", receipt=f"item={qid}")
        return EffectInspection(
            "conflict",
            receipt=f"item={qid}",
            detail=(
                "event public-read metadata mismatch: "
                f"read_versions={read_versions}; confidences={confidences}"
            ),
        )

    def inspect_effect(
        self, *, idempotency_key: str, mutation: Mapping[str, Any]
    ) -> EffectInspection:
        if mutation.get("action") == "metadata_update":
            resource_type = str(mutation.get("resource_type"))
            if resource_type == "entity":
                return self._entity_inspection(mutation)
            if resource_type == "event":
                return self._event_read_inspection(mutation)
            return EffectInspection(
                "conflict",
                detail=f"unsupported public-read metadata resource: {resource_type}",
            )
        return super().inspect_effect(idempotency_key=idempotency_key, mutation=mutation)

    def _entity_statements(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        statements = [
            self._simple_statement(
                self.props["payload_sha256"], "external-id", canonical_sha256(payload)
            ),
            self._simple_statement(
                self.props["read_projection_version"], "string", READ_PROJECTION_VERSION
            ),
            self._simple_statement(self.props["record_type"], "string", "entity"),
            self._simple_statement(
                self.props["entity_type"], "string", payload["entity_type"]
            ),
            self._simple_statement(
                self.props["record_status"], "string", payload["record_status"]
            ),
        ]
        if payload.get("subtype") is not None:
            statements.append(
                self._simple_statement(
                    self.props["entity_subtype"], "string", payload["subtype"]
                )
            )
        if payload.get("created_at"):
            statements.append(
                self._simple_statement(
                    self.props["created_at_iso"], "string", payload["created_at"]
                )
            )
        if payload.get("updated_at"):
            statements.append(
                self._simple_statement(
                    self.props["updated_at_iso"], "string", payload["updated_at"]
                )
            )
        return statements

    @staticmethod
    def _alias_map(payload: Mapping[str, Any]) -> dict[str, list[str]]:
        result: dict[str, list[str]] = {}
        for alias in payload.get("aliases", []):
            if not isinstance(alias, Mapping):
                continue
            language = alias.get("language")
            value = alias.get("value")
            if language in {"ar", "en"} and isinstance(value, str):
                result.setdefault(str(language), []).append(value)
        return result

    def _apply_entity_metadata(self, payload: Mapping[str, Any]) -> str:
        qid = self._resolve_domain_item(str(payload["id"]))
        data: dict[str, Any] = {
            "labels": self.api._language_values(dict(payload["names"])),
            "claims": self._entity_statements(payload),
        }
        aliases = self._alias_map(payload)
        if aliases:
            data["aliases"] = self.api._aliases(aliases)
        descriptions = payload.get("descriptions")
        if isinstance(descriptions, Mapping) and descriptions:
            data["descriptions"] = self.api._language_values(dict(descriptions))
        result = self.api.post(
            action="wbeditentity",
            id=qid,
            data=json.dumps(data, ensure_ascii=False),
            token=self.api._token(),
            summary=f"SDA M1 public read: project Entity {payload['id']}",
        )
        entity = result["entity"]
        return f"item={entity['id']};revision={entity.get('lastrevid')}"

    def _apply_event_read_metadata(self, payload: Mapping[str, Any]) -> str:
        qid = self._resolve_domain_item(str(payload["id"]))
        statements = [
            self._simple_statement(
                self.props["read_projection_version"], "string", READ_PROJECTION_VERSION
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

    def apply_effect(
        self, *, idempotency_key: str, mutation: Mapping[str, Any]
    ) -> str | None:
        if mutation.get("action") != "metadata_update":
            return super().apply_effect(idempotency_key=idempotency_key, mutation=mutation)
        resource_type = str(mutation.get("resource_type"))
        payload = mutation.get("payload")
        if not isinstance(payload, Mapping):
            raise DefinitiveWriteError("metadata_update payload must be an object")
        if mutation.get("target_id") != payload.get("id"):
            raise DefinitiveWriteError("metadata_update target_id must equal payload canonical ID")
        try:
            if resource_type == "entity":
                return self._apply_entity_metadata(payload)
            if resource_type == "event":
                return self._apply_event_read_metadata(payload)
            raise DefinitiveWriteError(
                f"unsupported public-read metadata resource: {resource_type}"
            )
        except DefinitiveWriteError:
            raise
        except Exception as exc:  # noqa: BLE001 - preserve base write semantics.
            raise self._translate_write_error(exc) from exc
