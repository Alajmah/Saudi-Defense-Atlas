"""Deterministic accessible inline-SVG visualization for RelationshipGraphView.

This renderer is deliberately small and framework-neutral. It consumes the
already-bounded public graph projection and never creates new graph semantics.
"""

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from typing import Any

from .equipment_view import ProjectionError


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
            "title": "شبكة العلاقات",
            "description": "عرض بصري لعلاقات موثقة ضمن أطلس الدفاع السعودي",
            "fallback": "العلاقات كنص",
            "source": "المصدر",
        }
    return {
        "title": "Relationship graph",
        "description": "Visual view of documented relationships in Saudi Defense Atlas",
        "fallback": "Relationships as text",
        "source": "Source",
    }


def _citation_html(citation: Mapping[str, Any], locale: str) -> str:
    publisher = html.escape(
        _text(citation.get("publisher"), locale) or str(citation.get("source_id", ""))
    )
    document = html.escape(_text(citation.get("document_title"), locale))
    label = document or publisher
    url = citation.get("url")
    if isinstance(url, str) and url:
        return (
            f'<a href="{html.escape(url, quote=True)}" rel="nofollow noopener">'
            f"{label}</a>"
        )
    return label


def _node_label(node: Mapping[str, Any], locale: str) -> str:
    label = _text(node.get("names"), locale)
    return label or str(node.get("id", ""))


