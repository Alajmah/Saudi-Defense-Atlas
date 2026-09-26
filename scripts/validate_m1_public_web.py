#!/usr/bin/env python3
"""Validate the framework-neutral M1 API and bilingual public equipment pages."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m1_equipment_view import canonical_records  # noqa: E402
from services.presentation.equipment_view import build_equipment_view  # noqa: E402
from services.presentation.public_web import create_public_wsgi_app  # noqa: E402

TARGET_ID = "SDA-EQUIP-F15SA"


def request(app, path: str) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": path}, start_response))
    return str(captured["status"]), dict(captured["headers"]), body


def main() -> int:
    records = canonical_records()
    view = build_equipment_view(
        entity_id=TARGET_ID,
        **records,
        projected_at="2026-01-07T00:06:00Z",
        revision_ids=["SDA-REVISION-M1-PUBLIC-WEB-TEST"],
    )
    app = create_public_wsgi_app(
        lambda entity_id: view if entity_id == TARGET_ID else None,
        equipment_routes={"f-15sa": TARGET_ID},
    )

    status, headers, body = request(app, f"/api/equipment/{TARGET_ID}")
    if status != "200 OK" or not headers["Content-Type"].startswith("application/json"):
        raise AssertionError("equipment API did not return typed JSON")
    api_view = json.loads(body)
    if api_view != view:
        raise AssertionError("equipment API changed the canonical EquipmentView")

    ar_status, _, ar_body = request(app, "/ar/equipment/f-15sa")
    en_status, _, en_body = request(app, "/en/equipment/f-15sa")
    if ar_status != "200 OK" or en_status != "200 OK":
        raise AssertionError("bilingual public routes are not both available")
    ar = ar_body.decode("utf-8")
    en = en_body.decode("utf-8")

    required_ar = [
        'lang="ar"',
        'dir="rtl"',
        "إف-15 إس إيه",
        "بوينغ",
        "غير معروف",
        "/en/equipment/f-15sa",
        "SDA-EQUIP-F15SA",
    ]
    required_en = [
        'lang="en"',
        'dir="ltr"',
        "F-15SA",
        "Boeing",
        "Unknown",
        "/ar/equipment/f-15sa",
        "SDA-EQUIP-F15SA",
    ]
    if any(value not in ar for value in required_ar):
        raise AssertionError("Arabic equipment page lost a required M1 public element")
    if any(value not in en for value in required_en):
        raise AssertionError("English equipment page lost a required M1 public element")

    for rendered in (ar, en):
        if "https://www.af.mil/" not in rendered:
            raise AssertionError("public page lost visible source citation")
        if "2020-12-10" not in rendered:
            raise AssertionError("public page lost delivery timeline date")
        if re.search(r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])", rendered):
            raise AssertionError("backend Wikibase identifier leaked into public HTML")

    missing_status, _, _ = request(app, "/api/equipment/SDA-EQUIP-NOT-FOUND")
    if missing_status != "404 Not Found":
        raise AssertionError("unknown SDA equipment ID must return 404")

    print(
        "Validated M1 web shell: SDA-ID JSON API, Arabic/English pages from one "
        "EquipmentView, localized manufacturer, visible citations/timeline, explicit "
        "unknowns, and no Q/P leakage."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
