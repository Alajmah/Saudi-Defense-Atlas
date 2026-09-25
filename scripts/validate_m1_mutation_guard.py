#!/usr/bin/env python3
"""Validate backend-independent M1 mutation convergence semantics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.governance.mutation_guard import (  # noqa: E402
    AmbiguousWriteError,
    DefinitiveWriteError,
    EffectInspection,
    execute_authorized_proposal,
)
from services.governance.proposal_auth import (  # noqa: E402
    AuthorizationError,
    canonical_sha256,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def proposal_fixture() -> dict:
    return {
        "id": "SDA-PROPOSAL-M1-MUTATION-GUARD-TEST",
        "created_at": "2026-01-01T00:00:00Z",
        "risk_class": "AMBER",
        "policy_outcome": "human_review_required",
        "mutations": [
            {
                "id": "SDA-MUT-TEST-001",
                "action": "create",
                "resource_type": "source",
                "payload": {"id": "SDA-SOURCE-TEST-001", "value": "alpha"},
            },
            {
                "id": "SDA-MUT-TEST-002",
                "action": "create",
                "resource_type": "document",
                "payload": {"id": "SDA-DOC-TEST-001", "value": "beta"},
            },
            {
                "id": "SDA-MUT-TEST-003",
                "action": "create",
                "resource_type": "evidence",
                "payload": {"id": "SDA-EVID-TEST-001", "value": "gamma"},
            },
        ],
    }


def approval_for(proposal: dict) -> dict:
    return {
        "id": "SDA-DECISION-M1-MUTATION-GUARD-TEST",
        "proposal_id": proposal["id"],
        "proposal_sha256": canonical_sha256(proposal),
        "decision": "approve",
        "decided_at": "2026-01-01T00:01:00Z",
        "decided_by": {"kind": "human", "id": "test-editor"},
    }


class FakeBackend:
    name = "fake-m1-backend"

    def __init__(self, behavior: dict[str, str] | None = None) -> None:
        self.behavior = behavior or {}
        self.state: dict[str, str] = {}
        self.apply_calls: list[str] = []

    def inspect_effect(self, *, idempotency_key: str, mutation: dict) -> EffectInspection:
        mutation_id = mutation["id"]
        mode = self.behavior.get(mutation_id)
        if mode == "preflight_unknown" and mutation_id not in self.apply_calls:
            return EffectInspection("unknown", detail="synthetic preflight uncertainty")
        if mode == "preflight_conflict" and mutation_id not in self.apply_calls:
            return EffectInspection("conflict", detail="synthetic conflict")
        if self.state.get(idempotency_key) == "equivalent":
            return EffectInspection(
                "equivalent", receipt=f"receipt:{mutation_id}"
            )
        return EffectInspection("absent")

    def apply_effect(self, *, idempotency_key: str, mutation: dict) -> str | None:
        mutation_id = mutation["id"]
        self.apply_calls.append(mutation_id)
        mode = self.behavior.get(mutation_id)
        if mode == "definitive_failure":
            raise DefinitiveWriteError("synthetic definitive rejection")
        if mode == "ambiguous_applied":
            self.state[idempotency_key] = "equivalent"
            raise AmbiguousWriteError("synthetic timeout after effect")
        if mode == "ambiguous_unproven":
            raise AmbiguousWriteError("synthetic timeout with no observable effect")
        self.state[idempotency_key] = "equivalent"
        return f"write:{mutation_id}"


def main() -> int:
    failures: list[str] = []
    proposal = proposal_fixture()
    decision = approval_for(proposal)

    happy = FakeBackend()
    first = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=happy
    )
    expect(first.status == "converged", "happy path must converge", failures)
    expect(first.may_create_revision, "converged proposal may create Revision", failures)
    expect(
        [effect.status for effect in first.effects] == ["applied", "applied", "applied"],
        "happy path must apply every absent mutation",
        failures,
    )
    expect(len(happy.apply_calls) == 3, "happy path must attempt each mutation once", failures)

    replay = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=happy
    )
    expect(replay.status == "converged", "equivalent replay must converge", failures)
    expect(
        [effect.status for effect in replay.effects]
        == ["already_applied", "already_applied", "already_applied"],
        "replay must detect equivalent effects",
        failures,
    )
    expect(
        len(happy.apply_calls) == 3,
        "equivalent replay must not issue additional writes",
        failures,
    )

    blocked = FakeBackend({"SDA-MUT-TEST-002": "preflight_unknown"})
    blocked_result = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=blocked
    )
    expect(blocked_result.status == "effect_unknown", "preflight unknown must block proposal", failures)
    expect(not blocked.apply_calls, "preflight blocker must prevent all new writes", failures)
    expect(
        [effect.status for effect in blocked_result.effects]
        == ["not_attempted", "effect_unknown", "not_attempted"],
        "preflight result must account for blocked and untouched mutations",
        failures,
    )

    ambiguous_applied = FakeBackend({"SDA-MUT-TEST-001": "ambiguous_applied"})
    reconciled = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=ambiguous_applied
    )
    expect(
        reconciled.status == "converged",
        "ambiguous write observed as equivalent must continue safely",
        failures,
    )
    expect(
        reconciled.effects[0].status == "applied",
        "reconciled ambiguous effect must be recorded as applied",
        failures,
    )
    expect(
        ambiguous_applied.apply_calls.count("SDA-MUT-TEST-001") == 1,
        "ambiguous effect must never be blindly retried",
        failures,
    )

    ambiguous_unknown = FakeBackend({"SDA-MUT-TEST-001": "ambiguous_unproven"})
    unknown_result = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=ambiguous_unknown
    )
    expect(
        unknown_result.status == "effect_unknown",
        "unproven ambiguous effect must remain unknown",
        failures,
    )
    expect(not unknown_result.may_create_revision, "unknown proposal cannot create Revision", failures)
    expect(
        [effect.status for effect in unknown_result.effects]
        == ["effect_unknown", "not_attempted", "not_attempted"],
        "unknown write must leave later mutations explicitly unattempted",
        failures,
    )
    expect(
        ambiguous_unknown.apply_calls == ["SDA-MUT-TEST-001"],
        "unproven ambiguous write must not retry or continue",
        failures,
    )

    definitive = FakeBackend({"SDA-MUT-TEST-002": "definitive_failure"})
    failed_result = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=definitive
    )
    expect(failed_result.status == "failed", "definitive backend rejection must fail", failures)
    expect(not failed_result.may_create_revision, "failed proposal cannot create Revision", failures)
    expect(
        [effect.status for effect in failed_result.effects]
        == ["applied", "failed", "not_attempted"],
        "failure must preserve applied/failed/unattempted effect states",
        failures,
    )

    wrong_decision = approval_for(proposal)
    wrong_decision["proposal_sha256"] = "0" * 64
    try:
        execute_authorized_proposal(
            proposal=proposal, decision=wrong_decision, backend=FakeBackend()
        )
        failures.append("mutation guard accepted a decision bound to the wrong proposal hash")
    except AuthorizationError:
        pass

    if failures:
        print("M1 mutation-guard validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated proposal authorization, preflight blocking, idempotent replay, "
        "single-attempt writes, ambiguous-effect reconciliation, and partial-state accounting."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
