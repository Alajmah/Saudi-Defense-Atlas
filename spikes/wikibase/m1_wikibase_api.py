"""M1-only Wikibase helpers layered over the verified M0 Action API client."""

from __future__ import annotations

import json
import re
from typing import Any

from wikibase_api import CreatedEntity, WikibaseAPI


class M1WikibaseAPI(WikibaseAPI):
    """Add atomic writes and strongly consistent item lookup for the M1 spike."""

    def create_item_with_statements(
        self,
        *,
        labels: dict[str, str],
        statements: list[dict[str, Any]],
        summary: str,
    ) -> CreatedEntity:
        data = {
            "labels": self._language_values(labels),
            "claims": statements,
        }
        result = self.post(
            action="wbeditentity",
            new="item",
            data=json.dumps(data, ensure_ascii=False),
            token=self._token(),
            summary=summary,
        )
        entity = result["entity"]
        return CreatedEntity(entity["id"], entity.get("lastrevid"))

    def add_statement_bundle(
        self,
        *,
        entity_id: str,
        statement: dict[str, Any],
        summary: str,
    ) -> CreatedEntity:
        result = self.post(
            action="wbeditentity",
            id=entity_id,
            data=json.dumps({"claims": [statement]}, ensure_ascii=False),
            token=self._token(),
            summary=summary,
        )
        entity = result["entity"]
        return CreatedEntity(entity["id"], entity.get("lastrevid"))

    @staticmethod
    def statement(
        mainsnak: dict[str, Any],
        *,
        qualifiers: dict[str, list[dict[str, Any]]] | None = None,
        references: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "mainsnak": mainsnak,
            "type": "statement",
            "rank": "normal",
        }
        if qualifiers:
            result["qualifiers"] = qualifiers
            result["qualifiers-order"] = list(qualifiers.keys())
        if references:
            normalized = []
            for reference in references:
                snaks = reference["snaks"]
                normalized.append(
                    {"snaks": snaks, "snaks-order": list(snaks.keys())}
                )
            result["references"] = normalized
        return result

    def item_namespace_id(self) -> int:
        """Return the MediaWiki namespace that stores Wikibase Items.

        The local stack exposes Items through an explicit ``Item:`` namespace,
        while other Wikibase deployments may use main namespace 0. Discover the
        configured Item namespace from current Action API siteinfo and fall back
        to namespace 0 only when no explicit Item namespace is registered.
        """
        data = self.get(action="query", meta="siteinfo", siprop="namespaces")
        namespaces = data.get("query", {}).get("namespaces", {})
        for raw_id, definition in namespaces.items():
            if not isinstance(definition, dict):
                continue
            names = {
                str(definition.get("canonical", "")).casefold(),
                str(definition.get("*", "")).casefold(),
            }
            if "item" in names:
                return int(definition.get("id", raw_id))
        return 0

    @staticmethod
    def _entity_id_from_page_title(title: str) -> str | None:
        """Extract a Q-id from either ``Q1`` or a namespaced ``Item:Q1`` title."""
        candidate = title.rsplit(":", 1)[-1]
        if re.fullmatch(r"Q\d+", candidate):
            return candidate
        return None

    def item_ids(self) -> list[str]:
        """List Q-IDs from MediaWiki itself, avoiding asynchronous WDQS state."""
        result: list[str] = []
        params: dict[str, Any] = {
            "action": "query",
            "list": "allpages",
            "apnamespace": self.item_namespace_id(),
            "aplimit": "max",
        }
        while True:
            data = self.get(**params)
            for page in data.get("query", {}).get("allpages", []):
                entity_id = self._entity_id_from_page_title(str(page.get("title", "")))
                if entity_id is not None:
                    result.append(entity_id)
            continuation = data.get("continue")
            if not continuation:
                break
            params.update(continuation)
        return result

    def find_items_by_string_claim(self, property_id: str, value: str) -> list[str]:
        """Find exact string-claim matches from current MediaWiki entity state."""
        matches: list[str] = []
        for entity_id in self.item_ids():
            entity = self.get_entity(entity_id)
            statements = entity.get("claims", {}).get(property_id, [])
            for statement in statements:
                observed = (
                    statement.get("mainsnak", {})
                    .get("datavalue", {})
                    .get("value")
                )
                if observed == value:
                    matches.append(entity_id)
                    break
        return matches
