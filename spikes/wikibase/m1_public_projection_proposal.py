"""Build the bounded AMBER proposal that qualifies M1 public read projection."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def _stable_suffix(value: Mapping[str, Any], length: int = 20) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:length].upper()


def entity_payloads() -> list[dict[str, Any]]:
    """Return the three domain Entity records needed by the bounded public slice.

    These are migration payloads for the preexisting M0 domain items; once
    approved/applied, canonical readback comes from Wikibase rather than this
    helper or the frontend. Lifecycle timestamps are intentionally omitted:
    the migration time is not the Entity's original creation/update time.
    """
    return [
        {
            "id": "SDA-EQUIP-F15SA",
            "entity_type": "equipment_variant",
            "subtype": "fighter_aircraft_variant",
            "names": {"en": "F-15SA", "ar": "إف-15 إس إيه"},
            "aliases": [
                {"value": "Saudi Advanced Eagle", "language": "en"}
            ],
            "record_status": "active",
        },
        {
            "id": "SDA-ORG-BOEING",
            "entity_type": "organization",
            "subtype": "manufacturer",
            "names": {"en": "Boeing", "ar": "بوينغ"},
            "record_status": "active",
        },
        {
            "id": "SDA-ORG-RSAF",
            "entity_type": "organization",
            "subtype": "military_service",
            "names": {
                "en": "Royal Saudi Air Force",
                "ar": "القوات الجوية الملكية السعودية",
            },
            "aliases": [
                {"value": "RSAF", "language": "en"},
                {"value": "القوات الجوية السعودية", "language": "ar"},
            ],
            "descriptions": {
                "en": "Saudi military aviation service",
                "ar": "القوة الجوية العسكرية السعودية",
            },
            "record_status": "active",
        },
    ]


def build_public_projection_proposal(
    *, event_payload: Mapping[str, Any], created_at: str
) -> dict[str, Any]:
    entities = entity_payloads()
    mutations: list[dict[str, Any]] = []
    for entity in entities:
        mutations.append(
            {
                "id": f"SDA-MUT-READ-ENTITY-{_stable_suffix(entity)}",
                "action": "metadata_update",
                "resource_type": "entity",
                "target_id": entity["id"],
                "payload": entity,
            }
        )

    event = dict(event_payload)
    mutations.append(
        {
            "id": f"SDA-MUT-READ-EVENT-{_stable_suffix(event)}",
            "action": "metadata_update",
            "resource_type": "event",
            "target_id": event["id"],
            "payload": event,
        }
    )

    seed = {"mutation_ids": [mutation["id"] for mutation in mutations]}
    return {
        "id": f"SDA-PROPOSAL-M1-PUBLIC-READ-{_stable_suffix(seed)}",
        "created_at": created_at,
        "created_by": {
            "kind": "system",
            "id": "m1-public-read-migration-builder",
            "provider": None,
            "model": None,
            "version": "m1-public-v1",
        },
        "source_document_ids": [],
        "risk_class": "AMBER",
        "policy_outcome": "human_review_required",
        "policy_reasons": [
            "canonical Entity read projection",
            "Event public confidence projection",
            "first bilingual public read slice",
        ],
        "rationale": (
            "Project mandatory Entity semantics and the bounded delivery Event confidence "
            "into the canonical backend so the public reader needs no secondary truth store."
        ),
        "supersedes_proposal_id": None,
        "mutations": mutations,
    }
