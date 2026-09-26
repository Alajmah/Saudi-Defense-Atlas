#!/usr/bin/env python3
"""Validate the first backend-neutral M2 procurement/exercise graph contract."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m1_equipment_view import canonical_records as m1_records  # noqa: E402
from scripts.validate_schemas import build_registry  # noqa: E402
from services.presentation.equipment_view import ProjectionError  # noqa: E402
from services.presentation.relationship_graph import build_relationship_graph  # noqa: E402


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def validate_instance(schema_name: str, instance: dict[str, Any], failures: list[str]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name],
        registry=registry,
        format_checker=FormatChecker(),
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        failures.append(
            f"{schema_name} failed: "
            + "; ".join(error.message for error in errors)
        )


def graph_records() -> dict[str, list[dict[str, Any]]]:
    records = copy.deepcopy(m1_records())

    source = {
        "id": "SDA-SOURCE-M2-SYNTHETIC",
        "publisher": {"en": "Synthetic M2 relationship fixture"},
        "source_class": "E",
        "publisher_type": "other",
        "homepage": "https://example.invalid/",
        "jurisdiction": None,
        "notes": "Synthetic validation source only; not factual project content.",
        "active": True,
    }
    document = {
        "id": "SDA-DOC-M2-SYNTHETIC-GRAPH",
        "source_id": source["id"],
        "title": {"en": "Synthetic M2 relationship graph fixture"},
        "canonical_url": "https://example.invalid/m2-relationship-graph",
        "retrieved_url": "https://example.invalid/m2-relationship-graph",
        "published_at": {"value": "2026-01-08", "precision": "day"},
        "retrieved_at": "2026-01-08T00:00:00Z",
        "language": "en",
        "document_type": "other",
        "media_type": "text/plain",
        "content_sha256": "b" * 64,
        "content_length_bytes": 2048,
        "version_of": None,
        "publisher_document_id": None,
        "access_notes": "Synthetic fixture.",
        "licensing_notes": None,
    }
    procurement_evidence = {
        "id": "SDA-EVID-M2-SYNTHETIC-PROCUREMENT",
        "document_id": document["id"],
        "locator": {"paragraph": 1, "selector": "fixture:p[1]"},
        "excerpt": None,
        "excerpt_sha256": None,
        "language": "en",
        "captured_at": "2026-01-08T00:00:00Z",
        "capture_method": "deterministic_parser",
        "notes": "Synthetic fixture evidence.",
    }
    exercise_evidence = {
        "id": "SDA-EVID-M2-SYNTHETIC-EXERCISE",
        "document_id": document["id"],
        "locator": {"paragraph": 2, "selector": "fixture:p[2]"},
        "excerpt": None,
        "excerpt_sha256": None,
        "language": "en",
        "captured_at": "2026-01-08T00:00:00Z",
        "capture_method": "deterministic_parser",
        "notes": "Synthetic fixture evidence.",
    }

    procurement = {
        "id": "SDA-PROC-M2-SYNTHETIC",
        "entity_type": "procurement_program",
        "subtype": "synthetic_validation_fixture",
        "names": {
            "en": "Synthetic M2 procurement program",
            "ar": "برنامج مشتريات اصطناعي لاختبار M2",
        },
        "aliases": [],
        "descriptions": {
            "en": "Synthetic fixture only.",
            "ar": "بيانات اصطناعية للاختبار فقط.",
        },
        "external_identifiers": [],
        "backend_identifiers": [{"backend": "wikibase", "value": "Q999"}],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-08T00:00:00Z",
        "updated_at": "2026-01-08T00:00:00Z",
    }
    contract = {
        "id": "SDA-CONTRACT-M2-SYNTHETIC",
        "entity_type": "contract",
        "subtype": "synthetic_validation_fixture",
        "names": {
            "en": "Synthetic M2 contract",
            "ar": "عقد اصطناعي لاختبار M2",
        },
        "aliases": [],
        "descriptions": {"en": "Synthetic fixture only."},
        "external_identifiers": [],
        "backend_identifiers": [],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-08T00:00:00Z",
        "updated_at": "2026-01-08T00:00:00Z",
    }
    exercise = {
        "id": "SDA-EXERCISE-M2-SYNTHETIC",
        "entity_type": "exercise",
        "subtype": "synthetic_validation_fixture",
        "names": {
            "en": "Synthetic M2 exercise",
            "ar": "تمرين اصطناعي لاختبار M2",
        },
        "aliases": [],
        "descriptions": {"en": "Synthetic fixture only."},
        "external_identifiers": [],
        "backend_identifiers": [],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-08T00:00:00Z",
        "updated_at": "2026-01-08T00:00:00Z",
    }

    f15sa_id = "SDA-EQUIP-F15SA"
    boeing_id = "SDA-ORG-BOEING"
    rsaf_id = "SDA-ORG-RSAF"

    procurement_claim = {
        "id": "SDA-CLAIM-M2-PROCUREMENT-ACQUIRES-F15SA",
        "subject_id": procurement["id"],
        "predicate_id": "procurement_program.acquires.equipment_variant",
        "value": {"kind": "entity", "entity_id": f15sa_id},
        "scope": {"entity_ids": [f15sa_id], "quantity_type": None, "note": "Synthetic fixture."},
        "validity": {"point_in_time": {"value": "2026-01-08", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": procurement_evidence["id"], "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }
    contract_program_claim = {
        "id": "SDA-CLAIM-M2-CONTRACT-PART-OF-PROGRAM",
        "subject_id": contract["id"],
        "predicate_id": "contract.part_of.procurement_program",
        "value": {"kind": "entity", "entity_id": procurement["id"]},
        "scope": {"entity_ids": [procurement["id"]], "quantity_type": None, "note": "Synthetic fixture."},
        "validity": {"point_in_time": {"value": "2026-01-08", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": procurement_evidence["id"], "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }
    contract_award_claim = {
        "id": "SDA-CLAIM-M2-CONTRACT-AWARDED-BOEING",
        "subject_id": contract["id"],
        "predicate_id": "contract.awarded_to.company",
        "value": {"kind": "entity", "entity_id": boeing_id},
        "scope": {"entity_ids": [boeing_id], "quantity_type": None, "note": "Synthetic fixture."},
        "validity": {"point_in_time": {"value": "2026-01-08", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": procurement_evidence["id"], "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }
    exercise_uses_claim = {
        "id": "SDA-CLAIM-M2-EXERCISE-USES-F15SA",
        "subject_id": exercise["id"],
        "predicate_id": "exercise.uses.equipment_variant",
        "value": {"kind": "entity", "entity_id": f15sa_id},
        "scope": {"entity_ids": [f15sa_id], "quantity_type": None, "note": "Synthetic fixture."},
        "validity": {"point_in_time": {"value": "2026-01-09", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": exercise_evidence["id"], "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }
    exercise_participant_claim = {
        "id": "SDA-CLAIM-M2-EXERCISE-PARTICIPANT-RSAF",
        "subject_id": exercise["id"],
        "predicate_id": "exercise.participant.organization",
        "value": {"kind": "entity", "entity_id": rsaf_id},
        "scope": {"entity_ids": [rsaf_id], "quantity_type": None, "note": "Synthetic fixture."},
        "validity": {"point_in_time": {"value": "2026-01-09", "precision": "day"}},
        "confidence": "verified",
        "evidence_links": [{"evidence_id": exercise_evidence["id"], "role": "supports"}],
        "claim_state": "active",
        "supersedes_claim_ids": [],
        "verified_at": "2026-01-08T00:00:00Z",
        "created_at": "2026-01-08T00:00:00Z",
    }

    contract_event = {
        "id": "SDA-EVENT-M2-SYNTHETIC-CONTRACT-AWARD",
        "event_type": "contract_award",
        "names": {
            "en": "Synthetic M2 contract award",
            "ar": "ترسية عقد اصطناعي لاختبار M2",
        },
        "occurred_at": {"value": "2026-01-08", "precision": "day"},
        "ended_at": None,
        "participants": [
            {"entity_id": rsaf_id, "role": "buyer"},
            {"entity_id": boeing_id, "role": "contractor"},
        ],
        "related_entity_ids": [f15sa_id, procurement["id"], contract["id"]],
        "related_claim_ids": [procurement_claim["id"], contract_program_claim["id"], contract_award_claim["id"]],
        "confidence": "verified",
        "evidence_links": [{"evidence_id": procurement_evidence["id"], "role": "supports"}],
        "notes": "Synthetic fixture only.",
        "created_at": "2026-01-08T00:00:00Z",
    }
    exercise_event = {
        "id": "SDA-EVENT-M2-SYNTHETIC-EXERCISE",
        "event_type": "exercise",
        "names": {
            "en": "Synthetic M2 exercise event",
            "ar": "حدث تمرين اصطناعي لاختبار M2",
        },
        "occurred_at": {"value": "2026-01-09", "precision": "day"},
        "ended_at": {"value": "2026-01-10", "precision": "day"},
        "participants": [{"entity_id": rsaf_id, "role": "participant"}],
        "related_entity_ids": [f15sa_id, exercise["id"]],
        "related_claim_ids": [exercise_uses_claim["id"], exercise_participant_claim["id"]],
        "confidence": "verified",
        "evidence_links": [{"evidence_id": exercise_evidence["id"], "role": "supports"}],
        "notes": "Synthetic fixture only; no operational location data.",
        "created_at": "2026-01-08T00:00:00Z",
    }

    records["entities"].extend([procurement, contract, exercise])
    records["claims"].extend(
        [
            procurement_claim,
            contract_program_claim,
            contract_award_claim,
            exercise_uses_claim,
            exercise_participant_claim,
        ]
    )
    records["events"].extend([contract_event, exercise_event])
    records["sources"].append(source)
    records["documents"].append(document)
    records["evidence"].extend([procurement_evidence, exercise_evidence])
    return records


def main() -> int:
    failures: list[str] = []
    records = graph_records()

    for schema_name, key in (
        ("entity.schema.json", "entities"),
        ("claim.schema.json", "claims"),
        ("event.schema.json", "events"),
        ("evidence.schema.json", "evidence"),
        ("document.schema.json", "documents"),
        ("source.schema.json", "sources"),
    ):
        for instance in records[key]:
            validate_instance(schema_name, instance, failures)

    graph = build_relationship_graph(
        root_entity_ids=["SDA-EQUIP-F15SA"],
        **records,
        projected_at="2026-01-08T00:05:00Z",
        revision_ids=["SDA-REVISION-M2-GRAPH-TEST"],
    )
    validate_instance("relationship-graph-view.schema.json", graph, failures)

    expect(
        graph["scope"] == {
            "root_entity_ids": ["SDA-EQUIP-F15SA"],
            "domains": ["exercise", "procurement"],
            "expansion": "bounded_single_pass",
        },
        "graph scope changed",
        failures,
    )

    node_ids = {node["id"] for node in graph["nodes"]}
    for required_id in (
        "SDA-EQUIP-F15SA",
        "SDA-ORG-BOEING",
        "SDA-ORG-RSAF",
        "SDA-PROC-M2-SYNTHETIC",
        "SDA-CONTRACT-M2-SYNTHETIC",
        "SDA-EXERCISE-M2-SYNTHETIC",
        "SDA-EVENT-M2-SYNTHETIC-CONTRACT-AWARD",
        "SDA-EVENT-M2-SYNTHETIC-EXERCISE",
    ):
        expect(required_id in node_ids, f"graph lost expected node {required_id}", failures)

    event_nodes = [node for node in graph["nodes"] if node["node_kind"] == "event"]
    expect(event_nodes, "graph must project selected Events as nodes", failures)
    for event_node in event_nodes:
        expect(bool(event_node["citations"]), f"Event node {event_node['id']} lost citations", failures)
        expect(
            any(citation["evidence_role"] == "supports" for citation in event_node["citations"]),
            f"Event node {event_node['id']} lacks supporting Evidence",
            failures,
        )

    edge_ids = {edge["id"] for edge in graph["edges"]}
    expect(
        "claim:SDA-CLAIM-M2-PROCUREMENT-ACQUIRES-F15SA" in edge_ids,
        "root-adjacent procurement Claim must project",
        failures,
    )
    expect(
        "claim:SDA-CLAIM-M2-EXERCISE-USES-F15SA" in edge_ids,
        "root-adjacent exercise Claim must project",
        failures,
    )
    expect(
        "claim:SDA-CLAIM-M2-CONTRACT-PART-OF-PROGRAM" not in edge_ids,
        "bounded graph must not cascade from procurement program to contract Claim",
        failures,
    )
    expect(
        "claim:SDA-CLAIM-M2-CONTRACT-AWARDED-BOEING" not in edge_ids,
        "bounded graph must not cascade from discovered contract to company Claim",
        failures,
    )
    expect(
        "claim:SDA-CLAIM-M2-EXERCISE-PARTICIPANT-RSAF" not in edge_ids,
        "bounded graph must not cascade from discovered exercise Entity to participant Claim",
        failures,
    )

    timeline_ids = [item["event_id"] for item in graph["timeline"]]
    expect(
        "SDA-EVENT-M2-SYNTHETIC-CONTRACT-AWARD" in timeline_ids,
        "contract award must appear in timeline",
        failures,
    )
    expect(
        "SDA-EVENT-M2-SYNTHETIC-EXERCISE" in timeline_ids,
        "exercise Event must appear in timeline",
        failures,
    )
    for item in graph["timeline"]:
        expect(bool(item["citations"]), f"timeline Event {item['event_id']} lost citations", failures)
        expect(
            any(citation["evidence_role"] == "supports" for citation in item["citations"]),
            f"timeline Event {item['event_id']} lacks supporting Evidence",
            failures,
        )

    serialized = json.dumps(graph, ensure_ascii=False, sort_keys=True)
    expect("Q999" not in serialized, "public graph must not leak backend identifiers", failures)
    expect("backend_identifiers" not in serialized, "public graph must not expose backend mapping fields", failures)

    reversed_records = copy.deepcopy(records)
    reversed_records["claims"].reverse()
    reversed_records["events"].reverse()
    reversed_graph = build_relationship_graph(
        root_entity_ids=["SDA-EQUIP-F15SA"],
        **reversed_records,
        projected_at="2026-01-08T00:05:00Z",
        revision_ids=["SDA-REVISION-M2-GRAPH-TEST"],
    )
    expect(
        reversed_graph == graph,
        "graph output must be independent of Claim/Event input order",
        failures,
    )

    exercise_only = build_relationship_graph(
        root_entity_ids=["SDA-EQUIP-F15SA"],
        **records,
        domains=["exercise"],
        projected_at="2026-01-08T00:05:00Z",
    )
    exercise_edge_relations = {edge["relation"] for edge in exercise_only["edges"]}
    expect(
        "procurement_program.acquires.equipment_variant" not in exercise_edge_relations,
        "exercise-only graph must exclude procurement Claim relations",
        failures,
    )
    expect(
        all(item["event_type"] == "exercise" for item in exercise_only["timeline"]),
        "exercise-only graph must exclude procurement Events",
        failures,
    )

    contradiction_only = copy.deepcopy(records)
    target = next(
        claim
        for claim in contradiction_only["claims"]
        if claim["id"] == "SDA-CLAIM-M2-PROCUREMENT-ACQUIRES-F15SA"
    )
    target["evidence_links"][0]["role"] = "contradicts"
    try:
        build_relationship_graph(
            root_entity_ids=["SDA-EQUIP-F15SA"],
            **contradiction_only,
            projected_at="2026-01-08T00:05:00Z",
        )
        failures.append("graph published a material Claim without supporting Evidence")
    except ProjectionError:
        pass

    event_without_support = copy.deepcopy(records)
    target_event = next(
        event
        for event in event_without_support["events"]
        if event["id"] == "SDA-EVENT-M2-SYNTHETIC-EXERCISE"
    )
    target_event["evidence_links"][0]["role"] = "contextualizes"
    try:
        build_relationship_graph(
            root_entity_ids=["SDA-EQUIP-F15SA"],
            **event_without_support,
            projected_at="2026-01-08T00:05:00Z",
        )
        failures.append("graph published a material Event without supporting Evidence")
    except ProjectionError:
        pass

    disputed = copy.deepcopy(records)
    target = next(
        claim
        for claim in disputed["claims"]
        if claim["id"] == "SDA-CLAIM-M2-PROCUREMENT-ACQUIRES-F15SA"
    )
    target["claim_state"] = "disputed"
    disputed_graph = build_relationship_graph(
        root_entity_ids=["SDA-EQUIP-F15SA"],
        **disputed,
        projected_at="2026-01-08T00:05:00Z",
    )
    disputed_edge = next(
        edge
        for edge in disputed_graph["edges"]
        if edge["source_record_id"] == "SDA-CLAIM-M2-PROCUREMENT-ACQUIRES-F15SA"
    )
    expect(disputed_edge["state"] == "disputed", "disputed Claim state must remain visible", failures)

    try:
        build_relationship_graph(
            root_entity_ids=["SDA-EQUIP-F15SA"],
            **records,
            domains=["exercise", "exercise"],
            projected_at="2026-01-08T00:05:00Z",
        )
        failures.append("graph accepted duplicate domain selectors")
    except ProjectionError:
        pass

    if failures:
        print("M2 relationship graph validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated bounded M2 relationship graph: explicit Claim/Event edges only, fixed "
        "single-pass expansion, procurement/exercise domain filtering, direct event/timeline "
        "citations, disputed-state preservation, order independence, and no backend-ID leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
