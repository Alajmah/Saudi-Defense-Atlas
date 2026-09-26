"""Project-owned Wikibase read adapter for the bounded M1 public slice.

The adapter exposes SDA identities and public-domain records, never raw Q/P IDs.
Only statements carrying explicit SDA projection markers are admitted. Legacy M0
trial statements therefore remain backend history and cannot become public facts.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from services.governance.proposal_auth import canonical_sha256

from m1_backend import PROJECTION_VERSION
from m1_public_projection_backend import READ_PROJECTION_VERSION
from m1_wikibase_api import M1WikibaseAPI


class ReadProjectionError(ValueError):
    pass


_PRECISION = {9: "year", 10: "month", 11: "day", 14: "second"}


class WikibaseM1ReadAdapter:
    def __init__(self, *, api: M1WikibaseAPI, base_state: Mapping[str, Any], projection_state: Mapping[str, Any]) -> None:
        self.api = api
        self.base_props: Mapping[str, str] = base_state["properties"]
        self.props: Mapping[str, str] = projection_state["properties"]
        self._entity_cache: dict[str, dict[str, Any]] = {}
        self._canonical_cache: dict[str, str] = {}

    @staticmethod
    def _main_value(statement: Mapping[str, Any]) -> Any:
        return statement.get("mainsnak", {}).get("datavalue", {}).get("value")

    @staticmethod
    def _qualifier_values(statement: Mapping[str, Any], property_id: str) -> list[Any]:
        return [
            snak.get("datavalue", {}).get("value")
            for snak in statement.get("qualifiers", {}).get(property_id, [])
        ]

    @staticmethod
    def _reference_values(reference: Mapping[str, Any], property_id: str) -> list[Any]:
        return [
            snak.get("datavalue", {}).get("value")
            for snak in reference.get("snaks", {}).get(property_id, [])
        ]

    @staticmethod
    def _qid(value: Any) -> str:
        if not isinstance(value, Mapping) or not isinstance(value.get("numeric-id"), int):
            raise ReadProjectionError(f"expected wikibase-item value, got {value!r}")
        return f"Q{value['numeric-id']}"

    def _entity(self, qid: str) -> dict[str, Any]:
        if qid not in self._entity_cache:
            self._entity_cache[qid] = self.api.get_entity(qid)
        return self._entity_cache[qid]

    def _main_values(self, entity: Mapping[str, Any], property_id: str) -> list[Any]:
        return [
            self._main_value(statement)
            for statement in entity.get("claims", {}).get(property_id, [])
        ]

    def _single(self, entity: Mapping[str, Any], property_id: str, label: str) -> Any:
        values = self._main_values(entity, property_id)
        if len(values) != 1:
            raise ReadProjectionError(f"{label} expected exactly one value, got {values}")
        return values[0]

    def _optional_single(self, entity: Mapping[str, Any], property_id: str, label: str) -> Any | None:
        values = self._main_values(entity, property_id)
        if len(values) > 1:
            raise ReadProjectionError(f"{label} expected at most one value, got {values}")
        return values[0] if values else None

    def _canonical_id(self, qid: str) -> str:
        if qid in self._canonical_cache:
            return self._canonical_cache[qid]
        value = self._single(self._entity(qid), self.base_props["canonical_id"], f"{qid} SDA canonical ID")
        if not isinstance(value, str):
            raise ReadProjectionError(f"{qid} SDA canonical ID is not a string")
        self._canonical_cache[qid] = value
        return value

    @staticmethod
    def _localized(entity: Mapping[str, Any], field: str) -> dict[str, str]:
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
    def _aliases(entity: Mapping[str, Any]) -> list[dict[str, str]]:
        result: list[dict[str, str]] = []
        values = entity.get("aliases", {})
        if not isinstance(values, Mapping):
            return result
        for language in ("ar", "en"):
            entries = values.get(language, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if isinstance(entry, Mapping) and isinstance(entry.get("value"), str):
                    result.append({"value": entry["value"], "language": language})
        return sorted(result, key=lambda item: (item["language"], item["value"]))

    @staticmethod
    def _time(value: Any) -> dict[str, str]:
        if not isinstance(value, Mapping):
            raise ReadProjectionError(f"invalid Wikibase time value: {value!r}")
        raw = value.get("time")
        precision = value.get("precision")
        if not isinstance(raw, str) or precision not in _PRECISION:
            raise ReadProjectionError(f"unsupported Wikibase time value: {value!r}")
        date = raw.lstrip("+").split("T", 1)[0]
        if precision == 9:
            rendered = date[:4]
        elif precision == 10:
            rendered = date[:7]
        else:
            rendered = date
        return {"value": rendered, "precision": _PRECISION[precision]}

    def _has_projection(self, entity: Mapping[str, Any], *, record_type: str, read: bool = False) -> bool:
        record_types = self._main_values(entity, self.props["record_type"])
        if record_types != [record_type]:
            return False
        if read:
            return self._main_values(entity, self.props["read_projection_version"]) == [READ_PROJECTION_VERSION]
        return self._main_values(entity, self.props["projection_version"]) == [PROJECTION_VERSION]

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
        expected_hash = self._single(entity, self.props["payload_sha256"], f"{qid} Entity payload hash")
        if expected_hash != canonical_sha256(record):
            raise ReadProjectionError(f"{qid} reconstructed Entity payload hash mismatch")
        return record

    def read_entities(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for qid in self.api.item_ids():
            entity = self._entity(qid)
            if self._has_projection(entity, record_type="entity", read=True):
                records.append(self._read_entity_item(qid))
        return sorted(records, key=lambda record: record["id"])

    def _read_sources(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for qid in self.api.item_ids():
            entity = self._entity(qid)
            if not self._has_projection(entity, record_type="source"):
                continue
            record = {
                "id": self._canonical_id(qid),
                "publisher": self._localized(entity, "labels"),
                "source_class": self._single(entity, self.props["source_class"], f"{qid} source_class"),
                "publisher_type": self._single(entity, self.props["publisher_type"], f"{qid} publisher_type"),
            }
            homepage = self._optional_single(entity, self.props["source_homepage"], f"{qid} homepage")
            jurisdiction = self._optional_single(entity, self.props["jurisdiction"], f"{qid} jurisdiction")
            if homepage:
                record["homepage"] = homepage
            if jurisdiction:
                record["jurisdiction"] = jurisdiction
            records.append(record)
        return sorted(records, key=lambda record: record["id"])

    def _read_documents(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for qid in self.api.item_ids():
            entity = self._entity(qid)
            if not self._has_projection(entity, record_type="document"):
                continue
            source_qid = self._qid(self._single(entity, self.props["document_source"], f"{qid} document source"))
            record: dict[str, Any] = {
                "id": self._canonical_id(qid),
                "source_id": self._canonical_id(source_qid),
                "title": self._localized(entity, "labels"),
                "retrieved_at": self._single(entity, self.props["retrieved_at_iso"], f"{qid} retrieved_at"),
                "language": self._single(entity, self.props["content_language"], f"{qid} language"),
                "document_type": self._single(entity, self.props["document_type"], f"{qid} document_type"),
                "content_sha256": self._single(entity, self.props["content_sha256"], f"{qid} content_sha256"),
            }
            url = self._optional_single(entity, self.props["document_url"], f"{qid} URL")
            media_type = self._optional_single(entity, self.props["media_type"], f"{qid} media_type")
            published = self._optional_single(entity, self.props["published_at"], f"{qid} published_at")
            if url:
                record["canonical_url"] = url
            if media_type:
                record["media_type"] = media_type
            if published:
                record["published_at"] = self._time(published)
            records.append(record)
        return sorted(records, key=lambda record: record["id"])

    def _read_evidence(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for qid in self.api.item_ids():
            entity = self._entity(qid)
            if not self._has_projection(entity, record_type="evidence"):
                continue
            document_qid = self._qid(self._single(entity, self.props["evidence_document"], f"{qid} Evidence Document"))
            selector = self._optional_single(entity, self.props["evidence_selector"], f"{qid} selector")
            if not selector:
                raise ReadProjectionError(f"{qid} public Evidence requires selector")
            records.append(
                {
                    "id": self._canonical_id(qid),
                    "document_id": self._canonical_id(document_qid),
                    "locator": {"selector": selector},
                    "captured_at": self._single(entity, self.props["captured_at_iso"], f"{qid} captured_at"),
                    "capture_method": self._single(entity, self.props["capture_method"], f"{qid} capture_method"),
                }
            )
        return sorted(records, key=lambda record: record["id"])

    def _read_claims(self) -> list[dict[str, Any]]:
        property_map = {
            self.props["manufactures_equipment"]: "manufacturer.manufactures.equipment",
            self.props["operates_equipment_variant"]: "organization.operates.equipment_variant",
        }
        records: list[dict[str, Any]] = []
        for subject_qid in self.api.item_ids():
            subject = self._entity(subject_qid)
            try:
                subject_id = self._canonical_id(subject_qid)
            except ReadProjectionError:
                continue
            for property_id, predicate in property_map.items():
                for statement in subject.get("claims", {}).get(property_id, []):
                    versions = self._qualifier_values(statement, self.props["projection_version"])
                    claim_ids = self._qualifier_values(statement, self.base_props["claim_id"])
                    hashes = self._qualifier_values(statement, self.props["payload_sha256"])
                    if versions != [PROJECTION_VERSION] or len(claim_ids) != 1 or len(hashes) != 1:
                        continue
                    confidence = self._qualifier_values(statement, self.base_props["confidence"])
                    state = self._qualifier_values(statement, self.props["claim_state"])
                    created = self._qualifier_values(statement, self.props["created_at_iso"])
                    if len(confidence) != 1 or len(state) != 1 or len(created) != 1:
                        raise ReadProjectionError(f"Claim {claim_ids[0]} has incomplete projection qualifiers")
                    object_qid = self._qid(self._main_value(statement))
                    evidence_links: list[dict[str, str]] = []
                    for reference in statement.get("references", []):
                        evidence_ids = self._reference_values(reference, self.props["evidence_id"])
                        roles = self._reference_values(reference, self.props["evidence_role"])
                        if len(evidence_ids) != 1 or len(roles) != 1:
                            raise ReadProjectionError(f"Claim {claim_ids[0]} has incomplete Evidence reference")
                        evidence_links.append({"evidence_id": evidence_ids[0], "role": roles[0]})
                    record: dict[str, Any] = {
                        "id": claim_ids[0],
                        "subject_id": subject_id,
                        "predicate_id": predicate,
                        "value": {"kind": "entity", "entity_id": self._canonical_id(object_qid)},
                        "confidence": confidence[0],
                        "evidence_links": evidence_links,
                        "claim_state": state[0],
                        "created_at": created[0],
                    }
                    points = self._qualifier_values(statement, self.base_props["point_in_time"])
                    if len(points) > 1:
                        raise ReadProjectionError(f"Claim {claim_ids[0]} has multiple point-in-time values")
                    if points:
                        record["validity"] = {"point_in_time": self._time(points[0])}
                    records.append(record)
        return sorted(records, key=lambda record: record["id"])

    def _read_events(self) -> list[dict[str, Any]]:
        records: list[dict[str, Any]] = []
        for qid in self.api.item_ids():
            entity = self._entity(qid)
            if not self._has_projection(entity, record_type="event"):
                continue
            if self._main_values(entity, self.props["read_projection_version"]) != [READ_PROJECTION_VERSION]:
                continue
            participants: list[dict[str, str]] = []
            for statement in entity.get("claims", {}).get(self.base_props["participant"], []):
                roles = self._qualifier_values(statement, self.props["participant_role"])
                if len(roles) != 1:
                    raise ReadProjectionError(f"{qid} Event participant lacks one role")
                participants.append(
                    {"entity_id": self._canonical_id(self._qid(self._main_value(statement))), "role": roles[0]}
                )
            evidence_links: list[dict[str, str]] = []
            for statement in entity.get("claims", {}).get(self.props["evidence_link"], []):
                roles = self._qualifier_values(statement, self.props["evidence_role"])
                if len(roles) != 1:
                    raise ReadProjectionError(f"{qid} Event Evidence link lacks one role")
                evidence_links.append(
                    {"evidence_id": self._canonical_id(self._qid(self._main_value(statement))), "role": roles[0]}
                )
            related_entity_ids = [
                self._canonical_id(self._qid(value))
                for value in self._main_values(entity, self.base_props["related_item"])
            ]
            related_claim_ids = [
                str(value) for value in self._main_values(entity, self.props["related_claim_id"])
            ]
            records.append(
                {
                    "id": self._canonical_id(qid),
                    "event_type": self._single(entity, self.base_props["event_type"], f"{qid} event_type"),
                    "names": self._localized(entity, "labels"),
                    "occurred_at": self._time(self._single(entity, self.base_props["event_date"], f"{qid} event_date")),
                    "participants": participants,
                    "related_entity_ids": related_entity_ids,
                    "related_claim_ids": related_claim_ids,
                    "confidence": self._single(entity, self.base_props["confidence"], f"{qid} confidence"),
                    "evidence_links": evidence_links,
                    "created_at": self._single(entity, self.props["created_at_iso"], f"{qid} created_at"),
                }
            )
        return sorted(records, key=lambda record: record["id"])

    def read_bundle(self, target_id: str) -> dict[str, list[dict[str, Any]]]:
        entities = self.read_entities()
        if target_id not in {record["id"] for record in entities}:
            raise ReadProjectionError(f"target Entity {target_id} is not publicly projected")
        return {
            "entities": entities,
            "claims": self._read_claims(),
            "events": self._read_events(),
            "evidence": self._read_evidence(),
            "documents": self._read_documents(),
            "sources": self._read_sources(),
        }
