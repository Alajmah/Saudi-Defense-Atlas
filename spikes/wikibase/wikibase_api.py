"""Small Action API client used only by the M0 Wikibase spike.

The goal is to exercise Wikibase itself without making a Python SDK part of the
project's domain contract. Production adapters may later use a mature client.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import requests


class WikibaseAPIError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreatedEntity:
    entity_id: str
    lastrevid: int | None


class WikibaseAPI:
    def __init__(self, base_url: str, username: str, password: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/w/api.php"
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Saudi-Defense-Atlas-M0-Wikibase-Spike/0.1"}
        )
        self.csrf_token: str | None = None

    def _json_response(self, response: requests.Response) -> dict[str, Any]:
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise WikibaseAPIError(json.dumps(data["error"], ensure_ascii=False))
        return data

    def get(self, **params: Any) -> dict[str, Any]:
        params.setdefault("format", "json")
        return self._json_response(
            self.session.get(self.api_url, params=params, timeout=30)
        )

    def post(self, **data: Any) -> dict[str, Any]:
        data.setdefault("format", "json")
        return self._json_response(
            self.session.post(self.api_url, data=data, timeout=30)
        )

    def login(self) -> None:
        token_data = self.get(action="query", meta="tokens", type="login")
        login_token = token_data["query"]["tokens"]["logintoken"]

        result = self.post(
            action="login",
            lgname=self.username,
            lgpassword=self.password,
            lgtoken=login_token,
        )
        login_result = result.get("login", {}).get("result")

        if login_result != "Success":
            # Current MediaWiki installations may prefer clientlogin for a normal
            # account. Keep the fallback local to the spike rather than teaching
            # the domain layer about MediaWiki authentication details.
            result = self.post(
                action="clientlogin",
                username=self.username,
                password=self.password,
                loginreturnurl=self.base_url,
                logintoken=login_token,
            )
            status = result.get("clientlogin", {}).get("status")
            if status != "PASS":
                raise WikibaseAPIError(
                    f"login failed: login={login_result!r}, clientlogin={status!r}"
                )

        csrf_data = self.get(action="query", meta="tokens", type="csrf")
        self.csrf_token = csrf_data["query"]["tokens"]["csrftoken"]

    def _token(self) -> str:
        if not self.csrf_token:
            raise WikibaseAPIError("login() must succeed before a write")
        return self.csrf_token

    @staticmethod
    def _language_values(values: dict[str, str]) -> dict[str, dict[str, str]]:
        return {
            language: {"language": language, "value": value}
            for language, value in values.items()
        }

    @staticmethod
    def _aliases(values: dict[str, list[str]]) -> dict[str, list[dict[str, str]]]:
        return {
            language: [
                {"language": language, "value": alias} for alias in aliases
            ]
            for language, aliases in values.items()
        }

    def create_property(
        self,
        labels: dict[str, str],
        datatype: str,
        descriptions: dict[str, str] | None = None,
    ) -> CreatedEntity:
        entity_data: dict[str, Any] = {
            "datatype": datatype,
            "labels": self._language_values(labels),
        }
        if descriptions:
            entity_data["descriptions"] = self._language_values(descriptions)

        result = self.post(
            action="wbeditentity",
            new="property",
            data=json.dumps(entity_data, ensure_ascii=False),
            token=self._token(),
            summary="SDA M0: create trial property",
        )
        entity = result["entity"]
        return CreatedEntity(entity["id"], entity.get("lastrevid"))

    def create_item(
        self,
        labels: dict[str, str],
        aliases: dict[str, list[str]] | None = None,
        descriptions: dict[str, str] | None = None,
    ) -> CreatedEntity:
        entity_data: dict[str, Any] = {
            "labels": self._language_values(labels),
        }
        if aliases:
            entity_data["aliases"] = self._aliases(aliases)
        if descriptions:
            entity_data["descriptions"] = self._language_values(descriptions)

        result = self.post(
            action="wbeditentity",
            new="item",
            data=json.dumps(entity_data, ensure_ascii=False),
            token=self._token(),
            summary="SDA M0: create trial item",
        )
        entity = result["entity"]
        return CreatedEntity(entity["id"], entity.get("lastrevid"))

    def add_claim(
        self,
        entity_id: str,
        property_id: str,
        value: Any,
        *,
        summary: str = "SDA M0: add trial statement",
    ) -> str:
        result = self.post(
            action="wbcreateclaim",
            entity=entity_id,
            property=property_id,
            snaktype="value",
            value=json.dumps(value, ensure_ascii=False),
            token=self._token(),
            summary=summary,
        )
        return result["claim"]["id"]

    def add_qualifier(self, claim_id: str, property_id: str, value: Any) -> None:
        self.post(
            action="wbsetqualifier",
            claim=claim_id,
            property=property_id,
            snaktype="value",
            value=json.dumps(value, ensure_ascii=False),
            token=self._token(),
        )

    @staticmethod
    def make_snak(property_id: str, datatype: str, value: Any) -> dict[str, Any]:
        if datatype in {"string", "external-id", "url"}:
            value_type = "string"
        elif datatype == "time":
            value_type = "time"
        elif datatype == "quantity":
            value_type = "quantity"
        elif datatype == "wikibase-item":
            value_type = "wikibase-entityid"
        else:
            raise ValueError(f"unsupported spike datatype: {datatype}")

        return {
            "snaktype": "value",
            "property": property_id,
            "datavalue": {"value": value, "type": value_type},
            "datatype": datatype,
        }

    def add_reference(
        self, claim_id: str, snaks: dict[str, list[dict[str, Any]]]
    ) -> None:
        self.post(
            action="wbsetreference",
            statement=claim_id,
            snaks=json.dumps(snaks, ensure_ascii=False),
            token=self._token(),
        )

    def get_entity(self, entity_id: str) -> dict[str, Any]:
        data = self.get(
            action="wbgetentities",
            ids=entity_id,
            props="info|labels|descriptions|aliases|claims",
            languages="ar|en",
        )
        return data["entities"][entity_id]

    def search_entities(
        self, text: str, language: str, entity_type: str = "item"
    ) -> list[dict[str, Any]]:
        data = self.get(
            action="wbsearchentities",
            search=text,
            language=language,
            type=entity_type,
            limit=20,
        )
        return data.get("search", [])

    def page_revisions(self, entity_id: str, limit: int = 20) -> list[dict[str, Any]]:
        namespace = "Property" if entity_id.startswith("P") else "Item"
        data = self.get(
            action="query",
            prop="revisions",
            titles=f"{namespace}:{entity_id}",
            rvprop="ids|timestamp|comment|user",
            rvlimit=limit,
        )
        pages = data.get("query", {}).get("pages", {})
        if not pages:
            return []
        page = next(iter(pages.values()))
        return page.get("revisions", [])


def item_value(qid: str) -> dict[str, Any]:
    if not qid.startswith("Q"):
        raise ValueError(f"expected Q-id, got {qid}")
    return {"entity-type": "item", "numeric-id": int(qid[1:])}


def quantity_value(amount: int | float | str) -> dict[str, Any]:
    amount_text = str(amount)
    if not amount_text.startswith(("+", "-")):
        amount_text = f"+{amount_text}"
    return {
        "amount": amount_text,
        "unit": "1",
        "upperBound": amount_text,
        "lowerBound": amount_text,
    }


def time_value(value: str, precision: str = "day") -> dict[str, Any]:
    precision_codes = {"year": 9, "month": 10, "day": 11, "second": 14}
    if precision not in precision_codes:
        raise ValueError(f"unsupported time precision: {precision}")

    parts = value.split("-")
    year = int(parts[0])
    month = int(parts[1]) if len(parts) > 1 else 1
    day = int(parts[2]) if len(parts) > 2 else 1
    return {
        "time": f"+{year:04d}-{month:02d}-{day:02d}T00:00:00Z",
        "timezone": 0,
        "before": 0,
        "after": 0,
        "precision": precision_codes[precision],
        "calendarmodel": "http://www.wikidata.org/entity/Q1985727",
    }
