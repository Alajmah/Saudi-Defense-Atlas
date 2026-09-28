#!/usr/bin/env python3
"""Prove one bounded M4 multi-source editorial path through public projection.

This is an integration proof over the already-reviewed contracts. It deliberately
uses deterministic fixtures rather than selecting a model, scheduler, queue
backend, or orchestrator.
"""

from __future__ import annotations

import copy
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m4_editorial_routing import ingestion, source  # noqa: E402
from scripts.validate_m4_resolver_verifier import (  # noqa: E402
    canonical_entities,
    extraction_run,
)
from scripts.validate_schemas import build_registry  # noqa: E402
from services.governance.editorial_decision_binding import (  # noqa: E402
    build_editorial_decision_binding,
    execute_editorial_authorized_proposal,
)
from services.governance.mutation_guard import EffectInspection  # noqa: E402
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from services.governance.revision_builder import build_revision  # noqa: E402
from services.intelligence.editorial_review_packet import build_editorial_review_packet  # noqa: E402
from services.intelligence.editorial_routing import (  # noqa: E402
    RoutingPolicy,
    build_monitoring_observation,
    route_observation,
)
from services.intelligence.resolver_verifier import build_resolution_verification  # noqa: E402
from services.presentation.equipment_view import build_equipment_view  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


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


class CanonicalFixtureBackend:
    """Minimal single-writer backend that retains applied canonical payloads."""

    name = "m4-vertical-fixture"

    def __init__(self) -> None:
        self.applied_keys: dict[str, str] = {}
        self.records: dict[str, dict[str, dict[str, Any]]] = {
            "evidence": {},
            "claim": {},
            "event": {},
        }
        self.write_count = 0

    def inspect_effect(self, *, idempotency_key: str, mutation: dict[str, Any]) -> EffectInspection:
        receipt = self.applied_keys.get(idempotency_key)
        if receipt is None:
            return EffectInspection("absent")
        return EffectInspection("equivalent", receipt=receipt)

    def apply_effect(self, *, idempotency_key: str, mutation: dict[str, Any]) -> str:
        resource_type = mutation["resource_type"]
        payload = copy.deepcopy(mutation["payload"])
        receipt = f"fixture:{mutation['id']}"
        self.records[resource_type][payload["id"]] = payload
        self.applied_keys[idempotency_key] = receipt
        self.write_count += 1
        return receipt


def document(document_id: str, source_id: str, *, title: str) -> dict[str, Any]:
    return {
        "id": document_id,
        "source_id": source_id,
        "title": {"en": title},
        "canonical_url": f"https://example.invalid/{document_id.lower()}",
        "retrieved_url": None,
        "archival_url": None,
        "published_at": {"value": "2026-01-02", "precision": "day"},
        "retrieved_at": "2026-01-02T00:00:00Z",
        "language": "en",
        "document_type": "official_statement",
        "media_type": "text/html",
        "content_sha256": "9" * 64,
        "content_length_bytes": 1000,
        "version_of": None,
        "publisher_document_id": None,
        "access_notes": None,
        "licensing_notes": None,
    }


def human_decision(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "SDA-DECISION-M4-VERTICAL",
        "proposal_id": proposal["id"],
        "proposal_sha256": canonical_sha256(proposal),
        "decision": "approve",
        "decided_at": "2026-01-02T00:05:00Z",
        "decided_by": {
            "kind": "human",
            "id": "editor-vertical-fixture",
            "provider": None,
            "model": None,
            "version": None,
        },
        "reason_codes": ["evidence_sufficient"],
        "rationale": "bounded multi-source vertical-slice fixture",
        "policy_references": ["AI_GOVERNANCE", "SOURCE_POLICY"],
    }


