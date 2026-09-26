"""Construct one project Revision after a fully converged approved proposal."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .mutation_guard import ProposalExecutionResult
from .proposal_auth import validate_approval


class RevisionBuildError(ValueError):
    """Raised when execution evidence is insufficient for a project Revision."""


_ACTION_MAP = {
    "create": "created",
    "supersede": "superseded",
    "merge": "merged",
    "metadata_update": "metadata_updated",
}


def _canonical_sha256(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _revision_id(body: Mapping[str, Any]) -> str:
    """Derive Revision identity from the exact canonical Revision body."""
    suffix = _canonical_sha256(body)[:24].upper()
    return f"SDA-REVISION-{suffix}"


def build_revision(
    *,
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    execution: ProposalExecutionResult,
    backend_name: str,
    applied_at: str,
    adapter_id: str,
) -> dict[str, Any]:
    """Build a Revision only for a converged execution that applied new effects."""
    proposal_digest = validate_approval(proposal, decision)
    if execution.proposal_sha256 != proposal_digest:
        raise RevisionBuildError("execution evidence belongs to a different proposal payload")
    if not execution.may_create_revision:
        raise RevisionBuildError(
            f"proposal execution is {execution.status}; project Revision is forbidden"
        )
    if not any(effect.status == "applied" for effect in execution.effects):
        raise RevisionBuildError(
            "execution is a pure replay; reuse or recover the existing project Revision"
        )

    mutations = proposal.get("mutations")
    if not isinstance(mutations, list) or len(mutations) != len(execution.effects):
        raise RevisionBuildError("execution does not account for every proposal mutation")

    effect_by_id = {effect.mutation_id: effect for effect in execution.effects}
    if len(effect_by_id) != len(execution.effects):
        raise RevisionBuildError("execution contains duplicate mutation results")

    affected_records: list[dict[str, Any]] = []
    receipts: list[dict[str, str]] = []
    for mutation in mutations:
        mutation_id = str(mutation["id"])
        effect = effect_by_id.get(mutation_id)
        if effect is None:
            raise RevisionBuildError(f"missing execution result for {mutation_id}")
        if effect.status not in {"applied", "already_applied"}:
            raise RevisionBuildError(
                f"mutation {mutation_id} is not converged: {effect.status}"
            )

        payload = mutation.get("payload")
        if not isinstance(payload, Mapping) or not isinstance(payload.get("id"), str):
            raise RevisionBuildError(f"mutation {mutation_id} payload requires canonical id")
        action = _ACTION_MAP.get(str(mutation.get("action")))
        if action is None:
            raise RevisionBuildError(f"unsupported revision action for {mutation_id}")

        affected_records.append(
            {
                "resource_type": str(mutation["resource_type"]),
                "record_id": str(payload["id"]),
                "action": action,
                "payload_sha256": _canonical_sha256(payload),
            }
        )
        if effect.receipt:
            receipts.append(
                {
                    "backend": backend_name,
                    "receipt": (
                        f"mutation={mutation_id};idempotency={effect.idempotency_key};"
                        f"receipt={effect.receipt}"
                    ),
                }
            )

    body = {
        "proposal_id": str(proposal["id"]),
        "decision_id": str(decision["id"]),
        "parent_revision_ids": [],
        "applied_at": applied_at,
        "applied_by": {"kind": "system", "id": adapter_id},
        "affected_records": affected_records,
        "backend_receipts": receipts,
        "rationale": (
            "Project Revision created only after at least one proposal effect was newly "
            "applied and every intended effect was observed as equivalent in the "
            "canonical backend."
        ),
    }
    return {"id": _revision_id(body), **body}
