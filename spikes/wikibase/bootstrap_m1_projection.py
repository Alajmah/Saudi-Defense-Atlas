#!/usr/bin/env python3
"""Create M1-only Wikibase projection properties after the M0 seed.

The property set is an adapter vocabulary, not the SDA ontology. In particular,
`operates_equipment_variant` preserves the accepted project predicate direction
instead of reusing the reversed M0 trial `operator` property.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from wikibase_api import WikibaseAPI

SPIKE_DIR = Path(__file__).resolve().parent
OUTPUT_PATH = SPIKE_DIR / "m1_projection_state.generated.json"


def property_defs() -> dict[str, dict[str, str]]:
    return {
        "payload_sha256": {"en": "SDA payload SHA-256", "datatype": "external-id"},
        "record_type": {"en": "SDA record type", "datatype": "string"},
        "source_class": {"en": "SDA source class", "datatype": "string"},
        "source_homepage": {"en": "source homepage", "datatype": "url"},
        "publisher_type": {"en": "publisher type", "datatype": "string"},
        "jurisdiction": {"en": "jurisdiction", "datatype": "string"},
        "document_source": {"en": "document source", "datatype": "wikibase-item"},
        "document_url": {"en": "document URL", "datatype": "url"},
        "document_type": {"en": "document type", "datatype": "string"},
        "content_language": {"en": "content language", "datatype": "string"},
        "media_type": {"en": "media type", "datatype": "string"},
        "content_sha256": {"en": "canonical content SHA-256", "datatype": "external-id"},
        "retrieved_at_iso": {"en": "retrieved at ISO timestamp", "datatype": "string"},
        "published_at": {"en": "published at", "datatype": "time"},
        "evidence_document": {"en": "evidence document", "datatype": "wikibase-item"},
        "evidence_selector": {"en": "evidence selector", "datatype": "string"},
        "evidence_sha256": {"en": "evidence SHA-256", "datatype": "external-id"},
        "evidence_id": {"en": "SDA evidence ID", "datatype": "external-id"},
        "evidence_link": {"en": "evidence link", "datatype": "wikibase-item"},
        "evidence_role": {"en": "evidence role", "datatype": "string"},
        "operates_equipment_variant": {
            "en": "operates equipment variant",
            "datatype": "wikibase-item",
        },
        "participant_role": {"en": "participant role", "datatype": "string"},
    }


def main() -> int:
    if OUTPUT_PATH.exists():
        raise SystemExit(
            "m1_projection_state.generated.json already exists; reset the spike before rerunning"
        )

    base_url = os.environ.get("WIKIBASE_URL", "http://localhost:8181")
    username = os.environ.get("MW_ADMIN_NAME", "")
    password = os.environ.get("MW_ADMIN_PASS", "")
    if not username or not password:
        raise SystemExit("MW_ADMIN_NAME and MW_ADMIN_PASS are required")

    api = WikibaseAPI(base_url, username, password)
    api.login()

    state: dict[str, dict[str, str]] = {"properties": {}}
    for key, definition in property_defs().items():
        created = api.create_property(
            labels={"en": definition["en"]},
            datatype=definition["datatype"],
        )
        state["properties"][key] = created.entity_id

    OUTPUT_PATH.write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"M1 projection vocabulary written to {OUTPUT_PATH.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
