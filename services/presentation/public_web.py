"""Framework-neutral M1 public web shell over an EquipmentView provider.

This module deliberately uses only the Python standard library. It proves the
public contract without silently adopting a frontend framework before the APR
process selects one.
"""

from __future__ import annotations

import html
import json
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import unquote

EquipmentProvider = Callable[[str], Mapping[str, Any] | None]


def _text(localized: Any, locale: str) -> str:
    if not isinstance(localized, Mapping):
        return ""
    preferred = localized.get(locale)
    if isinstance(preferred, str) and preferred:
        return preferred
    for fallback in ("ar", "en"):
        value = localized.get(fallback)
        if isinstance(value, str) and value:
            return value
    return ""


def _labels(locale: str) -> dict[str, str]:
    if locale == "ar":
        return {
            "manufacturer": "المُصنّع",
            "operator": "المشغّل",
            "inventory_quantity": "الكمية في المخزون",
            "service_state": "حالة الخدمة",
            "unknown": "غير معروف",
            "disputed": "متنازع عليه",
            "facts": "الحقائق الموثقة",
            "timeline": "الخط الزمني",
            "related": "كيانات مرتبطة",
            "sources": "المصادر",
            "source": "المصدر",
            "switch": "English",
            "delivery": "تسليم",
        }
    return {
        "manufacturer": "Manufacturer",
        "operator": "Operator",
        "inventory_quantity": "Inventory quantity",
        "service_state": "Service state",
        "unknown": "Unknown",
        "disputed": "Disputed",
        "facts": "Documented facts",
        "timeline": "Timeline",
        "related": "Related entities",
        "sources": "Sources",
        "source": "Source",
        "switch": "العربية",
        "delivery": "Delivery",
    }


def _field_value(view: Mapping[str, Any], field: str, locale: str) -> str:
    labels = _labels(locale)
    state = view.get("field_states", {}).get(field, {})
    state_name = state.get("state")
    if state_name == "unknown":
        return labels["unknown"]
    if state_name == "disputed":
        return labels["disputed"]

    claim_ids = set(state.get("claim_ids") or [])
    for fact in view.get("facts", []):
        if fact.get("claim_id") not in claim_ids:
            continue
        value = fact.get("value")
        if isinstance(value, Mapping) and value.get("kind") == "entity":
            entity_id = value.get("entity_id")
            for related in view.get("related_entities", []):
                if related.get("id") == entity_id:
                    return _text(related.get("names"), locale) or str(entity_id)
        if isinstance(value, Mapping) and "value" in value:
            return str(value["value"])
    return labels["unknown"]


def _citation_html(citation: Mapping[str, Any], locale: str) -> str:
    publisher = html.escape(_text(citation.get("publisher"), locale) or str(citation.get("source_id", "")))
    document = html.escape(_text(citation.get("document_title"), locale))
    label = document or publisher
    url = citation.get("url")
    if isinstance(url, str) and url:
        rendered = f'<a href="{html.escape(url, quote=True)}" rel="nofollow noopener">{label}</a>'
    else:
        rendered = label
    locator = citation.get("locator")
    selector = locator.get("selector") if isinstance(locator, Mapping) else None
    suffix = f" — {html.escape(str(selector))}" if selector else ""
    return f"{rendered}{suffix}"


