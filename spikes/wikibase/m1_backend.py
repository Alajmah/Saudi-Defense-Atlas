"""Wikibase MutationBackend for the bounded M1 F-15SA vertical slice.

The adapter owns projection mechanics only. Proposal authorization, retry policy,
and project Revision creation remain in services/governance.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Mapping

import requests

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.governance.mutation_guard import (  # noqa: E402
    AmbiguousWriteError,
    DefinitiveWriteError,
    EffectInspection,
)
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from wikibase_api import WikibaseAPIError, item_value, time_value  # noqa: E402
from m1_wikibase_api import M1WikibaseAPI  # noqa: E402


class WikibaseM1Backend:
    name = "wikibase"

    def __init__(
        self,
        *,
        api: M1WikibaseAPI,
        base_state: Mapping[str, Any],
        projection_state: Mapping[str, Any],
        proposal: Mapping[str, Any],
    ) -> None:
        self.api = api
        self.base_props: Mapping[str, str] = base_state["properties"]
        self.props: Mapping[str, str] = projection_state["properties"]
        mutations = proposal.get("mutations", [])
        self.payload_by_id = {
            str(mutation["payload"]["id"]): mutation["payload"]
            for mutation in mutations
            if isinstance(mutation, Mapping)
            and isinstance(mutation.get("payload"), Mapping)
            and isinstance(mutation["payload"].get("id"), str)
        }

    @staticmethod
    def _main_value(statement: Mapping[str, Any]) -> Any:
        return statement.get("mainsnak", {}).get("datavalue", {}).get("value")

    @staticmethod
    def _qualifier_values(statement: Mapping[str, Any], property_id: str) -> list[Any]:
        return [
            snak.get("datavalue", {}).get("value")
            for snak in statement.get("qualifiers", {}).get(property_id, [])
        ]

    def _domain_item_matches(self, canonical_id: str) -> list[str]:
        return self.api.find_items_by_string_claim(
            self.base_props["canonical_id"], canonical_id
        )

    def _resolve_domain_item(self, canonical_id: str) -> str:
        matches = self._domain_item_matches(canonical_id)
        if len(matches) != 1:
            raise DefinitiveWriteError(
                f"canonical ID {canonical_id!r} resolved to {len(matches)} Wikibase items"
            )
        return matches[0]

    def _payload_digest(self, mutation: Mapping[str, Any]) -> str:
        payload = mutation.get("payload")
        if not isinstance(payload, Mapping):
            raise DefinitiveWriteError("mutation payload must be an object")
        return canonical_sha256(payload)

    def _item_inspection(self, mutation: Mapping[str, Any]) -> EffectInspection:
        payload = mutation["payload"]
        canonical_id = str(payload["id"])
        matches = self._domain_item_matches(canonical_id)
        if not matches:
            return EffectInspection("absent")
        if len(matches) != 1:
            return EffectInspection(
                "conflict", detail=f"canonical ID maps to {len(matches)} items"
            )
        qid = matches[0]
        entity = self.api.get_entity(qid)
        statements = entity.get("claims", {}).get(self.props["payload_sha256"], [])
        hashes = [self._main_value(statement) for statement in statements]
        expected = self._payload_digest(mutation)
        if hashes == [expected]:
            return EffectInspection("equivalent", receipt=f"item={qid}")
        if expected in hashes and len(hashes) == 1:
            return EffectInspection("equivalent", receipt=f"item={qid}")
        return EffectInspection(
            "conflict",
            receipt=f"item={qid}",
            detail=f"payload hash mismatch or multiplicity: {hashes}",
        )

    def _claim_property(self, payload: Mapping[str, Any]) -> str:
        predicate = str(payload.get("predicate_id"))
        if predicate != "organization.operates.equipment_variant":
            raise DefinitiveWriteError(f"unsupported M1 predicate: {predicate}")
        return self.props["operates_equipment_variant"]

    def _claim_inspection(self, mutation: Mapping[str, Any]) -> EffectInspection:
        payload = mutation["payload"]
        try:
            subject_qid = self._resolve_domain_item(str(payload["subject_id"]))
            property_id = self._claim_property(payload)
        except DefinitiveWriteError as exc:
            return EffectInspection("unknown", detail=str(exc))

        entity = self.api.get_entity(subject_qid)
        matches = []
        for statement in entity.get("claims", {}).get(property_id, []):
            claim_ids = self._qualifier_values(statement, self.base_props["claim_id"])
            if str(payload["id"]) in claim_ids:
                matches.append(statement)
        if not matches:
            return EffectInspection("absent")
        if len(matches) != 1:
            return EffectInspection(
                "conflict", detail=f"claim ID appears on {len(matches)} statements"
            )

        statement = matches[0]
        hashes = self._qualifier_values(statement, self.props["payload_sha256"])
        expected = self._payload_digest(mutation)
        receipt = f"item={subject_qid};statement={statement.get('id')}"
        if hashes == [expected]:
            return EffectInspection("equivalent", receipt=receipt)
        return EffectInspection(
            "conflict", receipt=receipt, detail=f"claim payload hash mismatch: {hashes}"
        )

    def inspect_effect(
        self, *, idempotency_key: str, mutation: Mapping[str, Any]
    ) -> EffectInspection:
        del idempotency_key  # semantic equivalence is record ID + exact payload hash.
        if mutation.get("action") != "create":
            return EffectInspection(
                "conflict", detail=f"unsupported M1 action: {mutation.get('action')}"
            )
        resource_type = str(mutation.get("resource_type"))
        if resource_type == "claim":
            return self._claim_inspection(mutation)
        if resource_type in {"source", "document", "evidence", "event"}:
            return self._item_inspection(mutation)
        return EffectInspection("conflict", detail=f"unsupported resource type: {resource_type}")

    def _snak(self, property_id: str, datatype: str, value: Any) -> dict[str, Any]:
        return self.api.make_snak(property_id, datatype, value)

    def _simple_statement(self, property_id: str, datatype: str, value: Any) -> dict[str, Any]:
        return self.api.statement(self._snak(property_id, datatype, value))

    def _identity_statements(
        self, resource_type: str, payload: Mapping[str, Any]
    ) -> list[dict[str, Any]]:
        return [
            self._simple_statement(
                self.base_props["canonical_id"], "external-id", str(payload["id"])
            ),
            self._simple_statement(
                self.props["payload_sha256"], "external-id", canonical_sha256(payload)
            ),
            self._simple_statement(self.props["record_type"], "string", resource_type),
        ]

    def _item_labels(self, resource_type: str, payload: Mapping[str, Any]) -> dict[str, str]:
        if resource_type == "source":
            labels = payload.get("publisher")
        elif resource_type == "document":
            labels = payload.get("title")
        elif resource_type == "event":
            labels = payload.get("names")
        else:
            fragment = payload.get("locator", {}).get("fragment")
            labels = {"en": f"Evidence: {fragment or payload['id']}"}
        if isinstance(labels, Mapping) and labels:
            return {str(key): str(value) for key, value in labels.items() if value}
        return {"en": str(payload["id"])}

    def _source_statements(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        statements = self._identity_statements("source", payload)
        statements.append(
            self._simple_statement(self.props["source_class"], "string", payload["source_class"])
        )
        statements.append(
            self._simple_statement(
                self.props["publisher_type"], "string", payload["publisher_type"]
            )
        )
        if payload.get("homepage"):
            statements.append(
                self._simple_statement(
                    self.props["source_homepage"], "url", payload["homepage"]
                )
            )
        if payload.get("jurisdiction"):
            statements.append(
                self._simple_statement(
                    self.props["jurisdiction"], "string", payload["jurisdiction"]
                )
            )
        return statements

    def _document_statements(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        source_qid = self._resolve_domain_item(str(payload["source_id"]))
        statements = self._identity_statements("document", payload)
        statements.extend(
            [
                self._simple_statement(
                    self.props["document_source"], "wikibase-item", item_value(source_qid)
                ),
                self._simple_statement(
                    self.props["document_type"], "string", payload["document_type"]
                ),
                self._simple_statement(
                    self.props["content_language"], "string", payload["language"]
                ),
                self._simple_statement(
                    self.props["content_sha256"], "external-id", payload["content_sha256"]
                ),
                self._simple_statement(
                    self.props["retrieved_at_iso"], "string", payload["retrieved_at"]
                ),
            ]
        )
        if payload.get("canonical_url"):
            statements.append(
                self._simple_statement(
                    self.props["document_url"], "url", payload["canonical_url"]
                )
            )
        if payload.get("media_type"):
            statements.append(
                self._simple_statement(
                    self.props["media_type"], "string", payload["media_type"]
                )
            )
        published = payload.get("published_at")
        if isinstance(published, Mapping):
            statements.append(
                self._simple_statement(
                    self.props["published_at"],
                    "time",
                    time_value(str(published["value"]), str(published["precision"])),
                )
            )
        return statements

    def _evidence_statements(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        document_qid = self._resolve_domain_item(str(payload["document_id"]))
        selector = payload.get("locator", {}).get("selector")
        statements = self._identity_statements("evidence", payload)
        statements.append(
            self._simple_statement(
                self.props["evidence_document"], "wikibase-item", item_value(document_qid)
            )
        )
        if selector:
            statements.append(
                self._simple_statement(self.props["evidence_selector"], "string", selector)
            )
        if payload.get("excerpt_sha256"):
            statements.append(
                self._simple_statement(
                    self.props["evidence_sha256"], "external-id", payload["excerpt_sha256"]
                )
            )
        return statements

    def _event_statements(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        statements = self._identity_statements("event", payload)
        statements.extend(
            [
                self._simple_statement(
                    self.base_props["event_type"], "string", payload["event_type"]
                ),
                self._simple_statement(
                    self.base_props["event_date"],
                    "time",
                    time_value(
                        str(payload["occurred_at"]["value"]),
                        str(payload["occurred_at"]["precision"]),
                    ),
                ),
            ]
        )
        for participant in payload.get("participants", []):
            participant_qid = self._resolve_domain_item(str(participant["entity_id"]))
            role_snak = self._snak(
                self.props["participant_role"], "string", participant["role"]
            )
            statements.append(
                self.api.statement(
                    self._snak(
                        self.base_props["participant"],
                        "wikibase-item",
                        item_value(participant_qid),
                    ),
                    qualifiers={self.props["participant_role"]: [role_snak]},
                )
            )
        for entity_id in payload.get("related_entity_ids", []):
            qid = self._resolve_domain_item(str(entity_id))
            statements.append(
                self._simple_statement(
                    self.base_props["related_item"], "wikibase-item", item_value(qid)
                )
            )
        for link in payload.get("evidence_links", []):
            evidence_qid = self._resolve_domain_item(str(link["evidence_id"]))
            role_snak = self._snak(
                self.props["evidence_role"], "string", link["role"]
            )
            statements.append(
                self.api.statement(
                    self._snak(
                        self.props["evidence_link"],
                        "wikibase-item",
                        item_value(evidence_qid),
                    ),
                    qualifiers={self.props["evidence_role"]: [role_snak]},
                )
            )
        return statements

    def _item_statements(self, resource_type: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        if resource_type == "source":
            return self._source_statements(payload)
        if resource_type == "document":
            return self._document_statements(payload)
        if resource_type == "evidence":
            return self._evidence_statements(payload)
        if resource_type == "event":
            return self._event_statements(payload)
        raise DefinitiveWriteError(f"unsupported item resource type: {resource_type}")

    def _claim_references(self, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
        references: list[dict[str, Any]] = []
        for link in payload.get("evidence_links", []):
            evidence = self.payload_by_id.get(str(link["evidence_id"]))
            if not isinstance(evidence, Mapping):
                raise DefinitiveWriteError("claim Evidence payload is missing from proposal")
            document = self.payload_by_id.get(str(evidence["document_id"]))
            if not isinstance(document, Mapping):
                raise DefinitiveWriteError("Evidence Document payload is missing from proposal")
            snaks: dict[str, list[dict[str, Any]]] = {
                self.props["evidence_id"]: [
                    self._snak(
                        self.props["evidence_id"], "external-id", str(evidence["id"])
                    )
                ],
                self.base_props["document_id"]: [
                    self._snak(
                        self.base_props["document_id"],
                        "external-id",
                        str(document["id"]),
                    )
                ],
                self.props["evidence_role"]: [
                    self._snak(self.props["evidence_role"], "string", str(link["role"]))
                ],
            }
            selector = evidence.get("locator", {}).get("selector")
            if selector:
                snaks[self.props["evidence_selector"]] = [
                    self._snak(self.props["evidence_selector"], "string", selector)
                ]
            if document.get("canonical_url"):
                snaks[self.base_props["reference_url"]] = [
                    self._snak(
                        self.base_props["reference_url"], "url", document["canonical_url"]
                    )
                ]
            references.append({"snaks": snaks})
        return references

    def _claim_statement(self, payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        subject_qid = self._resolve_domain_item(str(payload["subject_id"]))
        value = payload.get("value", {})
        if value.get("kind") != "entity":
            raise DefinitiveWriteError("M1 operator Claim requires an entity value")
        object_qid = self._resolve_domain_item(str(value["entity_id"]))
        property_id = self._claim_property(payload)
        qualifiers: dict[str, list[dict[str, Any]]] = {
            self.base_props["claim_id"]: [
                self._snak(self.base_props["claim_id"], "external-id", payload["id"])
            ],
            self.props["payload_sha256"]: [
                self._snak(
                    self.props["payload_sha256"],
                    "external-id",
                    canonical_sha256(payload),
                )
            ],
            self.base_props["confidence"]: [
                self._snak(self.base_props["confidence"], "string", payload["confidence"])
            ],
        }
        point = payload.get("validity", {}).get("point_in_time")
        if isinstance(point, Mapping):
            qualifiers[self.base_props["point_in_time"]] = [
                self._snak(
                    self.base_props["point_in_time"],
                    "time",
                    time_value(str(point["value"]), str(point["precision"])),
                )
            ]
        statement = self.api.statement(
            self._snak(property_id, "wikibase-item", item_value(object_qid)),
            qualifiers=qualifiers,
            references=self._claim_references(payload),
        )
        return subject_qid, statement

    def _translate_write_error(self, exc: Exception) -> Exception:
        if isinstance(exc, (requests.Timeout, requests.ConnectionError)):
            return AmbiguousWriteError(str(exc))
        if isinstance(exc, requests.HTTPError):
            status = exc.response.status_code if exc.response is not None else 0
            if status >= 500:
                return AmbiguousWriteError(str(exc))
            return DefinitiveWriteError(str(exc))
        if isinstance(exc, WikibaseAPIError):
            return DefinitiveWriteError(str(exc))
        return DefinitiveWriteError(str(exc))

    def apply_effect(
        self, *, idempotency_key: str, mutation: Mapping[str, Any]
    ) -> str | None:
        del idempotency_key  # retained in the project execution/Revision receipt.
        if mutation.get("action") != "create":
            raise DefinitiveWriteError(f"unsupported M1 action: {mutation.get('action')}")
        resource_type = str(mutation.get("resource_type"))
        payload = mutation.get("payload")
        if not isinstance(payload, Mapping):
            raise DefinitiveWriteError("mutation payload must be an object")
        try:
            if resource_type == "claim":
                subject_qid, statement = self._claim_statement(payload)
                edited = self.api.add_statement_bundle(
                    entity_id=subject_qid,
                    statement=statement,
                    summary=f"SDA M1: apply Claim {payload['id']}",
                )
                return f"item={edited.entity_id};revision={edited.lastrevid}"
            if resource_type in {"source", "document", "evidence", "event"}:
                created = self.api.create_item_with_statements(
                    labels=self._item_labels(resource_type, payload),
                    statements=self._item_statements(resource_type, payload),
                    summary=f"SDA M1: create {resource_type} {payload['id']}",
                )
                return f"item={created.entity_id};revision={created.lastrevid}"
            raise DefinitiveWriteError(f"unsupported resource type: {resource_type}")
        except DefinitiveWriteError:
            raise
        except Exception as exc:  # noqa: BLE001 - translate backend/network semantics.
            raise self._translate_write_error(exc) from exc
