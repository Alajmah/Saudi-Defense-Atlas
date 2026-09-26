"""Framework-neutral public API/page shell for RelationshipGraphView."""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import unquote

from .relationship_visualization import render_relationship_figure

RelationshipProvider = Callable[[str], Mapping[str, Any] | None]


def create_relationship_wsgi_app(
    provider: RelationshipProvider,
    *,
    relationship_routes: Mapping[str, str],
):
    """Return a tiny WSGI app for relationship JSON and bilingual visualization pages."""

    def app(environ: Mapping[str, Any], start_response):
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = unquote(str(environ.get("PATH_INFO", "/")))
        if method != "GET":
            start_response("405 Method Not Allowed", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Method Not Allowed"]

        if path.startswith("/api/relationships/"):
            entity_id = path.removeprefix("/api/relationships/")
            graph = provider(entity_id)
            if graph is None:
                start_response("404 Not Found", [("Content-Type", "application/json; charset=utf-8")])
                return [b'{"error":"not_found"}']
            body = json.dumps(graph, ensure_ascii=False, sort_keys=True).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Cache-Control", "public, max-age=60"),
                ],
            )
            return [body]

        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[0] in {"ar", "en"} and parts[1] == "relationships":
            locale, slug = parts[0], parts[2]
            entity_id = relationship_routes.get(slug)
            graph = provider(entity_id) if entity_id else None
            if graph is None:
                start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
                return [b"Not Found"]
            direction = "rtl" if locale == "ar" else "ltr"
            opposite = "en" if locale == "ar" else "ar"
            switch_label = "English" if locale == "ar" else "العربية"
            title = "شبكة العلاقات" if locale == "ar" else "Relationship graph"
            figure = render_relationship_figure(graph, locale=locale)
            body = f"""<!doctype html>
<html lang="{locale}" dir="{direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(title)} — Saudi Defense Atlas</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:2rem;line-height:1.6}}
header{{display:flex;justify-content:space-between;gap:1rem;align-items:start}}
.relationship-figure{{margin:2rem 0}}.relationship-fallback{{margin-top:1rem}}code{{direction:ltr;unicode-bidi:isolate}}
a{{text-underline-offset:.2em}}
</style>
</head>
<body>
<header><h1>{html.escape(title)}</h1><nav><a href="/{opposite}/relationships/{html.escape(slug, quote=True)}">{html.escape(switch_label)}</a></nav></header>
<main>{figure}</main>
</body>
</html>""".encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "text/html; charset=utf-8"),
                    ("Cache-Control", "public, max-age=60"),
                ],
            )
            return [body]

        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"Not Found"]

    return app
