#!/usr/bin/env python3
"""Apply one human-approved synthetic ChangeProposal to the Wikibase spike.

This is intentionally a narrow adapter proof. It demonstrates that the backend
write occurs only after project schemas and cross-record governance authorize the
exact proposal/decision pair. It is not the general M1 canonical adapter.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SPIKE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from scripts.validate_schemas import build_registry  # noqa: E402
from scripts.validate_workflow import validate_case  # noqa: E402
from seed import qualify, reference_snaks  # noqa: E402
from wikibase_api import WikibaseAPI, quantity_value  # noqa: E402

BUNDLE_PATH = SPIKE_DIR / "approved-demo-bundle.json"
STATE_PATH = SPIKE_DIR / "state.generated.json"
OUTPUT_PATH = SPIKE_DIR / "approved-demo-applied.generated.json"


class AdapterAuthorizationError(RuntimeError):
    pass


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
        raise AdapterAuthorizationError(
            f"{schema_name} validation failed: {rendered}"
        )


def authorize(proposal: dict[str, Any], decision: dict[str, Any]) -> None:
    validate_schema("change-proposal.schema.json", proposal)
    validate_schema("review-decision.schema.json", decision)

    workflow_errors = validate_case(
        {"proposal": proposal, "decision": decision, "revision": None}
    )
    if workflow_errors:
        raise AdapterAuthorizationError("; ".join(workflow_errors))

    if decision["decision"] != "approve":
        raise AdapterAuthorizationError("adapter accepts only an approved proposal")

    if decision["proposal_id"] != proposal["id"]:
        raise AdapterAuthorizationError("decision does not bind to the exact proposal")


def canonical_sha256(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def main() -> int:
    if OUTPUT_PATH.exists():
        raise SystemExit(
            "approved-demo-applied.generated.json already exists; reset the spike before rerunning"
        )
    if not STATE_PATH.exists():
        raise SystemExit("run seed.py before apply_approved_demo.py")

    bundle = json.loads(BUNDLE_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    proposal = bundle["proposal"]
    decision = bundle["decision"]

    # No backend call is allowed before this gate succeeds.
    authorize(proposal, decision)

    mutations = proposal["mutations"]
    if len(mutations) != 1:
        raise AdapterAuthorizationError("M0 demo supports exactly one mutation")

    mutation = mutations[0]
    claim = mutation["payload"]
    if mutation["resource_type"] != "claim" or mutation["action"] != "create":
        raise AdapterAuthorizationError("M0 demo supports only claim creation")
    if claim["subject_id"] != "SDA-TEST-CONFLICT-001":
        raise AdapterAuthorizationError("M0 demo may write only to the synthetic fixture")
    if claim["predicate_id"] != "procurement.quantity":
        raise AdapterAuthorizationError("M0 demo supports only procurement.quantity")
    if claim["value"]["kind"] != "number":
        raise AdapterAuthorizationError("M0 demo quantity must be numeric")

    base_url = os.environ.get("WIKIBASE_URL", "http://localhost:8181")
    username = os.environ.get("MW_ADMIN_NAME", "")
    password = os.environ.get("MW_ADMIN_PASS", "")
    if not username or not password:
        raise SystemExit("MW_ADMIN_NAME and MW_ADMIN_PASS are required")

    api = WikibaseAPI(base_url, username, password)
    api.login()

    props: dict[str, str] = state["properties"]
    subject_qid = state["items"]["synthetic_conflict"]

    statement_guid = api.add_claim(
        subject_qid,
        props["procurement_quantity"],
        quantity_value(claim["value"]["value"]),
        summary=(
            "SDA M0: apply human-approved synthetic proposal "
            f"{proposal['id']}"
        ),
    )

    point = claim.get("validity", {}).get("point_in_time", {}).get("value")
    quantity_type = claim.get("scope", {}).get("quantity_type")
    qualify(
        api,
        props,
        statement_guid,
        claim["id"],
        confidence=claim["confidence"],
        point=point,
        quantity_type=quantity_type,
        fixture_status="SYNTHETIC_NON_PUBLIC",
    )

    demo_reference = bundle["demo_reference"]
    api.add_reference(
        statement_guid,
        reference_snaks(
            api,
            props,
            demo_reference["document_id"],
            demo_reference["url"],
            demo_reference["locator"],
        ),
    )

    revisions = api.page_revisions(subject_qid, limit=5)
    if not revisions:
        raise RuntimeError("backend write succeeded but no MediaWiki revision was visible")
    backend_revision_id = revisions[0].get("revid")

    revision = {
        "id": bundle["revision_id"],
        "proposal_id": proposal["id"],
        "decision_id": decision["id"],
        "applied_at": utc_now(),
        "applied_by": {"kind": "system", "id": "wikibase-m0-adapter"},
        "affected_records": [
            {
                "resource_type": "claim",
                "record_id": claim["id"],
                "action": "created",
                "payload_sha256": canonical_sha256(claim),
            }
        ],
        "backend_receipts": [
            {
                "backend": "wikibase",
                "receipt": (
                    f"item={subject_qid};statement={statement_guid};"
                    f"mediawiki_revision={backend_revision_id}"
                ),
            }
        ],
        "rationale": "Synthetic M0 approval-gate adapter proof only.",
    }

    validate_schema("revision.schema.json", revision)
    workflow_errors = validate_case(
        {"proposal": proposal, "decision": decision, "revision": revision}
    )
    if workflow_errors:
        raise RuntimeError(
            "post-write project revision failed governance validation: "
            + "; ".join(workflow_errors)
        )

    output = {
        "status": "PASS",
        "proposal_id": proposal["id"],
        "decision_id": decision["id"],
        "statement_guid": statement_guid,
        "revision": revision,
        "claim_ceiling": (
            "The tested approved synthetic proposal was gated before one local "
            "Wikibase write; this is not a production authorization result."
        ),
    }
    OUTPUT_PATH.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
