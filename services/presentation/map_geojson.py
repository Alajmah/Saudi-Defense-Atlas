"""Deterministic renderer adapter for the approved M3 PublicMapView boundary.

The adapter deliberately accepts only the already-coarsened public map projection.
It does not read canonical geography, Claims, Events, or backend identifiers.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any

from .projection_support import ProjectionError

_SCOPE = "public_non_operational_fixed_facilities"
_BACKEND_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])")
_ALLOWED_CATEGORIES = {
    "air_base",
    "naval_base",
    "military_city",
    "training_center",
    "military_education",
    "defense_industry_facility",
    "administrative_facility",
}


def _assert_no_backend_ids(value: Any) -> None:
    if _BACKEND_ID_RE.search(repr(value)):
        raise ProjectionError("backend Q/P identifier leaked into map renderer payload")


def _localized_text(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping) or not value:
        raise ProjectionError(f"{label} requires localized text")
    rendered: dict[str, str] = {}
    for locale in ("ar", "en"):
        item = value.get(locale)
        if item is None:
            continue
        if not isinstance(item, str) or not item:
            raise ProjectionError(f"{label}.{locale} must be non-empty text")
        rendered[locale] = item
    if not rendered:
        raise ProjectionError(f"{label} requires ar or en text")
    return rendered


def _citations(value: Any, feature_id: str) -> list[dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        raise ProjectionError(f"map feature {feature_id} requires citations")
    rendered: list[dict[str, Any]] = []
    for raw in value:
        if not isinstance(raw, Mapping):
            raise ProjectionError(f"map feature {feature_id} citation must be an object")
        if raw.get("evidence_role") != "supports":
            continue
        evidence_id = raw.get("evidence_id")
        source_id = raw.get("source_id")
        document_id = raw.get("document_id")
        if not all(isinstance(item, str) and item for item in (evidence_id, source_id, document_id)):
            raise ProjectionError(f"map feature {feature_id} citation identity is incomplete")
        rendered.append(
            {
                "evidence_id": evidence_id,
                "document_id": document_id,
                "source_id": source_id,
                "url": raw.get("url") if isinstance(raw.get("url"), str) else None,
            }
        )
    if not rendered:
        raise ProjectionError(f"map feature {feature_id} requires supporting Evidence")
    rendered.sort(key=lambda item: (item["evidence_id"], item["document_id"], item["source_id"]))
    return rendered


def build_map_renderer_payload(public_map_view: Mapping[str, Any]) -> dict[str, Any]:
    """Build deterministic GeoJSON + semantic fallback from PublicMapView only."""

    if not isinstance(public_map_view, Mapping):
        raise ProjectionError("public map view must be an object")
    if public_map_view.get("scope") != _SCOPE:
        raise ProjectionError("map renderer accepts only the public non-operational facility scope")
    features = public_map_view.get("features")
    if not isinstance(features, Sequence) or isinstance(features, (str, bytes)):
        raise ProjectionError("public map features must be an array")

    geo_features: list[dict[str, Any]] = []
    fallback_items: list[dict[str, Any]] = []
    seen_feature_ids: set[str] = set()

    for raw in sorted(features, key=lambda item: str(item.get("id")) if isinstance(item, Mapping) else ""):
        if not isinstance(raw, Mapping):
            raise ProjectionError("public map feature must be an object")
        feature_id = raw.get("id")
        entity_id = raw.get("entity_id")
        if not isinstance(feature_id, str) or not feature_id:
            raise ProjectionError("public map feature requires id")
        if feature_id in seen_feature_ids:
            raise ProjectionError(f"duplicate public map feature id: {feature_id}")
        seen_feature_ids.add(feature_id)
        if not isinstance(entity_id, str) or not entity_id:
            raise ProjectionError(f"map feature {feature_id} requires entity_id")
        if raw.get("entity_type") != "facility":
            raise ProjectionError(f"map feature {feature_id} must reference a facility")
        category = raw.get("category")
        if category not in _ALLOWED_CATEGORIES:
            raise ProjectionError(f"map feature {feature_id} has non-public category")

        names = _localized_text(raw.get("names"), f"{feature_id}.names")
        location_label_raw = raw.get("location_label")
        location_label = (
            None
            if location_label_raw is None
            else _localized_text(location_label_raw, f"{feature_id}.location_label")
        )

        coordinate = raw.get("coordinate")
        if not isinstance(coordinate, Mapping):
            raise ProjectionError(f"map feature {feature_id} requires public coordinate")
        if coordinate.get("precision_class") != "coarsened_2dp":
            raise ProjectionError(f"map feature {feature_id} requires coarsened_2dp coordinate")
        if coordinate.get("publication_policy") != "fixed_public_reference_only":
            raise ProjectionError(f"map feature {feature_id} has invalid publication policy")
        latitude = coordinate.get("latitude")
        longitude = coordinate.get("longitude")
        if isinstance(latitude, bool) or not isinstance(latitude, (int, float)):
            raise ProjectionError(f"map feature {feature_id} latitude is invalid")
        if isinstance(longitude, bool) or not isinstance(longitude, (int, float)):
            raise ProjectionError(f"map feature {feature_id} longitude is invalid")
        if not -90 <= float(latitude) <= 90 or not -180 <= float(longitude) <= 180:
            raise ProjectionError(f"map feature {feature_id} coordinate is out of range")
        if round(float(latitude), 2) != float(latitude) or round(float(longitude), 2) != float(longitude):
            raise ProjectionError(f"map feature {feature_id} exceeds public 2dp precision")

        citations = _citations(raw.get("citations"), feature_id)
        organizations = raw.get("associated_organization_ids", [])
        if not isinstance(organizations, Sequence) or isinstance(organizations, (str, bytes)):
            raise ProjectionError(f"map feature {feature_id} organization IDs must be an array")
        organization_ids = sorted({str(item) for item in organizations if isinstance(item, str) and item})

        geo_features.append(
            {
                "type": "Feature",
                "id": feature_id,
                "geometry": {
                    "type": "Point",
                    "coordinates": [float(longitude), float(latitude)],
                },
                "properties": {
                    "entity_id": entity_id,
                    "category": category,
                    "name_ar": names.get("ar"),
                    "name_en": names.get("en"),
                    "location_ar": None if location_label is None else location_label.get("ar"),
                    "location_en": None if location_label is None else location_label.get("en"),
                    "associated_organization_ids": organization_ids,
                },
            }
        )
        fallback_items.append(
            {
                "feature_id": feature_id,
                "entity_id": entity_id,
                "category": category,
                "names": names,
                "location_label": location_label,
                "coordinate": {"latitude": float(latitude), "longitude": float(longitude)},
                "citations": citations,
            }
        )

    payload = {
        "renderer_contract": "sda-public-map-v0.1",
        "scope": _SCOPE,
        "geojson": {"type": "FeatureCollection", "features": geo_features},
        "fallback_items": fallback_items,
        "provenance": dict(public_map_view.get("provenance", {}))
        if isinstance(public_map_view.get("provenance"), Mapping)
        else {},
    }
    _assert_no_backend_ids(payload)
    return payload
