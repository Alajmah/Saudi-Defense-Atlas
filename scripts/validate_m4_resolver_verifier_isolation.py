#!/usr/bin/env python3
"""Adversarial isolation checks for M4 resolver/verifier ambiguity semantics."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m4_resolver_verifier import (  # noqa: E402
    canonical_claims,
    canonical_entities,
    canonical_events,
    extraction_run,
)
from services.intelligence._resolver_verifier_core import (  # noqa: E402
    build_resolution_verification as build_core_resolution_verification,
)
from services.intelligence.resolver_verifier import build_resolution_verification  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def main() -> int:
    failures: list[str] = []
    extraction = extraction_run()

    # Make both Test Air Force and Test Aerospace exact resolution terms ambiguous.
    entities = canonical_entities() + [
        {
            "id": "SDA-ORG-TEST-AF-2",
            "entity_type": "organization",
            "names": {"en": "Another Air Organization"},
            "aliases": [
                {"value": "Test Air Force", "language": "en", "kind": "common"}
            ],
            "record_status": "active",
        },
        {
            "id": "SDA-ORG-TEST-AERO-2",
            "entity_type": "organization",
            "names": {"en": "Another Aerospace Organization"},
            "aliases": [
                {"value": "Test Aerospace", "language": "en", "kind": "common"}
            ],
            "record_status": "active",
        },
    ]

    run, proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=entities,
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )

    expect(
        run["resolver_version"] == "resolver-verifier-v0.4",
        "ambiguity hardening did not bump resolver version",
        failures,
    )

    # DRR-01B: one resolver version implies one resolution payload. The core
    # path and the public boundary must produce byte-identical payloads (and
    # therefore identical run identity) for the same extraction, including on
    # the ambiguous fixture where the pre-v0.4 wrapper diverged from its core.
    core_run, core_proposal = build_core_resolution_verification(
        extraction_run=extraction,
        canonical_entities=entities,
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    import json as _json

    expect(
        _json.dumps(core_run, sort_keys=True, ensure_ascii=False)
        == _json.dumps(run, sort_keys=True, ensure_ascii=False),
        "core and public resolver paths produced different payloads under one version",
        failures,
    )
    expect(
        core_run["id"] == run["id"] and core_run["resolver_version"] == run["resolver_version"],
        "core and public resolver paths minted different identities under one version",
        failures,
    )
    expect(
        _json.dumps(core_proposal, sort_keys=True, ensure_ascii=False)
        == _json.dumps(proposal, sort_keys=True, ensure_ascii=False),
        "core and public resolver paths produced different proposals under one version",
        failures,
    )

    resolutions = {
        item["candidate_entity_id"]: item["outcome"]
        for item in run["entity_resolutions"]
    }
    expect(
        resolutions["CAND-ENT-ORG"] == "ambiguous"
        and resolutions["CAND-ENT-MAKER"] == "ambiguous",
        "fixture did not create expected ambiguous entity resolutions",
        failures,
    )

    claim_states = {
        item["candidate_claim_id"]: item["outcome"]
        for item in run["claim_assessments"]
    }
    event_states = {
        item["candidate_event_id"]: item["outcome"]
        for item in run["event_assessments"]
    }
    expect(
        claim_states["CAND-CLAIM-DUP"] == "blocked_ambiguous",
        "Claim referencing ambiguous entity was mislabeled unresolved",
        failures,
    )
    expect(
        claim_states["CAND-CLAIM-UNRESOLVED"] == "blocked_unresolved",
        "genuinely unresolved Claim lost unresolved classification",
        failures,
    )
    expect(
        event_states["CAND-EVENT-POSSIBLE-DUP"] == "blocked_ambiguous",
        "Event referencing ambiguous entity was mislabeled unresolved",
        failures,
    )
    expect(
        event_states["CAND-EVENT-NEW"] == "blocked_ambiguous",
        "Event participant ambiguity was not preserved",
        failures,
    )

    if proposal is not None:
        ambiguous_canonical_ids = {
            "SDA-ORG-TEST-AF",
            "SDA-ORG-TEST-AF-2",
            "SDA-ORG-TEST-AERO",
            "SDA-ORG-TEST-AERO-2",
        }
        serialized = repr(proposal)
        expect(
            not any(entity_id in serialized for entity_id in ambiguous_canonical_ids),
            "proposal leaked a canonical choice from an ambiguous entity resolution",
            failures,
        )

    if failures:
        print("M4 resolver/verifier isolation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 resolver/verifier ambiguity isolation: ambiguous references remain "
        "blocked_ambiguous, unresolved references remain blocked_unresolved, and no ambiguous "
        "canonical choice enters the proposal."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
