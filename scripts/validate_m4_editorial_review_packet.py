#!/usr/bin/env python3
"""Validate the M4 multi-source editorial review-packet handoff."""

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

from scripts.validate_m4_resolver_verifier import (  # noqa: E402
    canonical_claims,
    canonical_entities,
    canonical_events,
    extraction_run,
)
from scripts.validate_schemas import build_registry  # noqa: E402
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


def canonical_sha(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    failures: list[str] = []

    extraction = extraction_run()
    # Prove the handoff keeps the full multi-source context even when only one
    # source document yielded candidate Evidence in this fixture.
    extraction["source_document_ids"] = ["SDA-DOC-M4-RV", "SDA-DOC-M4-RV-CORROBORATION"]

    resolution, proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=canonical_entities(),
        canonical_claims=canonical_claims(),
        canonical_events=canonical_events(),
    )
    expect(proposal is not None, "fixture did not produce review proposal", failures)
    if proposal is None:
        return 1

    queue_item = {
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

    packet = build_editorial_review_packet(
        queue_item=queue_item,
        extraction_run=extraction,
        resolution_run=resolution,
        proposal=proposal,
        created_at="2026-01-02T00:02:00Z",
    )
    validate("editorial-review-packet.schema.json", packet, failures)
    expect(
        packet["proposal_sha256"] == canonical_sha(proposal),
        "packet is not bound to exact proposal payload",
        failures,
    )
    expect(
        packet["source_document_ids"]
        == ["SDA-DOC-M4-RV", "SDA-DOC-M4-RV-CORROBORATION"],
        "multi-source document context was dropped",
        failures,
    )
    expect(
        "multi_source_context" in packet["review_flags"]
        and "conflict_present" in packet["review_flags"]
        and "duplicates_suppressed" in packet["review_flags"]
        and "policy_blocked" in packet["review_flags"],
        "review flags omitted material resolver context",
        failures,
    )
    expect(
        packet["authority"] == {
            "mode": "review_handoff_only",
            "approval_authority": False,
            "canonical_mutation_authority": False,
            "publication_authority": False,
        },
        "review packet gained authority",
        failures,
    )
    expect(
        packet["mutation_inventory"]["evidence"] >= 1
        and packet["mutation_inventory"]["claims"] >= 1,
        "review packet mutation inventory is incomplete",
        failures,
    )

    dropped_context = copy.deepcopy(queue_item)
    dropped_context["document_ids"] = ["SDA-DOC-M4-RV"]
    expect_raises(
        "dropped multi-source queue context",
        lambda: build_editorial_review_packet(
            queue_item=dropped_context,
            extraction_run=extraction,
            resolution_run=resolution,
            proposal=proposal,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    wrong_resolution = copy.deepcopy(resolution)
    wrong_resolution["change_proposal_id"] = "SDA-PROP-OTHER"
    expect_raises(
        "resolution/proposal mismatch",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=wrong_resolution,
            proposal=proposal,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    widened = copy.deepcopy(resolution)
    widened["authority"]["approval_authority"] = True
    expect_raises(
        "resolver approval authority widening",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=widened,
            proposal=proposal,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    green = copy.deepcopy(proposal)
    green["risk_class"] = "GREEN"
    green["policy_outcome"] = "auto_eligible"
    expect_raises(
        "AI proposal auto-approval widening",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=resolution,
            proposal=green,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    orphan_evidence = copy.deepcopy(proposal)
    for mutation in orphan_evidence["mutations"]:
        if mutation["resource_type"] in {"claim", "event"}:
            mutation["payload"]["evidence_links"][0]["evidence_id"] = "SDA-EVID-OUTSIDE-PROPOSAL"
            break
    expect_raises(
        "factual mutation Evidence outside proposal",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=resolution,
            proposal=orphan_evidence,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    escaped_document = copy.deepcopy(proposal)
    for mutation in escaped_document["mutations"]:
        if mutation["resource_type"] == "evidence":
            mutation["payload"]["document_id"] = "SDA-DOC-OUTSIDE-QUEUE"
            break
    expect_raises(
        "Evidence escaped extraction document context",
        lambda: build_editorial_review_packet(
            queue_item=queue_item,
            extraction_run=extraction,
            resolution_run=resolution,
            proposal=escaped_document,
            created_at="2026-01-02T00:02:00Z",
        ),
        failures,
    )

    if failures:
        print("M4 editorial review packet validation FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 editorial review packet: exact proposal hash binding, full multi-source context, "
        "resolver conflict/blocker visibility, Evidence provenance closure, and zero approval/write/publication authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
