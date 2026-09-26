#!/usr/bin/env python3
"""Qualify the bounded M1 public read projection against the real local Wikibase stack."""

from __future__ import annotations

import json
import os
import re
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
from services.presentation.equipment_view import build_equipment_view  # noqa: E402
from m1_public_projection_backend import (  # noqa: E402
    READ_PROJECTION_VERSION,
    WikibaseM1PublicProjectionBackend,
)
from m1_public_projection_proposal import build_public_projection_proposal  # noqa: E402
from m1_read_adapter import WikibaseM1ReadAdapter  # noqa: E402
from m1_wikibase_api import M1WikibaseAPI  # noqa: E402
from run_m1_vertical_slice import fixture_html  # noqa: E402

BASE_STATE = SPIKE_DIR / "state.generated.json"
PROJECTION_STATE = SPIKE_DIR / "m1_projection_state.generated.json"
M1_WRITE_OUTPUT = SPIKE_DIR / "m1_vertical_slice.generated.json"
OUTPUT = SPIKE_DIR / "m1_public_projection.generated.json"
TARGET_ID = "SDA-EQUIP-F15SA"


def validate_schema(schema_name: str, instance: dict[str, Any]) -> None:
    schemas, registry = build_registry()
    validator = Draft202012Validator(
        schemas[schema_name], registry=registry, format_checker=FormatChecker()
    )
    errors = sorted(
        validator.iter_errors(instance),
        key=lambda error: tuple(str(segment) for segment in error.absolute_path),
    )
    if errors:
        rendered = "; ".join(
            f"{'.'.join(map(str, error.absolute_path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise AssertionError(f"{schema_name} failed: {rendered}")


def rebuild_write_proposal() -> dict[str, Any]:
    """Rebuild the exact deterministic M1 write proposal used by the prior stack step."""
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
            f15sa_id=TARGET_ID,
            boeing_id="SDA-ORG-BOEING",
        ),
        published_date=parsed.published_date,
        delivery_date=parsed.reported_delivery_date,
        created_at="2026-01-07T00:00:01Z",
    )
    validate_schema("change-proposal.schema.json", proposal)
    return proposal


