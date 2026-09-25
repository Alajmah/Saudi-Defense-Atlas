"""M1-only Wikibase helpers layered over the verified M0 Action API client."""

from __future__ import annotations

import json
import re
from typing import Any

from wikibase_api import CreatedEntity, WikibaseAPI


class M1WikibaseAPI(WikibaseAPI):
    """Add atomic item/statement writes and strongly consistent item lookup."""

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

    def item_ids(self) -> list[str]:
        """List Q-IDs from MediaWiki itself, avoiding asynchronous WDQS state."""
        result: list[str] = []
        params: dict[str, Any] = {
            "action": "query",
            "list": "allpages",
            "apnamespace": 0,
            "aplimit": "max",
        }
        while True:
            data = self.get(**params)
            for page in data.get("query", {}).get("allpages", []):
                title = str(page.get("title", ""))
                if re.fullmatch(r"Q\d+", title):
                    result.append(title)
            continuation = data.get("continue")
            if not continuation:
                break
            params.update(continuation)
        return result

    def find_items_by_string_claim(self, property_id: str, value: str) -> list[str]:
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