def main() -> int:
    failures: list[str] = []

    policy = RoutingPolicy(
        policy_id="M4-VERTICAL-v0.1",
        relevance_terms=("falcon x", "training"),
        restricted_terms=("live unit movement", "readiness status"),
        high_priority_terms=("falcon x",),
        ai_extraction_feed_keys=(
            "SDA-SOURCE-VERTICAL-A|feed:test",
            "SDA-SOURCE-VERTICAL-B|feed:test",
        ),
    )
    source_a = source("SDA-SOURCE-VERTICAL-A", "A")
    source_b = source("SDA-SOURCE-VERTICAL-B", "A")
    source_a["publisher"] = {"en": "Official Vertical Source A"}
    source_b["publisher"] = {"en": "Official Vertical Source B"}

    obs_a = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-VERTICAL-A",
            canonical_sha="9" * 64,
            raw_sha="1" * 64,
            document_id="SDA-DOC-M4-RV",
            observed_at="2026-01-02T00:00:00Z",
        ),
        source=source_a,
        canonical_text="Falcon X training update from an official source.",
        policy=policy,
    )
    route_a = route_observation(obs_a, created_at="2026-01-02T00:00:10Z")
    queue = dict(route_a.item or {})

    obs_b = build_monitoring_observation(
        ingestion=ingestion(
            "SDA-SOURCE-VERTICAL-B",
            canonical_sha="9" * 64,
            raw_sha="2" * 64,
            document_id="SDA-DOC-M4-RV-CORROBORATION",
            observed_at="2026-01-02T00:00:05Z",
        ),
        source=source_b,
        canonical_text="Falcon X training update from an official source.",
        policy=policy,
    )
    route_b = route_observation(
        obs_b,
        created_at="2026-01-02T00:00:20Z",
        existing_item=queue,
    )
    queue = dict(route_b.item or {})
    queue["state"] = "claimed"

    validate("monitoring-observation.schema.json", obs_a, failures)
    validate("monitoring-observation.schema.json", obs_b, failures)
    validate("editorial-queue-item.schema.json", queue, failures)
    expect(
        set(queue["source_ids"])
        == {"SDA-SOURCE-VERTICAL-A", "SDA-SOURCE-VERTICAL-B"},
        "multi-source queue lost Source provenance",
        failures,
    )
    expect(
        set(queue["document_ids"])
        == {"SDA-DOC-M4-RV", "SDA-DOC-M4-RV-CORROBORATION"},
        "multi-source queue lost Document provenance",
        failures,
    )
    expect(queue["lane"] == "candidate_extraction", "queue did not enter extraction lane", failures)
    expect(queue["canonical_mutation_authority"] is False, "queue gained mutation authority", failures)

    extraction = extraction_run()
    extraction["queue_item_id"] = queue["id"]
    extraction["source_document_ids"] = sorted(queue["document_ids"])
    extraction["started_at"] = "2026-01-02T00:00:30Z"
    extraction["completed_at"] = "2026-01-02T00:01:00Z"
    for index, candidate in enumerate(extraction["candidates"]["evidence"]):
        candidate["document_id"] = sorted(queue["document_ids"])[index % 2]

    validate("ai-extraction-run.schema.json", extraction, failures)

    resolution, proposal = build_resolution_verification(
        extraction_run=extraction,
        canonical_entities=canonical_entities(),
        canonical_claims=[],
        canonical_events=[],
    )
    if proposal is None:
        failures.append("resolver produced no reviewable ChangeProposal")
        print("M4 multi-source vertical slice FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    proposal["source_document_ids"] = sorted(queue["document_ids"])
    validate("change-proposal.schema.json", proposal, failures)
    expect(proposal["risk_class"] == "AMBER", "resolver proposal was not AMBER", failures)
    expect(
        proposal["policy_outcome"] == "human_review_required",
        "resolver proposal bypassed human review",
        failures,
    )

    packet = build_editorial_review_packet(
        queue_item=queue,
        extraction_run=extraction,
        resolution_run=resolution,
        proposal=proposal,
        created_at="2026-01-02T00:03:00Z",
    )
    validate("editorial-review-packet.schema.json", packet, failures)
    expect(
        set(packet["source_document_ids"]) == set(queue["document_ids"]),
        "review packet lost multi-source document context",
        failures,
    )

    decision = human_decision(proposal)
    validate("review-decision.schema.json", decision, failures)
    binding = build_editorial_decision_binding(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        bound_at="2026-01-02T00:05:10Z",
    )
    validate("editorial-decision-binding.schema.json", binding, failures)

    backend = CanonicalFixtureBackend()
    execution = execute_editorial_authorized_proposal(
        review_packet=packet,
        proposal=proposal,
        decision=decision,
        binding=binding,
        backend=backend,
    )
    expect(execution.status == "converged", "canonical execution did not converge", failures)
    expect(
        backend.write_count == len(proposal["mutations"]),
        "canonical backend did not account for each mutation exactly once",
        failures,
    )

    revision = build_revision(
        proposal=proposal,
        decision=decision,
        execution=execution,
        backend_name=backend.name,
        applied_at="2026-01-02T00:06:00Z",
        adapter_id="m4-vertical-fixture",
    )
    validate("revision.schema.json", revision, failures)
    expect(
        set(item["record_id"] for item in revision["affected_records"])
        == {mutation["payload"]["id"] for mutation in proposal["mutations"]},
        "Revision does not account for every applied canonical record",
        failures,
    )

    documents = [
        document("SDA-DOC-M4-RV", source_a["id"], title="Official Falcon X update A"),
        document(
            "SDA-DOC-M4-RV-CORROBORATION",
            source_b["id"],
            title="Official Falcon X update B",
        ),
    ]
    evidence = list(backend.records["evidence"].values())
    claims = list(backend.records["claim"].values())
    events = list(backend.records["event"].values())
    view = build_equipment_view(
        entity_id="SDA-EQUIP-FALCON-X",
        entities=canonical_entities(),
        claims=claims,
        events=events,
        evidence=evidence,
        documents=documents,
        sources=[source_a, source_b],
        projected_at="2026-01-02T00:07:00Z",
        revision_ids=[revision["id"]],
    )
    validate("equipment-view.schema.json", view, failures)
    expect(
        revision["id"] in view["provenance"]["revision_ids"],
        "public view lost Revision provenance",
        failures,
    )
    expect(
        bool(view["facts"] or view["events"]),
        "canonical mutation produced no visible public fact/event",
        failures,
    )
    cited_source_ids = {
        citation["source_id"]
        for fact in view["facts"]
        for citation in fact["citations"]
    } | {
        citation["source_id"]
        for event in view["events"]
        for citation in event["citations"]
    }
    expect(
        cited_source_ids.issubset({source_a["id"], source_b["id"]}) and cited_source_ids,
        "public projection citations escaped the multi-source evidence context",
        failures,
    )
    expect(
        all(
            isinstance(record_id, str) and record_id.startswith("SDA-")
            for record_id in view["provenance"]["record_ids"]
        ),
        "backend identity leaked into public provenance",
        failures,
    )

    if failures:
        print("M4 multi-source vertical slice FAILED:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print(
        "Validated M4 multi-source editorial vertical slice: two authoritative observations -> deduplicated claimed queue -> "
        "candidate-only extraction -> resolver/verifier -> human review packet -> exact human decision binding -> existing "
        "canonical mutation guard -> project Revision -> cited EquipmentView, with multi-source provenance preserved and no AI approval authority."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())