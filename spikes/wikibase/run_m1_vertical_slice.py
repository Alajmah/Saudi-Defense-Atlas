#!/usr/bin/env python3
"""Run the bounded M1 proposal through the real local Wikibase backend."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SPIKE_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from scripts.validate_workflow import validate_case  # noqa: E402
from services.governance.mutation_guard import execute_authorized_proposal  # noqa: E402
from services.governance.proposal_auth import canonical_sha256  # noqa: E402
from services.governance.revision_builder import build_revision  # noqa: E402
from services.ingestion.acquisition import FetchResponse, classify_fetch  # noqa: E402
from services.ingestion.registry import load_registered_document  # noqa: E402
from services.ingestion.usaf_f15sa_2020 import analyze_release, materialize_evidence  # noqa: E402
from services.intelligence.f15sa_proposal import (  # noqa: E402
    ResolvedF15SAEntities,
    build_f15sa_proposal,
)
from m1_backend import PROJECTION_VERSION, WikibaseM1Backend  # noqa: E402
from m1_wikibase_api import M1WikibaseAPI  # noqa: E402

BASE_STATE = SPIKE_DIR / "state.generated.json"
PROJECTION_STATE = SPIKE_DIR / "m1_projection_state.generated.json"
OUTPUT = SPIKE_DIR / "m1_vertical_slice.generated.json"


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


def validate_schema(schema_name: str, instance: dict[str, Any]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    errors = list(validator.iter_errors(instance))
    if errors:
        raise AssertionError(
            f"{schema_name} failed: " + "; ".join(error.message for error in errors)
        )


def qualifier_values(statement: dict[str, Any], property_id: str) -> list[Any]:
    return [
        snak.get("datavalue", {}).get("value")
        for snak in statement.get("qualifiers", {}).get(property_id, [])
    ]


def main_values(entity: dict[str, Any], property_id: str) -> list[Any]:
    return [
        statement.get("mainsnak", {}).get("datavalue", {}).get("value")
        for statement in entity.get("claims", {}).get(property_id, [])
    ]


def verify_base_identity_lookup(
    api: M1WikibaseAPI, base_state: dict[str, Any]
) -> dict[str, str]:
    """Prove Action-API canonical-ID lookup for the preexisting M0 entities M1 needs."""
    canonical_ids = {
        "rsaf": "SDA-ORG-RSAF",
        "boeing": "SDA-ORG-BOEING",
        "f15sa": "SDA-EQUIP-F15SA",
    }
    property_id = base_state["properties"]["canonical_id"]
    mappings: dict[str, str] = {}
    for key, canonical_id in canonical_ids.items():
        expected_qid = str(base_state["items"][key])
        entity = api.get_entity(expected_qid)
        observed = main_values(entity, property_id)
        if observed != [canonical_id]:
            raise AssertionError(
                f"seeded {key} canonical ID mismatch: expected {canonical_id}, observed {observed}"
            )
        matches = api.find_items_by_string_claim(property_id, canonical_id)
        if matches != [expected_qid]:
            raise AssertionError(
                f"Action API canonical lookup for {canonical_id} returned {matches}, "
                f"expected {[expected_qid]}"
            )
        mappings[canonical_id] = expected_qid
    return mappings


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit("reset the spike before rerunning M1 verification")
    if not BASE_STATE.exists() or not PROJECTION_STATE.exists():
        raise SystemExit("run seed.py and bootstrap_m1_projection.py first")

    base_state = json.loads(BASE_STATE.read_text(encoding="utf-8"))
    projection_state = json.loads(PROJECTION_STATE.read_text(encoding="utf-8"))
    source_record = json.loads(
        (ROOT / "data" / "sources" / "usaf.json").read_text(encoding="utf-8")
    )
    policy, _ = load_registered_document("USAF_F15SA_FINAL_DELIVERY_2020")

    parsed = analyze_release(fixture_html())
    response = FetchResponse(
        content=fixture_html(),
        retrieved_url=policy.canonical_url,
        status_code=200,
        media_type="text/html",
        etag='"m1-wikibase-fixture"',
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
    proposal = build_f15sa_proposal(
        source_record=source_record,
        document_record=ingestion.document,
        evidence_records=evidence,
        resolved=ResolvedF15SAEntities(
            rsaf_id="SDA-ORG-RSAF",
            f15sa_id="SDA-EQUIP-F15SA",
            boeing_id="SDA-ORG-BOEING",
        ),
        published_date=parsed.published_date,
        delivery_date=parsed.reported_delivery_date,
        created_at="2026-01-07T00:00:01Z",
    )
    validate_schema("change-proposal.schema.json", proposal)

    decision = {
        "id": "SDA-DECISION-M1-F15SA-CI-APPROVAL",
        "proposal_id": proposal["id"],
        "proposal_sha256": canonical_sha256(proposal),
        "decision": "approve",
        "decided_at": "2026-01-07T00:01:00Z",
        "decided_by": {"kind": "human", "id": "m1-ci-reviewer"},
        "reason_codes": ["evidence_sufficient"],
        "rationale": "Synthetic runtime approval for the bounded local M1 verification only.",
        "policy_references": ["docs/AI_GOVERNANCE.md", "docs/SOURCE_POLICY.md"],
    }
    validate_schema("review-decision.schema.json", decision)
    workflow_errors = validate_case(
        {"proposal": proposal, "decision": decision, "revision": None}
    )
    if workflow_errors:
        raise AssertionError("pre-write workflow invalid: " + "; ".join(workflow_errors))

    base_url = os.environ.get("WIKIBASE_URL", "http://localhost:8181")
    username = os.environ.get("MW_ADMIN_NAME", "")
    password = os.environ.get("MW_ADMIN_PASS", "")
    if not username or not password:
        raise SystemExit("MW_ADMIN_NAME and MW_ADMIN_PASS are required")

    api = M1WikibaseAPI(base_url, username, password)
    api.login()
    base_identity_mappings = verify_base_identity_lookup(api, base_state)
    backend = WikibaseM1Backend(
        api=api,
        base_state=base_state,
        projection_state=projection_state,
        proposal=proposal,
    )

    first = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=backend
    )
    if first.status != "converged" or not first.may_create_revision:
        raise AssertionError(f"first execution did not converge: {first}")
    if not all(effect.status == "applied" for effect in first.effects):
        raise AssertionError("first execution did not apply every mutation exactly once")

    replay = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=backend
    )
    if replay.status != "converged":
        raise AssertionError(f"replay did not converge: {replay}")
    if not all(effect.status == "already_applied" for effect in replay.effects):
        raise AssertionError("replay issued or required a new backend effect")

    revision = build_revision(
        proposal=proposal,
        decision=decision,
        execution=first,
        backend_name=backend.name,
        applied_at="2026-01-07T00:02:00Z",
        adapter_id="wikibase-m1-adapter",
    )
    validate_schema("revision.schema.json", revision)
    workflow_errors = validate_case(
        {"proposal": proposal, "decision": decision, "revision": revision}
    )
    if workflow_errors:
        raise AssertionError("post-write workflow invalid: " + "; ".join(workflow_errors))

    base_props = base_state["properties"]
    props = projection_state["properties"]
    claim = next(
        mutation["payload"]
        for mutation in proposal["mutations"]
        if mutation["resource_type"] == "claim"
    )
    event = next(
        mutation["payload"]
        for mutation in proposal["mutations"]
        if mutation["resource_type"] == "event"
    )

    claim_subject_qid = backend._resolve_domain_item(claim["subject_id"])
    claim_subject = api.get_entity(claim_subject_qid)
    claim_property = backend._claim_property(claim)
    claim_statements = []
    for statement in claim_subject.get("claims", {}).get(claim_property, []):
        if claim["id"] in qualifier_values(statement, base_props["claim_id"]):
            claim_statements.append(statement)
    if len(claim_statements) != 1:
        raise AssertionError("canonical manufacturer Claim was not uniquely readable")
    claim_statement = claim_statements[0]
    if len(claim_statement.get("references", [])) != 1:
        raise AssertionError("canonical Claim did not retain exactly one Evidence reference")
    reference_snaks = claim_statement["references"][0].get("snaks", {})
    if props["evidence_id"] not in reference_snaks:
        raise AssertionError("Claim reference lost SDA Evidence ID")
    if base_props["document_id"] not in reference_snaks:
        raise AssertionError("Claim reference lost SDA Document ID")
    if props["evidence_selector"] not in reference_snaks:
        raise AssertionError("Claim reference lost Evidence selector")
    if qualifier_values(claim_statement, props["claim_state"]) != ["active"]:
        raise AssertionError("Claim projection lost claim_state")
    if qualifier_values(claim_statement, props["created_at_iso"]) != [claim["created_at"]]:
        raise AssertionError("Claim projection lost created_at")
    if qualifier_values(claim_statement, props["projection_version"]) != [PROJECTION_VERSION]:
        raise AssertionError("Claim projection version is missing or changed")

    event_qid = backend._resolve_domain_item(event["id"])
    event_item = api.get_entity(event_qid)
    evidence_links = event_item.get("claims", {}).get(props["evidence_link"], [])
    if len(evidence_links) != 2:
        raise AssertionError("Event did not retain both Evidence links")
    participant_statements = event_item.get("claims", {}).get(base_props["participant"], [])
    participant_roles = sorted(
        str(value)
        for statement in participant_statements
        for value in qualifier_values(statement, props["participant_role"])
    )
    if participant_roles != ["manufacturer", "recipient"]:
        raise AssertionError(f"Event participant roles changed: {participant_roles}")
    if main_values(event_item, props["related_claim_id"]) != event["related_claim_ids"]:
        raise AssertionError("Event projection lost related Claim IDs")
    if main_values(event_item, props["created_at_iso"]) != [event["created_at"]]:
        raise AssertionError("Event projection lost created_at")
    if main_values(event_item, props["projection_version"]) != [PROJECTION_VERSION]:
        raise AssertionError("Event projection version is missing or changed")

    evidence_payload = next(
        mutation["payload"]
        for mutation in proposal["mutations"]
        if mutation["resource_type"] == "evidence"
        and mutation["payload"].get("locator", {}).get("fragment") == "final-delivery"
    )
    evidence_qid = backend._resolve_domain_item(evidence_payload["id"])
    evidence_item = api.get_entity(evidence_qid)
    if main_values(evidence_item, props["captured_at_iso"]) != [evidence_payload["captured_at"]]:
        raise AssertionError("Evidence projection lost captured_at")
    if main_values(evidence_item, props["capture_method"]) != [evidence_payload["capture_method"]]:
        raise AssertionError("Evidence projection lost capture_method")
    if main_values(evidence_item, props["projection_version"]) != [PROJECTION_VERSION]:
        raise AssertionError("Evidence projection version is missing or changed")

    item_mappings = {}
    for mutation in proposal["mutations"]:
        if mutation["resource_type"] in {"source", "document", "evidence", "event"}:
            record_id = mutation["payload"]["id"]
            matches = backend._domain_item_matches(record_id)
            if len(matches) != 1:
                raise AssertionError(f"{record_id} is not uniquely addressable")
            item_mappings[record_id] = matches[0]

    output = {
        "status": "PASS",
        "proposal_id": proposal["id"],
        "decision_id": decision["id"],
        "revision": revision,
        "item_namespace_id": api.item_namespace_id(),
        "base_identity_mappings": base_identity_mappings,
        "first_execution": {
            "status": first.status,
            "effects": [effect.status for effect in first.effects],
        },
        "replay": {
            "status": replay.status,
            "effects": [effect.status for effect in replay.effects],
        },
        "item_mappings": item_mappings,
        "claim": {
            "id": claim["id"],
            "subject_qid": claim_subject_qid,
            "predicate": claim["predicate_id"],
            "reference_evidence_id_preserved": True,
            "reference_document_id_preserved": True,
            "reference_selector_preserved": True,
            "projection_version": PROJECTION_VERSION,
        },
        "event": {
            "id": event["id"],
            "qid": event_qid,
            "evidence_link_count": len(evidence_links),
            "participant_roles": participant_roles,
            "related_claim_ids_preserved": True,
            "projection_version": PROJECTION_VERSION,
        },
        "claim_ceiling": (
            "This verifies the bounded M1 adapter, exact replay/idempotency semantics, "
            "projection completeness markers, and project Revision construction in the "
            "local stack; it is not production or concurrent-writer qualification."
        ),
    }
    OUTPUT.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
