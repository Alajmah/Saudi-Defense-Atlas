#!/usr/bin/env python3
"""Validate the first M1 typed proposal boundary without network or datastore IO."""

from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from services.ingestion.acquisition import FetchResponse, classify_fetch  # noqa: E402
from services.ingestion.registry import load_registered_document  # noqa: E402
from services.ingestion.usaf_f15sa_2020 import analyze_release, materialize_evidence  # noqa: E402
from services.intelligence.f15sa_proposal import (  # noqa: E402
    ProposalBuildError,
    ResolvedF15SAEntities,
    build_f15sa_proposal,
)


def expect(condition: bool, message: str, failures: list[str]) -> None:
    if not condition:
        failures.append(message)


def fixture_html() -> bytes:
    return b"""
    <html><body>
      <p>Navigation fixture</p>
      <h1>AFLCMC delivers final F-15SA to Royal Saudi Air Force</h1>
      <div>Published Dec. 11, 2020</div>
      <p>Final F-15SA aircraft were delivered Dec. 10 to the Royal Saudi Air Force.</p>
      <p>The Boeing-produced aircraft represented the last delivery in this synthetic fixture.</p>
      <p>The F-15SA is an advanced version of the F-15S and is associated with the Royal Saudi Air Force.</p>
      <p>This article fixture also mentions associated spares, simulators, training, technical documentation and program support.</p>
      <p>Featured news fixture</p>
    </body></html>
    """