def assert_no_backend_ids(value: Any, path: str = "<root>") -> None:
    """Prove the public contract contains no Wikibase Q/P identity leakage."""
    if isinstance(value, dict):
        for key, child in value.items():
            assert_no_backend_ids(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_backend_ids(child, f"{path}[{index}]")
        return
    if isinstance(value, str) and re.fullmatch(r"[QP]\d+", value):
        raise AssertionError(f"backend identifier leaked at {path}: {value}")


def main() -> int:
    if OUTPUT.exists():
        raise SystemExit("reset the spike before rerunning M1 public projection verification")
    for required in (BASE_STATE, PROJECTION_STATE, M1_WRITE_OUTPUT):
        if not required.exists():
            raise SystemExit(f"required prior verification artifact is missing: {required.name}")

    base_state = json.loads(BASE_STATE.read_text(encoding="utf-8"))
    projection_state = json.loads(PROJECTION_STATE.read_text(encoding="utf-8"))
    write_proposal = rebuild_write_proposal()
    event_payload = next(
        mutation["payload"]
        for mutation in write_proposal["mutations"]
        if mutation["resource_type"] == "event"
    )

    proposal = build_public_projection_proposal(
        event_payload=event_payload,
        created_at="2026-01-07T00:03:00Z",
    )
    validate_schema("change-proposal.schema.json", proposal)

    decision = {
        "id": "SDA-DECISION-M1-PUBLIC-READ-CI-APPROVAL",
        "proposal_id": proposal["id"],
        "proposal_sha256": canonical_sha256(proposal),
        "decision": "approve",
        "decided_at": "2026-01-07T00:04:00Z",
        "decided_by": {"kind": "human", "id": "m1-public-read-ci-reviewer"},
        "reason_codes": ["evidence_sufficient"],
        "rationale": (
            "Synthetic CI approval for the bounded canonical read-projection migration only."
        ),
        "policy_references": ["docs/AI_GOVERNANCE.md", "docs/SOURCE_POLICY.md"],
    }
    validate_schema("review-decision.schema.json", decision)
    workflow_errors = validate_case(
        {"proposal": proposal, "decision": decision, "revision": None}
    )
    if workflow_errors:
        raise AssertionError(
            "public-read pre-write workflow invalid: " + "; ".join(workflow_errors)
        )

    base_url = os.environ.get("WIKIBASE_URL", "http://localhost:8181")
    username = os.environ.get("MW_ADMIN_NAME", "")
    password = os.environ.get("MW_ADMIN_PASS", "")
    if not username or not password:
        raise SystemExit("MW_ADMIN_NAME and MW_ADMIN_PASS are required")

    api = M1WikibaseAPI(base_url, username, password)
    api.login()
    backend = WikibaseM1PublicProjectionBackend(
        api=api,
        base_state=base_state,
        projection_state=projection_state,
        proposal=proposal,
    )

    first = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=backend
    )
    if first.status != "converged" or not first.may_create_revision:
        raise AssertionError(f"public-read migration did not converge: {first}")
    if not all(effect.status == "applied" for effect in first.effects):
        raise AssertionError("public-read migration did not apply each metadata update once")

    replay = execute_authorized_proposal(
        proposal=proposal, decision=decision, backend=backend
    )
    if replay.status != "converged":
        raise AssertionError(f"public-read migration replay did not converge: {replay}")
    if not all(effect.status == "already_applied" for effect in replay.effects):
        raise AssertionError("public-read migration replay required a new backend write")

    revision = build_revision(
        proposal=proposal,
        decision=decision,
        execution=first,
        backend_name=backend.name,
        applied_at="2026-01-07T00:05:00Z",
        adapter_id="wikibase-m1-public-read-adapter",
    )
    validate_schema("revision.schema.json", revision)
    workflow_errors = validate_case(
        {"proposal": proposal, "decision": decision, "revision": revision}
    )
    if workflow_errors:
        raise AssertionError(
            "public-read post-write workflow invalid: " + "; ".join(workflow_errors)
        )

    reader = WikibaseM1ReadAdapter(
        api=api,
        base_state=base_state,
        projection_state=projection_state,
    )
    bundle = reader.read_bundle(TARGET_ID)
    view = build_equipment_view(
        entity_id=TARGET_ID,
        entities=bundle["entities"],
        claims=bundle["claims"],
        events=bundle["events"],
        evidence=bundle["evidence"],
        documents=bundle["documents"],
        sources=bundle["sources"],
        projected_at="2026-01-07T00:06:00Z",
        revision_ids=[revision["id"]],
    )
    validate_schema("equipment-view.schema.json", view)
    assert_no_backend_ids(view)

    if set(view["names"]) != {"ar", "en"}:
        raise AssertionError(f"bilingual F-15SA names were not preserved: {view['names']}")
    if view["field_states"]["manufacturer"]["state"] != "known":
        raise AssertionError("canonical manufacturer Claim did not reach the public view")
    if view["field_states"]["operator"]["state"] != "unknown":
        raise AssertionError(
            "legacy M0/delivery context leaked into a timeless public operator fact"
        )
    if view["field_states"]["inventory_quantity"]["state"] != "unknown":
        raise AssertionError("public view invented an inventory quantity")
    if view["field_states"]["service_state"]["state"] != "unknown":
        raise AssertionError("public view invented a service state")
    if any(
        fact["predicate_id"] == "organization.operates.equipment_variant"
        for fact in view["facts"]
    ):
        raise AssertionError("unadmitted operator Claim leaked through read adapter")
    if len(view["events"]) != 1 or view["events"][0]["event_type"] != "delivery":
        raise AssertionError("bounded delivery Event did not survive canonical readback")
    if not view["events"][0]["citations"]:
        raise AssertionError("public delivery Event lost its citation chain")

    output = {
        "status": "PASS",
        "read_projection_version": READ_PROJECTION_VERSION,
        "proposal_id": proposal["id"],
        "decision_id": decision["id"],
        "revision_id": revision["id"],
        "first_execution": {
            "status": first.status,
            "effects": [effect.status for effect in first.effects],
        },
        "replay": {
            "status": replay.status,
            "effects": [effect.status for effect in replay.effects],
        },
        "bundle_counts": {key: len(records) for key, records in bundle.items()},
        "equipment_view": view,
        "assertions": {
            "bilingual_same_entity": True,
            "manufacturer_claim_visible": True,
            "legacy_operator_statement_excluded": True,
            "unknown_inventory_preserved": True,
            "unknown_service_state_preserved": True,
            "citation_chain_preserved": True,
            "backend_ids_excluded": True,
        },
        "claim_ceiling": (
            "This proves the bounded M1 canonical read projection and EquipmentView on the "
            "local clean stack. It does not qualify production hosting, scale, or concurrent writes."
        ),
    }
    OUTPUT.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
