#!/usr/bin/env python3
"""Validate the M4 single-writer canonical mutation dispatch contract."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m4_editorial_decision_binding import (  # noqa: E402
    FakeBackend,
    build_fixture,
    human_decision,
)
from scripts.validate_schemas import build_registry  # noqa: E402
from services.governance.canonical_mutation_dispatcher import (  # noqa: E402
    CanonicalMutationDispatchError,
    build_canonical_mutation_dispatch,
    execute_dispatched_editorial_proposal,
    validate_canonical_mutation_dispatch,
)
from services.governance.editorial_decision_binding import (  # noqa: E402
    build_editorial_decision_binding,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except (CanonicalMutationDispatchError, ValueError):
        return
    failures.append(f"{label} did not fail closed")


def validate(schema_name: str, value: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    errors = list(
        Draft202012Validator(
            schemas[schema_name], registry=registry, format_checker=FormatChecker()
        ).iter_errors(value)
    )
    if errors:
        failures.append(
            f"{schema_name}: " + "; ".join(error.message for error in errors)
        )


class FakeSingleWriterCoordinator:
    name = "fake-global-single-writer"

    def __init__(self) -> None:
        self.held = False
        self.token: str | None = None
        self.dispatch_id: str | None = None
        self.acquire_count = 0
        self.release_count = 0
        self.outcomes: list[str] = []

    def try_acquire(
        self, *, serialization_key: str, dispatch_id: str, worker_id: str
    ) -> str | None:
        if serialization_key != "canonical-global-single-writer":
            raise RuntimeError("unexpected serialization key")
        if self.held:
            return None
        self.acquire_count += 1
        self.held = True
        self.dispatch_id = dispatch_id
        self.token = f"permit:{self.acquire_count}:{worker_id}"
        return self.token

    def release(self, *, token: str, dispatch_id: str, outcome: str) -> None:
        if not self.held or token != self.token or dispatch_id != self.dispatch_id:
            raise RuntimeError("invalid single-writer release")
        self.release_count += 1
        self.outcomes.append(outcome)
        self.held = False
        self.token = None
        self.dispatch_id = None


def main() -> int:
    failures: list[str] = []
    _, proposal, packet = build_fixture()
    decision = human_decision(proposal)
    binding = build_editorial_decision_binding(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        bound_at="2026-01-02T00:04:00Z",
    )

    dispatch = build_canonical_mutation_dispatch(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
        enqueued_at="2026-01-02T00:04:10Z",
    )
    validate("canonical-mutation-dispatch.schema.json", dispatch, failures)
    validate_canonical_mutation_dispatch(
        dispatch=dispatch,
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
    )

    expected_targets: set[tuple[str, str]] = set()
    for mutation in proposal["mutations"]:
        expected_targets.add((mutation["resource_type"], mutation["payload"]["id"]))
        if mutation.get("target_id") is not None:
            expected_targets.add((mutation["resource_type"], mutation["target_id"]))
    actual_targets = {
        (item["resource_type"], item["record_id"])
        for item in dispatch["target_records"]
    }
    expect(actual_targets == expected_targets, "dispatch target set is incomplete", failures)
    expect(
        dispatch["authority"] == {
            "mode": "dispatch_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "dispatch gained independent authority",
        failures,
    )

    coordinator = FakeSingleWriterCoordinator()
    backend = FakeBackend()
    execution = execute_dispatched_editorial_proposal(
        dispatch=dispatch,
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
        backend=backend,
        coordinator=coordinator,
        worker_id="canonical-writer-1",
    )
    expect(execution.status == "converged", "serialized execution did not converge", failures)
    expect(
        backend.write_count == len(proposal["mutations"]),
        "serialized execution did not apply each mutation exactly once",
        failures,
    )
    expect(
        coordinator.acquire_count == 1
        and coordinator.release_count == 1
        and coordinator.outcomes == ["converged"]
        and coordinator.held is False,
        "single-writer permit lifecycle is incorrect",
        failures,
    )

    writes_after_first = backend.write_count
    replay = execute_dispatched_editorial_proposal(
        dispatch=dispatch,
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
        backend=backend,
        coordinator=coordinator,
        worker_id="canonical-writer-1",
    )
    expect(replay.status == "converged", "serialized replay did not converge", failures)
    expect(
        backend.write_count == writes_after_first,
        "serialized replay attempted duplicate backend writes",
        failures,
    )

    busy = FakeSingleWriterCoordinator()
    busy.held = True
    busy.token = "permit:existing"
    busy.dispatch_id = "SDA-DISPATCH-OTHER"
    busy_backend = FakeBackend()
    expect_raises(
        "second canonical worker while global lane is held",
        lambda: execute_dispatched_editorial_proposal(
            dispatch=dispatch,
            review_packet=packet,
            proposal=proposal,
            decision=decision,
            binding=binding,
            backend=busy_backend,
            coordinator=busy,
            worker_id="canonical-writer-2",
        ),
        failures,
    )
    expect(
        busy_backend.write_count == 0 and not busy_backend.applied,
        "busy single-writer lane allowed backend activity",
        failures,
    )

    tampered = copy.deepcopy(dispatch)
    tampered["target_records"] = tampered["target_records"][:-1]
    expect_raises(
        "dispatch target set tampering",
        lambda: validate_canonical_mutation_dispatch(
            dispatch=tampered,
            review_packet=packet,
            proposal=proposal,
            decision=decision,
            binding=binding,
        ),
        failures,
    )

    expect_raises(
        "dispatch predates editorial binding",
        lambda: build_canonical_mutation_dispatch(
            review_packet=packet,
            proposal=proposal,
            decision=decision,
            binding=binding,
            enqueued_at="2026-01-02T00:03:59Z",
        ),
        failures,
    )

    rejected = human_decision(proposal, disposition="reject")
    rejected_binding = build_editorial_decision_binding(
        review_packet=packet,
        proposal=proposal,
        decision=rejected,
        bound_at="2026-01-02T00:04:00Z",
    )
    expect_raises(
        "rejected decision entered canonical dispatch",
        lambda: build_canonical_mutation_dispatch(
            review_packet=packet,
            proposal=proposal,
            decision=rejected,
            binding=rejected_binding,
            enqueued_at="2026-01-02T00:04:10Z",
        ),
        failures,
    )

    if failures:
        print("M4 canonical mutation dispatcher validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 canonical mutation dispatcher: exact approved-artifact binding, complete target set, "
        "global single-writer exclusion before backend access, idempotent serialized replay, and no independent authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
