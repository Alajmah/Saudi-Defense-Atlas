#!/usr/bin/env python3
"""Regression tests for bounded M2 relationship-graph event admission."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m2_relationship_graph import graph_records  # noqa: E402
from services.presentation.relationship_graph import build_relationship_graph  # noqa: E402


def main() -> int:
    records = copy.deepcopy(graph_records())

    # Boeing is discovered as a root-adjacent manufacturer of F-15SA. This event
    # deliberately mentions Boeing but has no F-15SA/root relationship and no
    # selected related Claim. A projector that expands from any discovered
    # adjacent Entity would leak this unrelated event into the F-15SA graph.
    unrelated_event = {
        "id": "SDA-EVENT-M2-UNRELATED-BOEING-AWARD",
        "event_type": "contract_award",
        "names": {
            "en": "Synthetic unrelated Boeing contract award",
            "ar": "ترسية عقد اصطناعي غير مرتبط على بوينغ",
        },
        "occurred_at": {"value": "2026-01-11", "precision": "day"},
        "ended_at": None,
        "participants": [
            {"entity_id": "SDA-ORG-BOEING", "role": "contractor"}
        ],
        "related_entity_ids": [],
        "related_claim_ids": [],
        "confidence": "verified",
        "evidence_links": [
            {
                "evidence_id": "SDA-EVID-M2-SYNTHETIC-PROCUREMENT",
                "role": "supports",
            }
        ],
        "notes": "Synthetic isolation fixture; intentionally unrelated to F-15SA.",
        "created_at": "2026-01-11T00:00:00Z",
    }
    records["events"].append(unrelated_event)

    graph = build_relationship_graph(
        root_entity_ids=["SDA-EQUIP-F15SA"],
        **records,
        projected_at="2026-01-11T00:01:00Z",
    )

    event_ids = {
        node["id"]
        for node in graph["nodes"]
        if node.get("node_kind") == "event"
    }
    timeline_ids = {item["event_id"] for item in graph["timeline"]}
    source_record_ids = {edge["source_record_id"] for edge in graph["edges"]}

    unrelated_id = unrelated_event["id"]
    failures: list[str] = []
    if unrelated_id in event_ids:
        failures.append("unrelated adjacent-entity Event leaked into graph nodes")
    if unrelated_id in timeline_ids:
        failures.append("unrelated adjacent-entity Event leaked into graph timeline")
    if unrelated_id in source_record_ids:
        failures.append("unrelated adjacent-entity Event leaked into graph edges")

    # Preserve exercise duration instead of collapsing an interval into a start date.
    exercise_id = "SDA-EVENT-M2-SYNTHETIC-EXERCISE"
    exercise_node = next(
        node for node in graph["nodes"] if node.get("id") == exercise_id
    )
    exercise_timeline = next(
        item for item in graph["timeline"] if item["event_id"] == exercise_id
    )
    expected_end = {"value": "2026-01-10", "precision": "day"}
    if exercise_node.get("ended_at") != expected_end:
        failures.append("exercise Event node lost ended_at")
    if exercise_timeline.get("ended_at") != expected_end:
        failures.append("exercise timeline entry lost ended_at")

    if failures:
        print("M2 relationship-graph isolation validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated M2 graph isolation: adjacent non-root entities do not pull in "
        "unrelated Events, and exercise end dates remain visible."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
