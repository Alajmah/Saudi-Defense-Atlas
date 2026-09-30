"""Public deterministic M4 resolver/verifier boundary.

The unified v0.4 semantics live in ``_resolver_verifier_core``: the reviewed
proposal semantics (originally v0.2), the ambiguity-preservation audit
correction (originally the v0.3 public postprocessing, moved in-core so both
paths are behaviorally identical), and the reconciled manufacturer predicate
target types (equipment or equipment_variant). This boundary is the public
entry point and identity stamp; it computes exactly what the core computes.
One resolver version implies one resolution payload for one extraction.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from ._resolver_verifier_core import (
    ResolverVerifierError,
    build_resolution_verification as _build_core_resolution_verification,
)

_PUBLIC_RESOLVER_VERSION = "resolver-verifier-v0.4"


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"







def build_resolution_verification(
    *,
    extraction_run: Mapping[str, Any],
    canonical_entities: Sequence[Mapping[str, Any]],
    canonical_claims: Sequence[Mapping[str, Any]],
    canonical_events: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """Resolve candidates while preserving ambiguous vs unresolved audit semantics."""

    run, proposal = _build_core_resolution_verification(
        extraction_run=extraction_run,
        canonical_entities=canonical_entities,
        canonical_claims=canonical_claims,
        canonical_events=canonical_events,
    )

    extraction_id = run.get("extraction_run_id")
    if not isinstance(extraction_id, str) or not extraction_id:
        raise ResolverVerifierError("resolution run requires extraction_run_id")
    run["resolver_version"] = _PUBLIC_RESOLVER_VERSION
    run["id"] = _stable_id("SDA-AIRV", extraction_id, _PUBLIC_RESOLVER_VERSION)
    return run, proposal


__all__ = ["ResolverVerifierError", "build_resolution_verification"]
