#!/usr/bin/env python3
"""Validate the bounded M2 relationship visualization trial and public routes."""

from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.validate_m2_relationship_graph import graph_records  # noqa: E402
from services.presentation.equipment_view import ProjectionError  # noqa: E402
from services.presentation.relationship_graph import build_relationship_graph  # noqa: E402
from services.presentation.relationship_visualization import render_relationship_figure  # noqa: E402
from services.presentation.relationship_web import create_relationship_wsgi_app  # noqa: E402

TARGET_ID = "SDA-EQUIP-F15SA"


def request(app, path: str) -> tuple[str, dict[str, str], bytes]:
    captured: dict[str, object] = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": path}, start_response))
    return str(captured["status"]), dict(captured["headers"]), body


def main() -> int:
    records = graph_records()
    graph = build_relationship_graph(
        root_entity_ids=[TARGET_ID],
        **records,
        projected_at="2026-01-12T01:00:00Z",
        revision_ids=["SDA-REVISION-M2-VISUALIZATION-TEST"],
    )

    en = render_relationship_figure(graph, locale="en")
    ar = render_relationship_figure(graph, locale="ar")

    for rendered in (en, ar):
        if '<svg class="relationship-svg"' not in rendered:
            raise AssertionError("relationship visualization lost inline SVG")
        if 'role="img"' not in rendered or "<title" not in rendered or "<desc" not in rendered:
            raise AssertionError("relationship SVG lost accessible title/description")
        if '<details class="relationship-fallback">' not in rendered:
            raise AssertionError("relationship visualization lost semantic HTML fallback")
        if TARGET_ID not in rendered:
            raise AssertionError("relationship visualization lost root SDA identity")
        if "data-source-record-id=" not in rendered:
            raise AssertionError("relationship visualization lost source-record identity")
        if "example.invalid" not in rendered and "www.af.mil" not in rendered:
            raise AssertionError("relationship fallback lost visible citation links")
        if "Q999" in rendered or "backend_identifiers" in rendered:
            raise AssertionError("backend identifier leaked into relationship visualization")
        if re.search(r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])", rendered):
            raise AssertionError("Wikibase Q/P identifier leaked into relationship visualization")

    if "Relationship graph" not in en or "شبكة العلاقات" not in ar:
        raise AssertionError("relationship visualization lost bilingual heading")
    if "F-15SA" not in en or "إف-15 إس إيه" not in ar:
        raise AssertionError("relationship visualization lost localized root label")
    if "manufactures" not in en or "يصنّع" not in ar:
        raise AssertionError("relationship visualization lost localized relationship label")
    if "manufacturer.manufactures.equipment" not in ar:
        raise AssertionError("Arabic fallback lost canonical relationship code for auditability")
    if 'id="sda-relationship-title"' in en or 'id="sda-arrow"' in en:
        raise AssertionError("SVG accessibility/marker IDs must be graph-scoped, not global constants")

    # Rendering must be deterministic even if graph record arrays arrive reordered.
    reordered = copy.deepcopy(graph)
    reordered["nodes"].reverse()
    reordered["edges"].reverse()
    if render_relationship_figure(reordered, locale="en") != en:
        raise AssertionError("relationship SVG/HTML output depends on graph input order")

    # A material edge may not be visualized from contextual/contradicting evidence alone.
    unsupported = copy.deepcopy(graph)
    if not unsupported["edges"]:
        raise AssertionError("visualization fixture unexpectedly has no edges")
    unsupported["edges"][0]["citations"] = [
        {**citation, "evidence_role": "contextualizes"}
        for citation in unsupported["edges"][0]["citations"]
    ]
    try:
        render_relationship_figure(unsupported, locale="en")
        raise AssertionError("relationship visualization admitted an edge without supporting Evidence")
    except ProjectionError:
        pass

    app = create_relationship_wsgi_app(
        lambda entity_id: graph if entity_id == TARGET_ID else None,
        relationship_routes={"f-15sa": TARGET_ID},
    )

    api_status, api_headers, api_body = request(app, f"/api/relationships/{TARGET_ID}")
    if api_status != "200 OK" or not api_headers["Content-Type"].startswith("application/json"):
        raise AssertionError("relationship API did not return JSON")
    if json.loads(api_body) != graph:
        raise AssertionError("relationship API mutated the canonical public graph view")

    ar_status, _, ar_body = request(app, "/ar/relationships/f-15sa")
    en_status, _, en_body = request(app, "/en/relationships/f-15sa")
    if ar_status != "200 OK" or en_status != "200 OK":
        raise AssertionError("bilingual relationship visualization routes are unavailable")
    ar_page = ar_body.decode("utf-8")
    en_page = en_body.decode("utf-8")
    for required in ('lang="ar"', 'dir="rtl"', "/en/relationships/f-15sa", "شبكة العلاقات"):
        if required not in ar_page:
            raise AssertionError(f"Arabic relationship page lost required element: {required}")
    for required in ('lang="en"', 'dir="ltr"', "/ar/relationships/f-15sa", "Relationship graph"):
        if required not in en_page:
            raise AssertionError(f"English relationship page lost required element: {required}")

    missing_status, _, _ = request(app, "/api/relationships/SDA-EQUIP-NOT-FOUND")
    if missing_status != "404 Not Found":
        raise AssertionError("unknown relationship root must return 404")

    print(
        "Validated M2 first relationship visualization: deterministic inline SVG, localized "
        "relation labels with canonical audit codes, graph-scoped accessibility IDs, "
        "supporting-Evidence enforcement, semantic cited fallback, bilingual routes, SDA "
        "identity, and no backend-ID leakage or graph mutation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