def main() -> int:
    failures: list[str] = []
    schemas, schema_registry = build_registry()
    proposal_validator = Draft202012Validator(
        schemas["change-proposal.schema.json"],
        registry=schema_registry,
        format_checker=FormatChecker(),
    )

    with (ROOT / "data" / "sources" / "usaf.json").open("r", encoding="utf-8") as handle:
        source_record = json.load(handle)

    policy, _ = load_registered_document("USAF_F15SA_FINAL_DELIVERY_2020")
    parsed = analyze_release(fixture_html())
    response = FetchResponse(
        content=fixture_html(),
        retrieved_url=policy.canonical_url,
        status_code=200,
        media_type="text/html",
        etag='"proposal-fixture"',
        last_modified=None,
    )
    ingestion = classify_fetch(
        policy=policy,
        response=response,
        observed_at="2026-01-07T00:00:00Z",
        canonical_content_sha256=parsed.canonical_content_sha256,
        canonical_content_length_bytes=parsed.canonical_content_length_bytes,
        title={"en": parsed.title},
        published_at={"value": parsed.published_date, "precision": "day"},
    )
    evidence = materialize_evidence(
        parsed,
        document_id=ingestion.document["id"],
        captured_at="2026-01-07T00:00:00Z",
    )
    resolved = ResolvedF15SAEntities(
        rsaf_id="SDA-ORG-RSAF",
        f15sa_id="SDA-EQUIP-F15SA",
        boeing_id="SDA-ORG-BOEING",
    )

    proposal = build_f15sa_proposal(
        source_record=source_record,
        document_record=ingestion.document,
        evidence_records=evidence,
        resolved=resolved,
        published_date=parsed.published_date,
        delivery_date=parsed.reported_delivery_date,
        created_at="2026-01-07T00:00:01Z",
    )

    errors = list(proposal_validator.iter_errors(proposal))
    if errors:
        failures.append(
            "generated proposal failed schema: "
            + "; ".join(error.message for error in errors)
        )

    expect(proposal["risk_class"] == "AMBER", "proposal must be AMBER", failures)
    expect(
        proposal["policy_outcome"] == "human_review_required",
        "proposal must require human review",
        failures,
    )
    expect(
        proposal["source_document_ids"] == [ingestion.document["id"]],
        "proposal must reference exactly the parsed source Document",
        failures,
    )

    claim_payloads = [
        item["payload"]
        for item in proposal["mutations"]
        if item["resource_type"] == "claim"
    ]
    event_payloads = [
        item["payload"]
        for item in proposal["mutations"]
        if item["resource_type"] == "event"
    ]
    expect(len(claim_payloads) == 1, "slice must propose exactly one Claim", failures)
    expect(len(event_payloads) == 1, "slice must propose exactly one Event", failures)

    if claim_payloads:
        claim = claim_payloads[0]
        expect(
            claim["predicate_id"] == "manufacturer.manufactures.equipment",
            "slice Claim must stay within the directly supported manufacturer relationship",
            failures,
        )
        expect(
            claim["subject_id"] == resolved.boeing_id,
            "manufacturer Claim subject must be Boeing",
            failures,
        )
        expect(
            claim["value"] == {"kind": "entity", "entity_id": resolved.f15sa_id},
            "manufacturer Claim value must be F-15SA",
            failures,
        )
        expect(
            claim["validity"]["point_in_time"]["value"] == "2020-12-11",
            "manufacturer Claim must be time-qualified to the source publication date",
            failures,
        )
        expect(
            claim["confidence"] == "high",
            "candidate Claim confidence changed unexpectedly",
            failures,
        )

    if event_payloads:
        event = event_payloads[0]
        expect(event["event_type"] == "delivery", "event must remain a delivery event", failures)
        expect(
            event["occurred_at"] == {"value": "2020-12-10", "precision": "day"},
            "delivery Event date changed unexpectedly",
            failures,
        )
        participant_roles = {
            (item["entity_id"], item["role"]) for item in event["participants"]
        }
        expect(
            (resolved.rsaf_id, "recipient") in participant_roles,
            "delivery Event must retain RSAF recipient role",
            failures,
        )
        expect(
            (resolved.boeing_id, "manufacturer") in participant_roles,
            "delivery Event must retain Boeing manufacturer role",
            failures,
        )
        expect(
            "inventory" not in (event.get("notes") or "").casefold()
            or "does not imply" in (event.get("notes") or "").casefold(),
            "event notes must not imply current inventory",
            failures,
        )
        expect(
            "operator relationship" in (event.get("notes") or "").casefold(),
            "event notes must explicitly reject a timeless operator inference",
            failures,
        )

    forbidden_predicates = {
        "organization.operates.equipment_variant",
        "inventory.quantity",
        "procurement.quantity",
        "equipment.service_state",
        "procurement_program.lifecycle_state",
    }
    observed_predicates = {
        payload["predicate_id"] for payload in claim_payloads
    }
    expect(
        not (observed_predicates & forbidden_predicates),
        "first slice inferred operator/quantity/service/procurement-state claims",
        failures,
    )

    evidence_ids = {record["id"] for record in evidence}
    for payload in [*claim_payloads, *event_payloads]:
        for link in payload["evidence_links"]:
            expect(
                link["evidence_id"] in evidence_ids,
                "Claim/Event references Evidence outside this proposal bundle",
                failures,
            )

    proposal_repeat = build_f15sa_proposal(
        source_record=source_record,
        document_record=ingestion.document,
        evidence_records=evidence,
        resolved=resolved,
        published_date=parsed.published_date,
        delivery_date=parsed.reported_delivery_date,
        created_at="2026-01-07T00:00:01Z",
    )
    expect(
        proposal_repeat == proposal,
        "same immutable inputs must produce byte-equivalent proposal objects",
        failures,
    )

    try:
        build_f15sa_proposal(
            source_record=source_record,
            document_record=ingestion.document,
            evidence_records=evidence,
            resolved=ResolvedF15SAEntities(
                rsaf_id="UNRESOLVED",
                f15sa_id="SDA-EQUIP-F15SA",
                boeing_id="SDA-ORG-BOEING",
            ),
            published_date=parsed.published_date,
            delivery_date=parsed.reported_delivery_date,
            created_at="2026-01-07T00:00:01Z",
        )
        failures.append("proposal builder accepted an unresolved entity identity")
    except ProposalBuildError:
        pass

    try:
        build_f15sa_proposal(
            source_record=source_record,
            document_record=ingestion.document,
            evidence_records=evidence[:-1],
            resolved=resolved,
            published_date=parsed.published_date,
            delivery_date=parsed.reported_delivery_date,
            created_at="2026-01-07T00:00:01Z",
        )
        failures.append("proposal builder accepted incomplete Evidence")
    except ProposalBuildError:
        pass

    if failures:
        print("M1 proposal validation failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print(
        "Validated typed AMBER proposal generation, resolved-identity requirement, "
        "bounded manufacturer Claim/delivery Event scope, Evidence closure, and deterministic output."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