def _positions(graph: Mapping[str, Any]) -> tuple[dict[str, tuple[int, int]], int]:
    scope = graph.get("scope")
    nodes = graph.get("nodes")
    if not isinstance(scope, Mapping):
        raise ProjectionError("relationship visualization requires graph scope")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ProjectionError("relationship visualization requires graph nodes")

    root_values = scope.get("root_entity_ids")
    if not isinstance(root_values, Sequence) or isinstance(root_values, (str, bytes)):
        raise ProjectionError("relationship visualization requires root_entity_ids")
    roots = {value for value in root_values if isinstance(value, str) and value}
    if not roots:
        raise ProjectionError("relationship visualization requires at least one root Entity")

    node_by_id: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ProjectionError("relationship visualization node must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ProjectionError("relationship visualization node requires canonical ID")
        if node_id in node_by_id:
            raise ProjectionError(f"duplicate visualization node ID: {node_id}")
        node_by_id[node_id] = node

    missing_roots = sorted(roots - set(node_by_id))
    if missing_roots:
        raise ProjectionError(
            "relationship visualization has missing root nodes: " + ", ".join(missing_roots)
        )

    root_nodes = sorted(roots)
    event_nodes = sorted(
        node_id
        for node_id, node in node_by_id.items()
        if node.get("node_kind") == "event"
    )
    related_nodes = sorted(set(node_by_id) - set(root_nodes) - set(event_nodes))

    largest_column = max(len(root_nodes), len(event_nodes), len(related_nodes), 1)
    height = max(320, 100 + largest_column * 100)

    def column_positions(ids: list[str], x: int) -> dict[str, tuple[int, int]]:
        if not ids:
            return {}
        step = height // (len(ids) + 1)
        return {node_id: (x, step * (index + 1)) for index, node_id in enumerate(ids)}

    positions: dict[str, tuple[int, int]] = {}
    positions.update(column_positions(root_nodes, 130))
    positions.update(column_positions(event_nodes, 480))
    positions.update(column_positions(related_nodes, 830))
    return positions, height


def render_relationship_figure(graph: Mapping[str, Any], *, locale: str) -> str:
    """Render an accessible SVG plus semantic HTML fallback for one bounded graph."""

    if locale not in {"ar", "en"}:
        raise ValueError("locale must be 'ar' or 'en'")
    labels = _labels(locale)
    direction = "rtl" if locale == "ar" else "ltr"

    nodes = graph.get("nodes")
    edges = graph.get("edges")
    if not isinstance(nodes, Sequence) or isinstance(nodes, (str, bytes)):
        raise ProjectionError("relationship visualization requires nodes")
    if not isinstance(edges, Sequence) or isinstance(edges, (str, bytes)):
        raise ProjectionError("relationship visualization requires edges")

    node_by_id: dict[str, Mapping[str, Any]] = {}
    for node in nodes:
        if not isinstance(node, Mapping):
            raise ProjectionError("relationship visualization node must be an object")
        node_id = node.get("id")
        if not isinstance(node_id, str) or not node_id:
            raise ProjectionError("relationship visualization node requires canonical ID")
        if node_id in node_by_id:
            raise ProjectionError(f"duplicate visualization node ID: {node_id}")
        node_by_id[node_id] = node

    positions, height = _positions(graph)
    root_ids = set(graph["scope"]["root_entity_ids"])

    rendered_edges: list[str] = []
    fallback_edges: list[str] = []
    seen_edges: set[str] = set()
    for edge in sorted(edges, key=lambda item: str(item.get("id", "")) if isinstance(item, Mapping) else ""):
        if not isinstance(edge, Mapping):
            raise ProjectionError("relationship visualization edge must be an object")
        edge_id = edge.get("id")
        from_id = edge.get("from_id")
        to_id = edge.get("to_id")
        relation = edge.get("relation")
        source_record_id = edge.get("source_record_id")
        if not all(isinstance(value, str) and value for value in (edge_id, from_id, to_id, relation, source_record_id)):
            raise ProjectionError("relationship visualization edge is missing required identity")
        if edge_id in seen_edges:
            raise ProjectionError(f"duplicate visualization edge ID: {edge_id}")
        seen_edges.add(edge_id)
        if from_id not in positions or to_id not in positions:
            raise ProjectionError(f"visualization edge {edge_id} references a missing node")

        x1, y1 = positions[from_id]
        x2, y2 = positions[to_id]
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        rendered_edges.append(
            f'<g class="relationship-edge" data-source-record-id="{html.escape(source_record_id, quote=True)}">'
            f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" marker-end="url(#sda-arrow)" />'
            f'<text x="{mx}" y="{my - 8}" text-anchor="middle" direction="ltr">{html.escape(relation)}</text>'
            "</g>"
        )

        citations = edge.get("citations")
        if not isinstance(citations, Sequence) or isinstance(citations, (str, bytes)) or not citations:
            raise ProjectionError(f"visualization edge {edge_id} requires citations")
        rendered_citations: list[str] = []
        for citation in citations:
            if not isinstance(citation, Mapping):
                raise ProjectionError(f"visualization edge {edge_id} has malformed citation")
            rendered_citations.append(_citation_html(citation, locale))
        citation_text = "; ".join(rendered_citations)
        fallback_edges.append(
            "<li "
            f'data-source-record-id="{html.escape(source_record_id, quote=True)}">'
            f'<strong>{html.escape(_node_label(node_by_id[from_id], locale))}</strong> '
            f'<code>{html.escape(relation)}</code> '
            f'<strong>{html.escape(_node_label(node_by_id[to_id], locale))}</strong> '
            f'— {html.escape(labels["source"])}: {citation_text}</li>'
        )

    rendered_nodes: list[str] = []
    for node_id in sorted(node_by_id):
        node = node_by_id[node_id]
        x, y = positions[node_id]
        node_kind = str(node.get("node_kind", ""))
        css_class = "root" if node_id in root_ids else node_kind
        label = html.escape(_node_label(node, locale))
        rendered_nodes.append(
            f'<g class="relationship-node {html.escape(css_class, quote=True)}" '
            f'data-sda-id="{html.escape(node_id, quote=True)}" transform="translate({x} {y})">'
            '<rect x="-105" y="-28" width="210" height="56" rx="10" />'
            f'<text text-anchor="middle" dominant-baseline="middle" direction="{direction}">{label}</text>'
            "</g>"
        )

    svg_title = html.escape(labels["title"])
    svg_desc = html.escape(labels["description"])
    return (
        f'<figure class="relationship-figure" dir="{direction}">'
        f'<svg class="relationship-svg" viewBox="0 0 960 {height}" role="img" '
        'aria-labelledby="sda-relationship-title sda-relationship-desc" '
        'xmlns="http://www.w3.org/2000/svg">'
        f'<title id="sda-relationship-title">{svg_title}</title>'
        f'<desc id="sda-relationship-desc">{svg_desc}</desc>'
        '<defs><marker id="sda-arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">'
        '<path d="M0,0 L8,4 L0,8 z" /></marker></defs>'
        '<style>.relationship-svg{width:100%;height:auto}.relationship-edge line{stroke:currentColor;stroke-width:1.5}.relationship-edge text{font:11px system-ui,sans-serif}.relationship-node rect{fill:white;stroke:currentColor;stroke-width:1.5}.relationship-node.root rect{stroke-width:3}.relationship-node.event rect{stroke-dasharray:5 3}.relationship-node text{font:13px system-ui,sans-serif}</style>'
        f'{"".join(rendered_edges)}{"".join(rendered_nodes)}'
        '</svg>'
        f'<figcaption><strong>{svg_title}</strong></figcaption>'
        f'<details class="relationship-fallback"><summary>{html.escape(labels["fallback"])}</summary>'
        f'<ul>{"".join(fallback_edges)}</ul></details>'
        '</figure>'
    )
