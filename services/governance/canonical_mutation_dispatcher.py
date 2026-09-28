"""Single-writer dispatch boundary for scaled M4 editorial operations.

Upstream monitoring, extraction, resolution, and review workers may run concurrently,
but canonical backend effects remain serialized through one project-owned coordination
lane. The dispatch envelope is audit metadata only; approval authority remains the
exact human ReviewDecision and canonical mutation semantics remain in the existing
mutation guard.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from .editorial_decision_binding import (
    validate_editorial_decision_binding,
    execute_editorial_authorized_proposal,
)
from .mutation_guard import MutationBackend, ProposalExecutionResult
from .proposal_auth import canonical_sha256


class CanonicalMutationDispatchError(ValueError):
    """Raised when dispatch identity, authority, or serialization is invalid."""


class SingleWriterCoordinator(Protocol):
    """Atomic exclusive-lane coordinator supplied by the deployment layer.

    A production implementation must make ``try_acquire`` atomic across every
    canonical mutation worker sharing the lane and retain exclusivity until
    ``release``. This module deliberately does not select Redis/PostgreSQL/etc.
    """

    name: str

    def try_acquire(
        self, *, serialization_key: str, dispatch_id: str, worker_id: str
    ) -> str | None: ...

    def release(
        self, *, token: str, dispatch_id: str, outcome: str
    ) -> None: ...


def _stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256(value: Any) -> str:
    return hashlib.sha256(_stable_json(value).encode("utf-8")).hexdigest()


def _stable_id(prefix: str, value: Any) -> str:
    return f"{prefix}-{_sha256(value)[:24].upper()}"


def _parse_datetime(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise CanonicalMutationDispatchError(f"{label} must be a date-time string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CanonicalMutationDispatchError(f"{label} must be ISO date-time") from exc
    if parsed.tzinfo is None:
        raise CanonicalMutationDispatchError(f"{label} must include timezone")
    return parsed.astimezone(timezone.utc)


def _normalized_utc(value: Any, label: str) -> str:
    return _parse_datetime(value, label).isoformat().replace("+00:00", "Z")


def _target_records(proposal: Mapping[str, Any]) -> list[dict[str, str]]:
    mutations = proposal.get("mutations")
    if not isinstance(mutations, Sequence) or isinstance(mutations, (str, bytes)) or not mutations:
        raise CanonicalMutationDispatchError("proposal requires non-empty mutations")

    targets: set[tuple[str, str]] = set()
    for mutation in mutations:
        if not isinstance(mutation, Mapping):
            raise CanonicalMutationDispatchError("proposal mutations must be objects")
        resource_type = mutation.get("resource_type")
        if resource_type not in {"entity", "claim", "event", "source", "document", "evidence"}:
            raise CanonicalMutationDispatchError("mutation has invalid resource_type")
        payload = mutation.get("payload")
        if not isinstance(payload, Mapping):
            raise CanonicalMutationDispatchError("mutation payload must be an object")
        payload_id = payload.get("id")
        if not isinstance(payload_id, str) or not payload_id:
            raise CanonicalMutationDispatchError("mutation payload requires canonical record id")
        targets.add((str(resource_type), payload_id))

        target_id = mutation.get("target_id")
        if target_id is not None:
            if not isinstance(target_id, str) or not target_id:
                raise CanonicalMutationDispatchError("mutation target_id must be canonical id")
            targets.add((str(resource_type), target_id))

    return [
        {"resource_type": resource_type, "record_id": record_id}
        for resource_type, record_id in sorted(targets)
    ]


def build_canonical_mutation_dispatch(
    *,
    review_packet: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    binding: Mapping[str, Any],
    enqueued_at: str,
) -> dict[str, Any]:
    """Build one immutable dispatch envelope for an exact approved editorial decision."""

    proposal_digest = validate_editorial_decision_binding(
        review_packet=review_packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
    )
    if decision.get("decision") != "approve":
        raise CanonicalMutationDispatchError(
            "only approved editorial decisions may enter canonical dispatch"
        )

    packet_id = review_packet.get("id")
    proposal_id = proposal.get("id")
    decision_id = decision.get("id")
    binding_id = binding.get("id")
    if not all(
        isinstance(value, str) and value
        for value in (packet_id, proposal_id, decision_id, binding_id)
    ):
        raise CanonicalMutationDispatchError("dispatch inputs require stable IDs")

    binding_time = _parse_datetime(binding.get("bound_at"), "binding bound_at")
    enqueued_time = _parse_datetime(enqueued_at, "dispatch enqueued_at")
    if enqueued_time < binding_time:
        raise CanonicalMutationDispatchError("dispatch cannot predate editorial decision binding")

    dispatch: dict[str, Any] = {
        "review_packet_id": packet_id,
        "review_packet_sha256": _sha256(review_packet),
        "proposal_id": proposal_id,
        "proposal_sha256": proposal_digest,
        "review_decision_id": decision_id,
        "review_decision_sha256": _sha256(decision),
        "editorial_decision_binding_id": binding_id,
        "editorial_decision_binding_sha256": _sha256(binding),
        "target_records": _target_records(proposal),
        "serialization_key": "canonical-global-single-writer",
        "enqueued_at": _normalized_utc(enqueued_at, "dispatch enqueued_at"),
        "authority": {
            "mode": "dispatch_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
    }
    dispatch["id"] = _stable_id("SDA-CANONICAL-DISPATCH", dispatch)
    return dispatch


def validate_canonical_mutation_dispatch(
    *,
    dispatch: Mapping[str, Any],
    review_packet: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    binding: Mapping[str, Any],
) -> None:
    """Fail closed unless the dispatch exactly matches all reviewed artifacts."""

    enqueued_at = dispatch.get("enqueued_at")
    expected = build_canonical_mutation_dispatch(
        review_packet=review_packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
        enqueued_at=str(enqueued_at) if isinstance(enqueued_at, str) else "",
    )
    if dict(dispatch) != expected:
        raise CanonicalMutationDispatchError(
            "canonical mutation dispatch does not match exact approved inputs"
        )


def execute_dispatched_editorial_proposal(
    *,
    dispatch: Mapping[str, Any],
    review_packet: Mapping[str, Any],
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    binding: Mapping[str, Any],
    backend: MutationBackend,
    coordinator: SingleWriterCoordinator,
    worker_id: str,
) -> ProposalExecutionResult:
    """Execute one exact approved proposal while holding the global writer lane."""

    validate_canonical_mutation_dispatch(
        dispatch=dispatch,
        review_packet=review_packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
    )
    if not isinstance(worker_id, str) or not worker_id:
        raise CanonicalMutationDispatchError("canonical dispatcher worker_id is required")

    dispatch_id = str(dispatch["id"])
    serialization_key = str(dispatch["serialization_key"])
    token = coordinator.try_acquire(
        serialization_key=serialization_key,
        dispatch_id=dispatch_id,
        worker_id=worker_id,
    )
    if not isinstance(token, str) or not token:
        raise CanonicalMutationDispatchError(
            "canonical single-writer lane is already held; no backend inspection/write attempted"
        )

    outcome = "error"
    try:
        execution = execute_editorial_authorized_proposal(
            review_packet=review_packet,
            proposal=proposal,
            decision=decision,
            binding=binding,
            backend=backend,
        )
        outcome = execution.status
        return execution
    finally:
        coordinator.release(token=token, dispatch_id=dispatch_id, outcome=outcome)


__all__ = [
    "CanonicalMutationDispatchError",
    "SingleWriterCoordinator",
    "build_canonical_mutation_dispatch",
    "validate_canonical_mutation_dispatch",
    "execute_dispatched_editorial_proposal",
]
