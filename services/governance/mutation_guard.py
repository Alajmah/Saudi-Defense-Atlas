"""Backend-independent canonical mutation reconciliation for M1.

A proposal is complete only when every intended backend effect is demonstrably
equivalent. Ambiguous effects are never blindly retried. Backend inspection
failures become explicit unknown state rather than escaping the audit result.
Project Revision creation is permitted only after full proposal convergence.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

from .proposal_auth import validate_approval


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
    status: str  # not_attempted | already_applied | applied | failed | effect_unknown
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


def _inspect_or_unknown(
    *,
    backend: MutationBackend,
    key: str,
    mutation: Mapping[str, Any],
) -> EffectInspection:
    """Convert backend inspection failures into explicit, fail-closed uncertainty."""
    try:
        inspection = backend.inspect_effect(idempotency_key=key, mutation=mutation)
    except Exception as exc:  # noqa: BLE001 - backend read failure must remain auditable.
        return EffectInspection(
            "unknown",
            detail=f"inspection_error={type(exc).__name__}: {exc}",
        )
    if inspection.state not in {"absent", "equivalent", "conflict", "unknown"}:
        raise ValueError(f"backend returned invalid inspection state: {inspection.state}")
    return inspection


def _result_from_inspection(
    *, mutation: Mapping[str, Any], key: str, inspection: EffectInspection
) -> EffectResult:
    if inspection.state == "equivalent":
        status = "already_applied"
    elif inspection.state in {"conflict", "unknown"}:
        status = "effect_unknown"
    else:
        status = "not_attempted"
    return EffectResult(
        mutation_id=str(mutation["id"]),
        idempotency_key=key,
        status=status,
        write_attempted=False,
        receipt=inspection.receipt,
        detail=inspection.detail,
    )


def _remaining_results(
    preflight: list[tuple[Mapping[str, Any], str, EffectInspection]], start: int
) -> list[EffectResult]:
    return [
        _result_from_inspection(mutation=mutation, key=key, inspection=inspection)
        for mutation, key, inspection in preflight[start:]
    ]


def execute_authorized_proposal(
    *,
    proposal: Mapping[str, Any],
    decision: Mapping[str, Any],
    backend: MutationBackend,
) -> ProposalExecutionResult:
    """Converge an approved proposal without blind retries.

    The function performs a full preflight before any write. Existing equivalent
    effects are skipped. Any preflight conflict/unknown state blocks all new
    writes. During execution, each absent effect receives at most one write
    attempt. If a write outcome is ambiguous, the backend is inspected once;
    only observed equivalence is accepted as success. If inspection itself is
    unavailable, the result is explicit ``effect_unknown`` rather than an
    unstructured exception or retry.
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
        inspection = _inspect_or_unknown(
            backend=backend, key=key, mutation=mutation
        )
        preflight.append((mutation, key, inspection))

    if any(
        inspection.state in {"conflict", "unknown"}
        for _, _, inspection in preflight
    ):
        return ProposalExecutionResult(
            status="effect_unknown",
            proposal_sha256=proposal_digest,
            effects=tuple(
                _result_from_inspection(
                    mutation=mutation, key=key, inspection=inspection
                )
                for mutation, key, inspection in preflight
            ),
        )

    results: list[EffectResult] = []
    for index, (mutation, key, inspection) in enumerate(preflight):
        mutation_id = str(mutation["id"])
        if inspection.state == "equivalent":
            results.append(
                _result_from_inspection(
                    mutation=mutation, key=key, inspection=inspection
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
            results.extend(_remaining_results(preflight, index + 1))
            return ProposalExecutionResult(
                status="failed",
                proposal_sha256=proposal_digest,
                effects=tuple(results),
            )
        except AmbiguousWriteError as exc:
            reconciled = _inspect_or_unknown(
                backend=backend, key=key, mutation=mutation
            )
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
                    detail=f"{exc}; reconciliation={reconciled.state}; {reconciled.detail or ''}".rstrip(),
                )
            )
            results.extend(_remaining_results(preflight, index + 1))
            return ProposalExecutionResult(
                status="effect_unknown",
                proposal_sha256=proposal_digest,
                effects=tuple(results),
            )

        reconciled = _inspect_or_unknown(
            backend=backend, key=key, mutation=mutation
        )
        if reconciled.state != "equivalent":
            results.append(
                EffectResult(
                    mutation_id=mutation_id,
                    idempotency_key=key,
                    status="effect_unknown",
                    write_attempted=True,
                    receipt=write_receipt or reconciled.receipt,
                    detail=(
                        f"write returned but reconciliation={reconciled.state}; "
                        f"{reconciled.detail or ''}"
                    ).rstrip(),
                )
            )
            results.extend(_remaining_results(preflight, index + 1))
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
