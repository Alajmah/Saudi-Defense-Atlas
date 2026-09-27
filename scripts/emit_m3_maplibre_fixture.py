#!/usr/bin/env python3
"""Emit a synthetic PublicMapView-derived renderer payload for the MapLibre trial."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.presentation.map_geojson import build_map_renderer_payload  # noqa: E402


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "spikes/maplibre/trial-data.json"
    public_map_view = {
        "scope": "public_non_operational_fixed_facilities",
        "projected_at": "2026-09-27T00:00:00Z",
        "features": [
            {
                "id": "SDA-MAP-FAC-TRIAL-RIYADH",
                "entity_id": "SDA-FAC-TRIAL-RIYADH",
                "entity_type": "facility",
                "category": "training_center",
                "names": {"ar": "منشأة تدريب تجريبية", "en": "Trial Training Facility"},
                "location_label": {"ar": "منطقة الرياض", "en": "Riyadh area"},
                "coordinate": {
                    "latitude": 24.71,
                    "longitude": 46.68,
                    "precision_class": "coarsened_2dp",
                    "publication_policy": "fixed_public_reference_only",
                },
                "coordinate_claim_ids": ["SDA-CLAIM-TRIAL-LAT", "SDA-CLAIM-TRIAL-LON"],
                "associated_organization_ids": ["SDA-ORG-TRIAL"],
                "citations": [
                    {
                        "evidence_id": "SDA-EVID-TRIAL-MAP",
                        "evidence_role": "supports",
                        "document_id": "SDA-DOC-TRIAL-MAP",
                        "source_id": "SDA-SOURCE-TRIAL-MAP",
                        "source_class": "A",
                        "publisher": {"en": "Synthetic Official Fixture"},
                        "document_title": {"en": "Synthetic Public Location Fixture"},
                        "url": "https://example.invalid/sda-map-trial",
                        "published_at": {"value": "2026-09-01", "precision": "day"},
                        "retrieved_at": "2026-09-02T00:00:00Z",
                        "locator": {"section": "public location"},
                    }
                ],
            }
        ],
        "provenance": {
            "record_ids": [
                "SDA-FAC-TRIAL-RIYADH",
                "SDA-CLAIM-TRIAL-LAT",
                "SDA-CLAIM-TRIAL-LON",
                "SDA-EVID-TRIAL-MAP",
                "SDA-DOC-TRIAL-MAP",
                "SDA-SOURCE-TRIAL-MAP",
            ],
            "revision_ids": ["SDA-REV-TRIAL-MAP"],
        },
    }
    payload = build_map_renderer_payload(public_map_view)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
