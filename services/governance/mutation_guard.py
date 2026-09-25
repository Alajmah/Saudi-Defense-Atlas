"""Backend-independent canonical mutation reconciliation for M1.

A proposal is complete only when every intended backend effect is demonstrably
equivalent. Ambiguous effects are never blindly retried. Project Revision
creation is permitted only after full proposal convergence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .proposal_auth import canonical_sha256, validate_approval


class DefinitiveWriteError(RuntimeError):
    """Backend definitively rejected the requested effect."""


class AmbiguousWriteError(RuntimeError):
    """Backend write may or may not have taken effect."""


@dataclass(frozen=True)
class EffectInspection:
    state: str  # absent | equivalent | conflict | unknown
    receipt: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class EffectResult:
    mutation_id: str
    idempotency_key: str
    status: str  # already_applied | applied | failed | effect_unknown
    write_attempted: bool
    receipt: str | None = None
    detail: str | None = None


@dataclass(frozen=True)
class ProposalExecutionResult:
    status: str  # converged | failed | effect_unknown
    proposal_sha256: str
    effects: tuple[EffectResult, ...]

    @property
    def may_create_revision(self) -> bool:
        return self.status == "converged"


class MutationBackend(Protocol):
    name: str

    def inspect_effect(
        self, *, idempotency_key: str, mutation: Mapping[str, Any]
    ) -> EffectInspection: ...

    def apply_effect(
        self, *, idempotency_key: str, mutation: Mapping[str, Any]
    ) -> str | None: ...


def _canonical(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def effect_idempotency_key(
    *,
    backend_name: str,
    proposal_id: str,
    proposal_sha256: str,
    mutation: Mapping[str, Any],
) -> str:
    """Bind one backend effect to the exact reviewed proposal and mutation payload."""
    seed = {
        "backend": backend_name,
        "proposal_id": proposal_id,
        "proposal_sha256": proposal_sha256,
        "mutation_id": mutation.get("id"),
        "action": mutation.get("action"),
        "resource_type": mutation.get("resource_type"),
        "target_id": mutation.get("target_id"),
        "payload_sha256": hashlib.sha256(
            _canonical(mutation.get("payload") or {})
        ).hexdigest(),
    }
    return hashlib.sha256(_canonical(seed)).hexdigest()


def _find_mutations(proposal: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    mutations = proposal.get("mutations")
    if not isinstance(mutations, list) or not mutations:
        raise ValueError("proposal must contain mutations")
    seen: set[str] = set()
    result: list[Mapping[str, Any]] = []
    for mutation in mutations:
        if not isinstance(mutation, Mapping):
            raise ValueError("proposal mutation must be an object")
        mutation_id = mutation.get("id")
        if not isinstance(mutation_id, str) or not mutation_id:
            raise ValueError("proposal mutation requires an ID")
        if mutation_id in seen:
            raise ValueError(f"duplicate mutation ID: {mutation_id}")
        seen.add(mutation_id)
        result.append(mutation)
    return result


def execute_authorized_proposal(
    *,
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    backend: MutationBackend,
) -> ProposalExecutionResult:
    """Converge an approved proposal without blind retries.

    The function performs a full preflight before any write. Existing equivalent
    effects are skipped. Any preflight conflict/unknown state blocks new writes.
    During execution, each absent effect receives at most one write attempt. If a
    write outcome is ambiguous, the backend is inspected once; only observed
    equivalence is accepted as success.
    """
    proposal_digest = validate_approval(proposal, decision)
    proposal_id = str(proposal["id"])
    mutations = _find_mutations(proposal)

    preflight: list[tuple[Mapping[str, Any], str, EffectInspection]] = []
    for mutation in mutations:
        key = effect_idempotency_key(
            backend_name=backend.name,
            proposal_id=proposal_id,
            proposal_sha256=proposal_digest,
            mutation=mutation,
        )
        inspection = backend.inspect_effect(idempotency_key=key, mutation=mutation)
        if inspection.state not in {"absent", "equivalent", "conflict", "unknown"}:
            raise ValueError(f"backend returned invalid inspection state: {inspection.state}")
        preflight.append((mutation, key, inspection))

    blockers = [entry for entry in preflight if entry[2].state in {"conflict", "unknown"}]
    if blockers:
        effects = tuple(
            EffectResult(
                mutation_id=str(mutation["id"]),
                idempotency_key=key,
                status=(
                    "already_applied"
                    if inspection.state == "equivalent"
                    else "effect_unknown"
                    if inspection.state in {"conflict", "unknown"}
                    else "failed"
                ),
                write_attempted=False,
                receipt=inspection.receipt,
                detail=inspection.detail,
            )
            for mutation, key, inspection in preflight
        )
        return ProposalExecutionResult(
            status="effect_unknown",
            proposal_sha256=proposal_digest,
            effects=effects,
        )

    results: list[EffectResult] = []
    for mutation, key, inspection in preflight:
        mutation_id = str(mutation["id"])
        if inspection.state == "equivalent":
            results.append(
                EffectResult(
                    mutation_id=mutation_id,
                    idempotency_key=key,
                    status="already_applied",
                    write_attempted=False,
                    receipt=inspection.receipt,
                    detail=inspection.detail,
                )
            )
            continue

        try:
            write_receipt = backend.apply_effect(idempotency_key=key, mutation=mutation)
        except DefinitiveWriteError as exc:
            results.append(
                EffectResult(
                    mutation_id=mutation_id,
                    idempotency_key=key,
                    status="failed",
                    write_attempted=True,
                    detail=str(exc),
                )
            )
            return ProposalExecutionResult(
                status="failed",
                proposal_sha256=proposal_digest,
                effects=tuple(results),
            )
        except AmbiguousWriteError as exc:
            reconciled = backend.inspect_effect(idempotency_key=key, mutation=mutation)
            if reconciled.state == "equivalent":
                results.append(
                    EffectResult(
                        mutation_id=mutation_id,
                        idempotency_key=key,
                        status="applied",
                        write_attempted=True,
                        receipt=reconciled.receipt,
                        detail="ambiguous write reconciled as equivalent",
                    )
                )
                continue
            results.append(
                EffectResult(
                    mutation_id=mutation_id,
                    idempotency_key=key,
                    status="effect_unknown",
                    write_attempted=True,
                    receipt=reconciled.receipt,
                    detail=f"{exc}; reconciliation={reconciled.state}",
                )
            )
            return ProposalExecutionResult(
                status="effect_unknown",
                proposal_sha256=proposal_digest,
                effects=tuple(results),
            )

        reconciled = backend.inspect_effect(idempotency_key=key, mutation=mutation)
        if reconciled.state != "equivalent":
            results.append(
                EffectResult(
                    mutation_id=mutation_id,
                    idempotency_key=key,
                    status="effect_unknown",
                    write_attempted=True,
                    receipt=write_receipt or reconciled.receipt,
                    detail=f"write returned but reconciliation={reconciled.state}",
                )
            )
            return ProposalExecutionResult(
                status="effect_unknown",
                proposal_sha256=proposal_digest,
                effects=tuple(results),
            )

        results.append(
            EffectResult(
                mutation_id=mutation_id,
                idempotency_key=key,
                status="applied",
                write_attempted=True,
                receipt=write_receipt or reconciled.receipt,
            )
        )

    return ProposalExecutionResult(
        status="converged",
        proposal_sha256=proposal_digest,
        effects=tuple(results),
    )
