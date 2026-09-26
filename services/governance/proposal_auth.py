"""Authorization checks for exact immutable ChangeProposal payloads."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Mapping


class AuthorizationError(ValueError):
    """Raised when a ReviewDecision does not authorize the exact proposal."""


def canonical_sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _parse_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def validate_approval(
    proposal: Mapping[str, Any], decision: Mapping[str, Any]
) -> str:
    """Validate policy, actor, identity, hash binding, and temporal ordering."""
    if decision.get("proposal_id") != proposal.get("id"):
        raise AuthorizationError("decision references a different proposal")

    digest = canonical_sha256(proposal)
    if str(decision.get("proposal_sha256", "")).lower() != digest:
        raise AuthorizationError("decision does not bind to exact proposal payload")
    if decision.get("decision") != "approve":
        raise AuthorizationError("canonical mutation requires an approve decision")

    outcome = proposal.get("policy_outcome")
    if outcome not in {"auto_admit_allowed", "human_review_required"}:
        raise AuthorizationError("proposal policy does not permit admission")

    risk = proposal.get("risk_class")
    actor = decision.get("decided_by") or {}
    actor_kind = actor.get("kind")
    if risk == "RED":
        raise AuthorizationError("RED proposals cannot be canonically applied")
    if risk == "AMBER" and actor_kind != "human":
        raise AuthorizationError("AMBER proposals require human approval")
    if actor_kind == "system" and not (
        risk == "GREEN" and outcome == "auto_admit_allowed"
    ):
        raise AuthorizationError("system approval is not authorized for this proposal")

    created_at = proposal.get("created_at")
    decided_at = decision.get("decided_at")
    if isinstance(created_at, str) and isinstance(decided_at, str):
        if _parse_datetime(decided_at) < _parse_datetime(created_at):
            raise AuthorizationError("decision predates proposal")

    return digest