def render_equipment_page(
    view: Mapping[str, Any], *, locale: str, slug: str = "f-15sa"
) -> str:
    if locale not in {"ar", "en"}:
        raise ValueError("locale must be 'ar' or 'en'")
    labels = _labels(locale)
    direction = "rtl" if locale == "ar" else "ltr"
    opposite = "en" if locale == "ar" else "ar"
    title = html.escape(_text(view.get("names"), locale) or str(view.get("id", "")))
    aliases = view.get("aliases", {}).get(locale, []) if isinstance(view.get("aliases"), Mapping) else []
    alias_line = ", ".join(html.escape(str(value)) for value in aliases)

    fields = "".join(
        f"<dt>{html.escape(labels[field])}</dt><dd>{html.escape(_field_value(view, field, locale))}</dd>"
        for field in ("manufacturer", "operator", "inventory_quantity", "service_state")
    )

    facts: list[str] = []
    for fact in view.get("facts", []):
        citations = "".join(
            f"<li>{_citation_html(citation, locale)}</li>"
            for citation in fact.get("citations", [])
        )
        facts.append(
            "<article class=\"fact\">"
            f"<code>{html.escape(str(fact.get('predicate_id', '')))}</code>"
            f"<p>{html.escape(str(fact.get('claim_state', '')))} · {html.escape(str(fact.get('confidence', '')))}</p>"
            f"<ul class=\"citations\">{citations}</ul>"
            "</article>"
        )

    events: list[str] = []
    for event in view.get("events", []):
        occurred = event.get("occurred_at", {})
        date = occurred.get("value", "") if isinstance(occurred, Mapping) else ""
        participants = ", ".join(
            f"{html.escape(_text(item.get('names'), locale) or str(item.get('entity_id', '')))} ({html.escape(str(item.get('role', '')))})"
            for item in event.get("participants", [])
        )
        citations = "".join(
            f"<li>{_citation_html(citation, locale)}</li>"
            for citation in event.get("citations", [])
        )
        event_type = labels.get(str(event.get("event_type")), str(event.get("event_type", "")))
        events.append(
            "<article class=\"event\">"
            f"<time>{html.escape(str(date))}</time> — <strong>{html.escape(event_type)}</strong>"
            f"<p>{participants}</p><ul class=\"citations\">{citations}</ul>"
            "</article>"
        )

    related = "".join(
        f"<li data-sda-id=\"{html.escape(str(entity.get('id', '')), quote=True)}\">{html.escape(_text(entity.get('names'), locale) or str(entity.get('id', '')))}</li>"
        for entity in view.get("related_entities", [])
    )

    description = _text(view.get("descriptions"), locale)
    return f"""<!doctype html>
<html lang="{locale}" dir="{direction}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Saudi Defense Atlas</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:960px;margin:0 auto;padding:2rem;line-height:1.6}}header{{display:flex;justify-content:space-between;gap:1rem;align-items:start}}dl{{display:grid;grid-template-columns:minmax(10rem,1fr) 2fr;gap:.5rem 1rem}}dt{{font-weight:700}}dd{{margin:0}}article{{border-top:1px solid #ccc;padding:1rem 0}}code{{direction:ltr;unicode-bidi:isolate}}.muted{{opacity:.7}}a{{text-underline-offset:.2em}}
</style>
</head>
<body data-sda-id="{html.escape(str(view.get('id', '')), quote=True)}">
<header><div><h1>{title}</h1><p class="muted">{html.escape(description)}</p><p>{alias_line}</p></div><nav><a href="/{opposite}/equipment/{html.escape(slug, quote=True)}">{html.escape(labels['switch'])}</a></nav></header>
<main>
<section><dl>{fields}</dl></section>
<section><h2>{html.escape(labels['facts'])}</h2>{''.join(facts)}</section>
<section><h2>{html.escape(labels['timeline'])}</h2>{''.join(events)}</section>
<section><h2>{html.escape(labels['related'])}</h2><ul>{related}</ul></section>
</main>
</body>
</html>"""


def create_public_wsgi_app(
    provider: EquipmentProvider, *, equipment_routes: Mapping[str, str]
):
    """Return a tiny WSGI app exposing the M1 API and bilingual equipment page."""

    def app(environ: Mapping[str, Any], start_response):
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = unquote(str(environ.get("PATH_INFO", "/")))
        if method != "GET":
            start_response("405 Method Not Allowed", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Method Not Allowed"]

        if path.startswith("/api/equipment/"):
            entity_id = path.removeprefix("/api/equipment/")
            view = provider(entity_id)
            if view is None:
                start_response("404 Not Found", [("Content-Type", "application/json; charset=utf-8")])
                return [b'{"error":"not_found"}']
            body = json.dumps(view, ensure_ascii=False, sort_keys=True).encode("utf-8")
            start_response(
                "200 OK",
                [
                    ("Content-Type", "application/json; charset=utf-8"),
                    ("Cache-Control", "public, max-age=60"),
                ],
            )
            return [body]

        parts = [part for part in path.split("/") if part]
        if len(parts) == 3 and parts[0] in {"ar", "en"} and parts[1] == "equipment":
            locale, slug = parts[0], parts[2]
            entity_id = equipment_routes.get(slug)
            view = provider(entity_id) if entity_id else None
            if view is None:
                start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
                return [b"Not Found"]
            body = render_equipment_page(view, locale=locale, slug=slug).encode("utf-8")
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
