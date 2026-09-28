#!/usr/bin/env python3
"""Validate M4 human editorial decision binding into the existing mutation guard."""

from __future__ import annotations

import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m4_editorial_review_packet_isolation import queue_fixture  # noqa: E402
from scripts.validate_m4_resolver_verifier import (  # noqa: E402
    canonical_claims,
    canonical_entities,
    canonical_events,
    extraction_run,
)
from scripts.validate_schemas import build_registry  # noqa: E402
from services.governance.editorial_decision_binding import (  # noqa: E402
    EditorialDecisionBindingError,
    build_editorial_decision_binding,
    execute_editorial_authorized_proposal,
    validate_editorial_decision_binding,
)
from services.governance.mutation_guard import EffectInspection  # noqa: E402
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from services.intelligence.editorial_review_packet import build_editorial_review_packet  # noqa: E402
from services.intelligence.resolver_verifier import build_resolution_verification  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except (EditorialDecisionBindingError, ValueError):
        return
    failures.append(f"{label} did not fail closed")


def validate(schema_name: str, value: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(value))
    if errors:
        failures.append(
            f"{schema_name}: " + "; ".join(error.message for error in errors)
        )


def canonical_object_sha(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class FakeBackend:
    name = "fake-editorial-binding"

    def __init__(self) -> None:
        self.applied: dict[str, str] = {}
        self.write_count = 0

    def inspect_effect(self, *, idempotency_key: str, mutation: dict[str, Any]) -> EffectInspection:
        receipt = self.applied.get(idempotency_key)
        if receipt is None:
            return EffectInspection("absent")
        return EffectInspection("equivalent", receipt=receipt)

    def apply_effect(self, *, idempotency_key: str, mutation: dict[str, Any]) -> str:
        self.write_count += 1
        receipt = f"receipt:{mutation['id']}"
        self.applied[idempotency_key] = receipt
        return receipt


def build_fixture() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    extraction = extraction_run()
    extraction["source_document_ids"] = [
        "SDA-DOC-M4-RV",
        "SDA-DOC-M4-RV-CORROBORATION",
    ]
    resolution, proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=canonical_entities(),
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    if proposal is None:
        raise RuntimeError("fixture produced no proposal")
    packet = build_editorial_review_packet(
        queue_item=queue_fixture(),
        extraction_run=extraction,
        resolution_run=resolution,
        proposal=proposal,
        created_at="2026-01-02T00:02:00Z",
    )
    return extraction, proposal, packet


def human_decision(proposal: dict[str, Any], *, disposition: str = "approve") -> dict[str, Any]:
    return {
        "id": f"SDA-DECISION-M4-{disposition.upper()}",
        "proposal_id": proposal["id"],
        "proposal_sha256": canonical_sha256(proposal),
        "decision": disposition,
        "decided_at": "2026-01-02T00:03:00Z",
        "decided_by": {
            "kind": "human",
            "id": "editor-fixture",
            "provider": None,
            "model": None,
            "version": None,
        },
        "reason_codes": [
            "evidence_sufficient" if disposition == "approve" else "editorial_correction"
        ],
        "rationale": "fixture decision",
        "policy_references": ["AI_GOVERNANCE", "SOURCE_POLICY"],
    }


def main() -> int:
    failures: list[str] = []
    _, proposal, packet = build_fixture()
    decision = human_decision(proposal)
    validate("review-decision.schema.json", decision, failures)

    binding = build_editorial_decision_binding(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        bound_at="2026-01-02T00:04:00Z",
    )
    validate("editorial-decision-binding.schema.json", binding, failures)
    expect(
        binding["review_packet_id"] == packet["id"]
        and binding["review_packet_sha256"] == canonical_object_sha(packet)
        and binding["proposal_id"] == proposal["id"]
        and binding["proposal_sha256"] == canonical_sha256(proposal),
        "binding lost exact review/proposal identity",
        failures,
    )
    expect(
        binding["authority"] == {
            "mode": "decision_binding_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "binding gained independent authority",
        failures,
    )
    validate_editorial_decision_binding(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
    )

    backend = FakeBackend()
    execution = execute_editorial_authorized_proposal(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
        backend=backend,
    )
    expect(execution.status == "converged", "approved editorial proposal did not converge", failures)
    expect(
        backend.write_count == len(proposal["mutations"]),
        "approved execution did not pass through mutation effects exactly once",
        failures,
    )

    reject = human_decision(proposal, disposition="reject")
    reject_binding = build_editorial_decision_binding(
        review_packet=packet,
        proposal=proposal,
        decision=reject,
        bound_at="2026-01-02T00:04:00Z",
    )
    reject_backend = FakeBackend()
    expect_raises(
        "rejected editorial decision enters canonical execution",
        lambda: execute_editorial_authorized_proposal(
            review_packet=packet,
            proposal=proposal,
            decision=reject,
            binding=reject_binding,
            backend=reject_backend,
        ),
        failures,
    )
    expect(reject_backend.write_count == 0, "rejected decision attempted backend write", failures)

    ai_decision = copy.deepcopy(decision)
    ai_decision["decided_by"]["kind"] = "ai"
    expect_raises(
        "AI reviewer at human editorial gate",
        lambda: build_editorial_decision_binding(
            review_packet=packet,
            proposal=proposal,
            decision=ai_decision,
            bound_at="2026-01-02T00:04:00Z",
        ),
        failures,
    )

    stale_decision = copy.deepcopy(decision)
    stale_decision["decided_at"] = "2026-01-02T00:01:30Z"
    expect_raises(
        "decision predates review packet",
        lambda: build_editorial_decision_binding(
            review_packet=packet,
            proposal=proposal,
            decision=stale_decision,
            bound_at="2026-01-02T00:04:00Z",
        ),
        failures,
    )

    tampered_packet = copy.deepcopy(packet)
    tampered_packet["review_flags"] = [*tampered_packet["review_flags"], "tampered"]
    expect_raises(
        "review packet changed without content-addressed ID change",
        lambda: build_editorial_decision_binding(
            review_packet=tampered_packet,
            proposal=proposal,
            decision=decision,
            bound_at="2026-01-02T00:04:00Z",
        ),
        failures,
    )

    tampered_decision = copy.deepcopy(decision)
    tampered_decision["rationale"] = "changed after binding"
    expect_raises(
        "ReviewDecision changed after binding",
        lambda: validate_editorial_decision_binding(
            review_packet=packet,
            proposal=proposal,
            decision=tampered_decision,
            binding=binding,
        ),
        failures,
    )

    tampered_binding = copy.deepcopy(binding)
    tampered_binding["review_packet_sha256"] = "0" * 64
    expect_raises(
        "binding record tampered after creation",
        lambda: validate_editorial_decision_binding(
            review_packet=packet,
            proposal=proposal,
            decision=decision,
            binding=tampered_binding,
        ),
        failures,
    )

    changed_proposal = copy.deepcopy(proposal)
    changed_proposal["created_at"] = "2026-01-02T00:01:30Z"
    expect_raises(
        "proposal changed after human review",
        lambda: validate_editorial_decision_binding(
            review_packet=packet,
            proposal=changed_proposal,
            decision=decision,
            binding=binding,
        ),
        failures,
    )

    if failures:
        print("M4 editorial decision binding validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 editorial decision binding: full packet/proposal/decision hashes, human-only AMBER review, "
        "temporal ordering, immutable audit binding, reject-no-write behavior, and approved reuse of the existing mutation guard."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())