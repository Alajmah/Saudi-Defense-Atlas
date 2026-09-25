#!/usr/bin/env python3
"""Verify the bounded M0 Wikibase acceptance mechanics after seeding."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from wikibase_api import WikibaseAPI

ROOT = Path(__file__).resolve().parent
STATE_PATH = ROOT / "state.generated.json"
EVIDENCE_PATH = ROOT / "verification.generated.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def statement_by_guid(entity: dict[str, Any], guid: str) -> dict[str, Any]:
    for statements in entity.get("claims", {}).values():
        for statement in statements:
            if statement.get("id") == guid:
                return statement
    raise AssertionError(f"statement {guid} not found")


def qualifier_count(statement: dict[str, Any], property_id: str) -> int:
    return len(statement.get("qualifiers", {}).get(property_id, []))


def sparql_lookup(endpoint: str, base_url: str, property_id: str, canonical_id: str) -> list[dict[str, Any]]:
    query = f'''SELECT ?item WHERE {{
      ?item <{base_url.rstrip('/')}/prop/direct/{property_id}> "{canonical_id}" .
    }}'''
    last_error: Exception | None = None
    for _ in range(30):
        try:
            response = requests.get(
                endpoint,
                params={"query": query, "format": "json"},
                headers={"Accept": "application/sparql-results+json"},
                timeout=30,
            )
            response.raise_for_status()
            bindings = response.json().get("results", {}).get("bindings", [])
            if bindings:
                return bindings
        except Exception as exc:  # noqa: BLE001 - preserve final endpoint error for spike diagnostics.
            last_error = exc
        time.sleep(2)
    if last_error:
        raise AssertionError(f"SPARQL lookup failed: {last_error}") from last_error
    raise AssertionError("SPARQL updater did not expose the canonical ID within the verification window")


def main() -> int:
    require(STATE_PATH.exists(), "run seed.py first")
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))

    base_url = os.environ.get("WIKIBASE_URL", "http://localhost:8181")
    wdqs_url = os.environ.get(
        "WDQS_URL", "http://localhost:9999/bigdata/namespace/wdq/sparql"
    )
    username = os.environ.get("MW_ADMIN_NAME", "")
    password = os.environ.get("MW_ADMIN_PASS", "")
    require(bool(username and password), "MW_ADMIN_NAME and MW_ADMIN_PASS are required")

    api = WikibaseAPI(base_url, username, password)
    api.login()

    props = state["properties"]
    items = state["items"]
    claims = state["claims"]
    checks: dict[str, Any] = {}

    # 1. Arabic, English, and abbreviation resolve to the same entity.
    rsaf_qid = items["rsaf"]
    searches = {
        "en": api.search_entities("Royal Saudi Air Force", "en"),
        "ar": api.search_entities("القوات الجوية الملكية السعودية", "ar"),
        "alias": api.search_entities("RSAF", "en"),
    }
    for label, results in searches.items():
        require(any(row.get("id") == rsaf_qid for row in results), f"{label} search did not resolve RSAF")
    checks["bilingual_alias_resolution"] = {key: True for key in searches}

    # 2. Project identity remains separate from the Q-id.
    rsaf = api.get_entity(rsaf_qid)
    canonical_statements = rsaf.get("claims", {}).get(props["canonical_id"], [])
    require(canonical_statements, "RSAF has no SDA canonical ID statement")
    canonical_value = canonical_statements[0]["mainsnak"]["datavalue"]["value"]
    require(canonical_value == "SDA-ORG-RSAF", "unexpected RSAF domain ID")
    require(canonical_value != rsaf_qid, "store identity leaked into domain identity")
    checks["domain_vs_store_identity"] = {"sda_id": canonical_value, "wikibase_id": rsaf_qid}

    # 3. Historical quantity carries qualifiers and multiple references.
    f15sa = api.get_entity(items["f15sa"])
    f15_statement = statement_by_guid(f15sa, claims["f15sa.procurement_quantity"])
    require(qualifier_count(f15_statement, props["claim_id"]) == 1, "F-15 quantity missing claim ID qualifier")
    require(qualifier_count(f15_statement, props["quantity_type"]) == 1, "F-15 quantity missing quantity-type qualifier")
    require(qualifier_count(f15_statement, props["point_in_time"]) == 1, "F-15 quantity missing temporal qualifier")
    require(qualifier_count(f15_statement, props["confidence"]) == 1, "F-15 quantity missing confidence qualifier")
    require(len(f15_statement.get("references", [])) >= 2, "F-15 quantity did not preserve multiple references")
    checks["qualified_multi_reference_claim"] = True

    # 4. Synthetic contradictory quantities coexist rather than overwrite each other.
    synthetic = api.get_entity(items["synthetic_conflict"])
    qty_statements = synthetic.get("claims", {}).get(props["procurement_quantity"], [])
    require(len(qty_statements) == 2, "synthetic conflict fixture must contain exactly two quantity statements")
    values = sorted(
        statement["mainsnak"]["datavalue"]["value"]["amount"]
        for statement in qty_statements
    )
    require(values == ["+10", "+12"], f"unexpected synthetic conflict values: {values}")
    for statement in qty_statements:
        require(qualifier_count(statement, props["fixture_status"]) == 1, "synthetic conflict statement is not clearly marked")
    checks["conflicting_claim_coexistence"] = values

    # 5. Procurement approval semantics remain explicit; quantity is not encoded as contract/delivery.
    pac_event = api.get_entity(items["pac_event"])
    event_type_statements = pac_event.get("claims", {}).get(props["event_type"], [])
    require(event_type_statements, "PAC-3 MSE event type missing")
    event_type = event_type_statements[0]["mainsnak"]["datavalue"]["value"]
    require(event_type == "procurement_approval_or_notification", "PAC event semantics collapsed to another stage")
    checks["procurement_stage_separation"] = event_type

    # 6. MediaWiki revision history is visible and includes multiple writes.
    revisions = api.page_revisions(items["f15sa"])
    require(len(revisions) >= 3, "F-15SA item revision history is unexpectedly shallow")
    checks["revision_history"] = [revision.get("revid") for revision in revisions]

    # 7. Query-service lookup by project ID works.
    bindings = sparql_lookup(wdqs_url, base_url, props["canonical_id"], "SDA-ORG-RSAF")
    require(any(binding.get("item", {}).get("value", "").endswith(f"/entity/{rsaf_qid}") for binding in bindings), "SPARQL project-ID lookup returned the wrong entity")
    checks["sparql_query"] = True

    # 8. Raw API read path returns labels, aliases, claims.
    require(rsaf.get("labels", {}).get("ar", {}).get("value"), "Arabic label missing from API response")
    require(rsaf.get("labels", {}).get("en", {}).get("value"), "English label missing from API response")
    checks["action_api_read"] = True

    report = {
        "status": "PASS",
        "scope": "M0 local representational mechanics only",
        "checks": checks,
        "limitations": [
            "Does not establish production security, scaling, HA, backup, or recovery.",
            "Does not by itself authorize Wikibase adoption; ADR-0002 must evaluate the evidence.",
            "Synthetic conflict fixture is explicitly non-factual and non-public.",
        ],
    }
    EVIDENCE_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
