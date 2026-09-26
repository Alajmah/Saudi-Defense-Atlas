#!/usr/bin/env python3
"""Validate that project Revision creation requires a newly applied execution."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.governance.mutation_guard import (  # noqa: E402
    EffectInspection,
    execute_authorized_proposal,
)
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from services.governance.revision_builder import (  # noqa: E402
    RevisionBuildError,
    build_revision,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


class EquivalentBackend:
    name = "fake-revision-backend"

    def __init__(self, *, unknown: bool = False) -> None:
        self.unknown = unknown
        self.state: set[str] = set()

    def inspect_effect(self, *, idempotency_key: str, mutation: dict) -> EffectInspection:
        if self.unknown:
            return EffectInspection("unknown", detail="synthetic unresolved backend state")
        if idempotency_key in self.state:
            return EffectInspection("equivalent", receipt=f"state:{mutation['id']}")
        return EffectInspection("absent")

    def apply_effect(self, *, idempotency_key: str, mutation: dict) -> str:
        self.state.add(idempotency_key)
        return f"write:{mutation['id']}"


def main() -> int:
    failures: list[str] = []
    with (ROOT / "data" / "sources" / "usaf.json").open("r", encoding="utf-8") as handle:
        source_record = json.load(handle)

    proposal = {
        "id": "SDA-PROPOSAL-M1-REVISION-TEST",
        "created_at": "2026-01-01T00:00:00Z",
        "risk_class": "AMBER",
        "policy_outcome": "human_review_required",
        "mutations": [
            {
                "id": "SDA-MUT-M1-REVISION-TEST",
                "action": "create",
                "resource_type": "source",
                "payload": source_record,
            }
        ],
    }
    decision = {
        "id": "SDA-DECISION-M1-REVISION-TEST",
        "proposal_id": proposal["id"],
        "proposal_sha256": canonical_sha256(proposal),
        "decision": "approve",
        "decided_at": "2026-01-01T00:01:00Z",
        "decided_by": {"kind": "human", "id": "test-editor"},
    }

    backend = EquivalentBackend()
    execution = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=backend
    )
    revision = build_revision(
        proposal=proposal,
        decision=decision,
        execution=execution,
        backend_name=backend.name,
        applied_at="2026-01-01T00:02:00Z",
        adapter_id="test-revision-adapter",
    )

    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas["revision.schema.json"],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(revision))
    if errors:
        failures.append(
            "generated Revision failed schema: "
            + "; ".join(error.message for error in errors)
        )

    expect(
        revision["proposal_id"] == proposal["id"],
        "Revision must reference the exact proposal",
        failures,
    )
    expect(
        revision["decision_id"] == decision["id"],
        "Revision must reference the approving decision",
        failures,
    )
    expect(
        len(revision["affected_records"]) == 1,
        "Revision must account for every converged mutation",
        failures,
    )
    expect(
        revision["affected_records"][0]["record_id"] == source_record["id"],
        "Revision affected record must use SDA canonical ID",
        failures,
    )
    expect(
        revision["backend_receipts"],
        "Revision should retain available backend receipts",
        failures,
    )

    same_revision = build_revision(
        proposal=proposal,
        decision=decision,
        execution=execution,
        backend_name=backend.name,
        applied_at="2026-01-01T00:02:00Z",
        adapter_id="test-revision-adapter",
    )
    expect(
        same_revision == revision,
        "identical Revision content must derive identical project Revision identity",
        failures,
    )

    replay = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=backend
    )
    expect(replay.status == "converged", "pure replay must still converge", failures)
    expect(
        all(effect.status == "already_applied" for effect in replay.effects),
        "pure replay must not issue a new backend effect",
        failures,
    )
    try:
        build_revision(
            proposal=proposal,
            decision=decision,
            execution=replay,
            backend_name=backend.name,
            applied_at="2026-01-01T00:03:00Z",
            adapter_id="test-revision-adapter",
        )
        failures.append("Revision builder accepted a pure already_applied replay")
    except RevisionBuildError:
        pass

    unknown_execution = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=EquivalentBackend(unknown=True),
    )
    try:
        build_revision(
            proposal=proposal,
            decision=decision,
            execution=unknown_execution,
            backend_name="fake-revision-backend",
            applied_at="2026-01-01T00:04:00Z",
            adapter_id="test-revision-adapter",
        )
        failures.append("Revision builder accepted effect_unknown execution")
    except RevisionBuildError:
        pass

    if failures:
        print("M1 Revision validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated schema-valid project Revision construction after newly applied effects, "
        "content-addressed Revision identity, pure-replay rejection, and rejection of "
        "effect_unknown execution."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
