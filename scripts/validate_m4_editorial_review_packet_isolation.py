#!/usr/bin/env python3
"""First-pass isolation tests for M4 editorial review packets."""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m4_resolver_verifier import (  # noqa: E402
    canonical_claims,
    canonical_entities,
    canonical_events,
    extraction_run,
)
from services.intelligence.editorial_review_packet import (  # noqa: E402
    EditorialReviewPacketError,
    build_editorial_review_packet,
)
from services.intelligence.resolver_verifier import build_resolution_verification  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def expect_raises(label: str, fn: Any, failures: list[str]) -> None:
    try:
        fn()
    except EditorialReviewPacketError:
        return
    failures.append(f"{label} did not fail closed")


def queue_fixture() -> dict[str, Any]:
    return {
        "id": "SDA-QUEUE-M4-RV-TEST",
        "observation_ids": ["SDA-OBS-M4-1", "SDA-OBS-M4-2"],
        "source_ids": ["SDA-SOURCE-M4-A", "SDA-SOURCE-M4-B"],
        "document_ids": ["SDA-DOC-M4-RV", "SDA-DOC-M4-RV-CORROBORATION"],
        "dedupe_key": "sha256:" + "d" * 64,
        "lane": "candidate_extraction",
        "state": "claimed",
        "priority": "high",
        "reason_codes": ["multi_source_candidate"],
        "ai_extraction_allowed": True,
        "canonical_mutation_authority": False,
        "created_at": "2026-01-02T00:00:00Z",
    }


def main() -> int:
    failures: list[str] = []
    extraction = extraction_run()
    extraction["source_document_ids"] = [
        "SDA-DOC-M4-RV",
        "SDA-DOC-M4-RV-CORROBORATION",
    ]
    # Standalone unresolved entity: it is not referenced by a Claim/Event, but a
    # human editor must still see that the extraction contained an unresolved mention.
    extraction["candidates"]["entities"].append(
        {
            "candidate_id": "CAND-ENT-STANDALONE",
            "entity_type": "organization",
            "subtype": None,
            "names": {"en": "Standalone Unknown Organization"},
            "aliases": [],
            "evidence_candidate_ids": ["CAND-EVID-1"],
        }
    )

    resolution, proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=canonical_entities(),
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    if proposal is None:
        print("M4 editorial review packet isolation FAILED: fixture produced no proposal")
        return 1

    queue_item = queue_fixture()
    packet = build_editorial_review_packet(
        queue_item=queue_item,
        extraction_run=extraction,
        resolution_run=resolution,
        proposal=proposal,
        created_at="2026-01-02T00:02:00Z",
    )
    expect(
        "CAND-ENT-STANDALONE"
        in packet["assessment_summary"]["blocked_unresolved_candidate_ids"],
        "standalone unresolved Entity disappeared from human review context",
        failures,
    )
    expect(
        "unresolved_entity_blocked" in packet["review_flags"],
        "standalone unresolved Entity did not raise review flag",
        failures,
    )

    repeated = build_editorial_review_packet(
        queue_item=queue_item,
        extraction_run=extraction,
        resolution_run=resolution,
        proposal=proposal,
        created_at="2026-01-02T00:02:00Z",
    )
    expect(packet["id"] == repeated["id"], "packet ID is not deterministic", failures)

    tampered = copy.deepcopy(proposal)
    for mutation in tampered["mutations"]:
        if mutation["resource_type"] == "claim":
            mutation["payload"]["notes"] = "tampered after resolver"
            break
    expect_raises(
        "proposal payload changed without deterministic ID change",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=resolution,
            proposal=tampered,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    expect_raises(
        "review packet predates upstream artifacts",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=resolution,
            proposal=proposal,
            created_at="2026-01-01T23:59:59Z",
        ),
        failures,
    )

    if failures:
        print("M4 editorial review packet isolation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 review-packet first-pass isolation: deterministic proposal identity, "
        "standalone entity-resolution visibility, temporal ordering, and content-addressed packet identity."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
