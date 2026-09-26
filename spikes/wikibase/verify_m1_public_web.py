#!/usr/bin/env python3
"""Verify the M1 web shell against the clean-stack canonical EquipmentView artifact."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPIKE_DIR = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.presentation.public_web import create_public_wsgi_app  # noqa: E402

INPUT = SPIKE_DIR / "m1_public_projection.generated.json"
REPORT = SPIKE_DIR / "m1_public_web.generated.json"
API_OUTPUT = SPIKE_DIR / "m1_f15sa_api.generated.json"
AR_OUTPUT = SPIKE_DIR / "m1_f15sa_ar.generated.html"
EN_OUTPUT = SPIKE_DIR / "m1_f15sa_en.generated.html"
TARGET_ID = "SDA-EQUIP-F15SA"


def request(app, path: str) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": path}, start_response))
    return str(captured["status"]), dict(captured["headers"]), body


def main() -> int:
    for output in (REPORT, API_OUTPUT, AR_OUTPUT, EN_OUTPUT):
        if output.exists():
            raise SystemExit(f"reset the spike before rerunning public web verification: {output.name}")
    if not INPUT.exists():
        raise SystemExit(f"missing canonical public projection artifact: {INPUT.name}")

    evidence = json.loads(INPUT.read_text(encoding="utf-8"))
    if evidence.get("status") != "PASS":
        raise AssertionError("canonical public projection did not pass before web rendering")
    view = evidence["equipment_view"]
    if view.get("id") != TARGET_ID:
        raise AssertionError("unexpected EquipmentView identity")

    app = create_public_wsgi_app(
        lambda entity_id: view if entity_id == TARGET_ID else None,
        equipment_routes={"f-15sa": TARGET_ID},
    )

    api_status, api_headers, api_body = request(app, f"/api/equipment/{TARGET_ID}")
    ar_status, ar_headers, ar_body = request(app, "/ar/equipment/f-15sa")
    en_status, en_headers, en_body = request(app, "/en/equipment/f-15sa")
    if (api_status, ar_status, en_status) != ("200 OK", "200 OK", "200 OK"):
        raise AssertionError("one or more public M1 routes failed")
    if not api_headers["Content-Type"].startswith("application/json"):
        raise AssertionError("equipment API did not return JSON")
    if not ar_headers["Content-Type"].startswith("text/html") or not en_headers["Content-Type"].startswith("text/html"):
        raise AssertionError("localized equipment routes did not return HTML")

    api_view = json.loads(api_body)
    if api_view != view:
        raise AssertionError("public API mutated the canonical EquipmentView")

    ar = ar_body.decode("utf-8")
    en = en_body.decode("utf-8")
    assertions = {
        "same_canonical_view": api_view["id"] == TARGET_ID,
        "arabic_rtl": 'lang="ar"' in ar and 'dir="rtl"' in ar and "إف-15 إس إيه" in ar,
        "english_ltr": 'lang="en"' in en and 'dir="ltr"' in en and "F-15SA" in en,
        "localized_manufacturer": "بوينغ" in ar and "Boeing" in en,
        "language_switch": "/en/equipment/f-15sa" in ar and "/ar/equipment/f-15sa" in en,
        "explicit_unknowns": "غير معروف" in ar and "Unknown" in en,
        "citation_visible": "https://www.af.mil/" in ar and "https://www.af.mil/" in en,
        "timeline_visible": "2020-12-10" in ar and "2020-12-10" in en,
        "legacy_operator_excluded": view["field_states"]["operator"]["state"] == "unknown",
        "backend_ids_excluded": not re.search(
            r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])", ar + en
        ),
    }
    failed = [name for name, passed in assertions.items() if not passed]
    if failed:
        raise AssertionError("public web assertions failed: " + ", ".join(failed))

    API_OUTPUT.write_text(json.dumps(api_view, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    AR_OUTPUT.write_text(ar, encoding="utf-8")
    EN_OUTPUT.write_text(en, encoding="utf-8")
    report = {
        "status": "PASS",
        "entity_id": TARGET_ID,
        "routes": {
            "api": f"/api/equipment/{TARGET_ID}",
            "ar": "/ar/equipment/f-15sa",
            "en": "/en/equipment/f-15sa",
        },
        "assertions": assertions,
        "source_projection_report": INPUT.name,
        "claim_ceiling": (
            "Framework-neutral M1 web-shell proof only; frontend framework/deployment adoption "
            "remains subject to the Architecture Pattern Register."
        ),
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
