"""Bind M4 human editorial decisions to the existing canonical mutation guard.

The binding is operational audit metadata only. It proves which exact review
packet and ChangeProposal a human ReviewDecision referred to, while the existing
M1 proposal authorization and mutation guard remain the canonical write boundary.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from .mutation_guard import MutationBackend, ProposalExecutionResult, execute_authorized_proposal
from .proposal_auth import canonical_sha256


class EditorialDecisionBindingError(ValueError):
    """Raised when a review decision is not bound to the exact editorial context."""


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, *parts: Any) -> str:
    digest = hashlib.sha256(_stable_json(parts).encode("utf-8")).hexdigest()[:24].upper()
    return f"{prefix}-{digest}"


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise EditorialDecisionBindingError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise EditorialDecisionBindingError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise EditorialDecisionBindingError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _normalized_utc(value: Any, label: str) -> str:
    return _parse_datetime(value, label).isoformat().replace("+00:00", "Z")


def _validate_packet_identity(review_packet: Mapping[str, Any]) -> str:
    packet_id = review_packet.get("id")
    if not isinstance(packet_id, str) or not packet_id:
        raise EditorialDecisionBindingError("review packet requires ID")
    packet_without_id = {key: value for key, value in review_packet.items() if key != "id"}
    expected_id = _stable_id("SDA-REVIEW-PACKET", packet_without_id)
    if packet_id != expected_id:
        raise EditorialDecisionBindingError("review packet ID is not bound to its final content")
    if review_packet.get("review_state") != "awaiting_human":
        raise EditorialDecisionBindingError("decision binding requires awaiting_human review packet")
    if review_packet.get("risk_class") != "AMBER":
        raise EditorialDecisionBindingError("editorial decision binding requires AMBER review packet")
    authority = review_packet.get("authority")
    expected_authority = {
        "mode": "review_handoff_only",
        "approval_authority": False,
        "canonical_mutation_authority": False,
        "publication_authority": False,
    }
    if authority != expected_authority:
        raise EditorialDecisionBindingError("review packet authority boundary is invalid")
    return packet_id


def build_editorial_decision_binding(
    *,
    review_packet: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    bound_at: str,
) -> dict[str, Any]:
    """Create an immutable audit binding for one human editorial decision."""

    packet_id = _validate_packet_identity(review_packet)
    proposal_id = proposal.get("id")
    decision_id = decision.get("id")
    if not isinstance(proposal_id, str) or not proposal_id:
        raise EditorialDecisionBindingError("proposal requires ID")
    if not isinstance(decision_id, str) or not decision_id:
        raise EditorialDecisionBindingError("ReviewDecision requires ID")

    proposal_digest = canonical_sha256(proposal)
    if review_packet.get("proposal_id") != proposal_id:
        raise EditorialDecisionBindingError("review packet references a different proposal")
    if str(review_packet.get("proposal_sha256", "")).lower() != proposal_digest:
        raise EditorialDecisionBindingError("review packet does not bind exact proposal payload")
    if decision.get("proposal_id") != proposal_id:
        raise EditorialDecisionBindingError("ReviewDecision references a different proposal")
    if str(decision.get("proposal_sha256", "")).lower() != proposal_digest:
        raise EditorialDecisionBindingError("ReviewDecision does not bind exact proposal payload")

    disposition = decision.get("decision")
    if disposition not in {"approve", "reject", "return_for_revision"}:
        raise EditorialDecisionBindingError("ReviewDecision has invalid disposition")
    actor = decision.get("decided_by")
    if not isinstance(actor, Mapping) or actor.get("kind") != "human":
        raise EditorialDecisionBindingError("M4 editorial decisions require a human reviewer")
    actor_id = actor.get("id")
    if not isinstance(actor_id, str) or not actor_id:
        raise EditorialDecisionBindingError("human reviewer requires actor ID")

    packet_created = _parse_datetime(review_packet.get("created_at"), "review packet created_at")
    proposal_created = _parse_datetime(proposal.get("created_at"), "proposal created_at")
    decided_at_dt = _parse_datetime(decision.get("decided_at"), "decision decided_at")
    bound_at_dt = _parse_datetime(bound_at, "binding bound_at")
    if decided_at_dt < max(packet_created, proposal_created):
        raise EditorialDecisionBindingError("ReviewDecision predates the reviewed packet/proposal")
    if bound_at_dt < decided_at_dt:
        raise EditorialDecisionBindingError("decision binding predates ReviewDecision")

    binding: dict[str, Any] = {
        "review_packet_id": packet_id,
        "review_packet_sha256": _sha256(review_packet),
        "proposal_id": proposal_id,
        "proposal_sha256": proposal_digest,
        "review_decision_id": decision_id,
        "review_decision_sha256": _sha256(decision),
        "decision": disposition,
        "decided_at": _normalized_utc(decision.get("decided_at"), "decision decided_at"),
        "decided_by": dict(actor),
        "bound_at": _normalized_utc(bound_at, "binding bound_at"),
        "authority": {
            "mode": "decision_binding_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }
    binding["id"] = _stable_id("SDA-EDITORIAL-DECISION", binding)
    return binding


def validate_editorial_decision_binding(
    *,
    review_packet: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> str:
    """Validate an existing binding and return the exact proposal SHA-256."""

    bound_at = binding.get("bound_at")
    expected = build_editorial_decision_binding(
        review_packet=review_packet,
        proposal=proposal,
        decision=decision,
        bound_at=str(bound_at) if isinstance(bound_at, str) else "",
    )
    if dict(binding) != expected:
        raise EditorialDecisionBindingError("editorial decision binding does not match exact inputs")
    return expected["proposal_sha256"]


def execute_editorial_authorized_proposal(
    *,
    review_packet: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    binding: Mapping[str, Any],
    backend: MutationBackend,
) -> ProposalExecutionResult:
    """Execute only an exact human-approved packet through the existing mutation guard."""

    validate_editorial_decision_binding(
        review_packet=review_packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
    )
    if decision.get("decision") != "approve":
        raise EditorialDecisionBindingError(
            "reject/return_for_revision decisions cannot enter canonical execution"
        )
    return execute_authorized_proposal(
        proposal=proposal,
        decision=decision,
        backend=backend,
    )


__all__ = [
    "EditorialDecisionBindingError",
    "build_editorial_decision_binding",
    "validate_editorial_decision_binding",
    "execute_editorial_authorized_proposal",
]
