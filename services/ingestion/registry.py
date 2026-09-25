"""Load source-specific acquisition policy from the checked-in registry."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .document_identity import (
    IngestionContractError,
    SourceAcquisitionPolicy,
    validate_policy,
)

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REGISTRY_PATH = Path(__file__).with_name("registered_documents.json")

_REQUIRED_FIELDS = {
    "source_id",
    "document_key",
    "canonical_url",
    "allowed_hosts",
    "language",
    "document_type",
}
_ALLOWED_FIELDS = _REQUIRED_FIELDS | {"publisher_document_id", "expected_title"}


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> dict[str, dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise IngestionContractError("document registry must be a JSON object")
    return data


def load_registered_document(
    key: str, path: Path = DEFAULT_REGISTRY_PATH
) -> tuple[SourceAcquisitionPolicy, dict[str, Any]]:
    registry = load_registry(path)
    if key not in registry:
        raise IngestionContractError(f"unknown registered document key: {key}")

    raw = registry[key]
    if not isinstance(raw, dict):
        raise IngestionContractError(f"registry entry {key} must be an object")

    missing = sorted(_REQUIRED_FIELDS - raw.keys())
    extra = sorted(raw.keys() - _ALLOWED_FIELDS)
    if missing:
        raise IngestionContractError(
            f"registry entry {key} is missing fields: {', '.join(missing)}"
        )
    if extra:
        raise IngestionContractError(
            f"registry entry {key} has unsupported fields: {', '.join(extra)}"
        )

    allowed_hosts = raw["allowed_hosts"]
    if not isinstance(allowed_hosts, list) or not all(
        isinstance(item, str) and item for item in allowed_hosts
    ):
        raise IngestionContractError("allowed_hosts must be a non-empty string array")

    policy = SourceAcquisitionPolicy(
        source_id=str(raw["source_id"]),
        document_key=str(raw["document_key"]),
        canonical_url=str(raw["canonical_url"]),
        allowed_hosts=tuple(allowed_hosts),
        language=str(raw["language"]),
        document_type=str(raw["document_type"]),
        publisher_document_id=(
            None
            if raw.get("publisher_document_id") is None
            else str(raw["publisher_document_id"])
        ),
    )
    validate_policy(policy)
    return policy, dict(raw)
