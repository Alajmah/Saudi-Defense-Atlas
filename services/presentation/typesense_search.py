"""Bounded Typesense adapter for the M3 public search trial.

Typesense is used only as a disposable candidate index. SDA owns normalization,
query/filter semantics, match-quality classification, canonical identity, and
public result ranking through the frozen search contract.
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .search_contract import (
    SearchContractError,
    execute_reference_lexical_search,
    normalize_search_text,
    resolve_query_locale,
)


class TypesenseTrialError(RuntimeError):
    """Raised when the bounded Typesense trial cannot preserve the SDA contract."""


_FACET_KEYS = (
    "service_ids",
    "manufacturer_ids",
    "country_ids",
    "equipment_classes",
    "status_values",
)
_ASCII_COMPACT_RE = re.compile(r"[-_\s]+")
_ASCII_ALNUM_RE = re.compile(r"[a-z0-9]")
_VALIDATION_QUERY = {
    "query": "SDA contract validation sentinel",
    "locale": "en",
    "limit": 1,
    "filters": {
        "entity_types": [],
        "service_ids": [],
        "manufacturer_ids": [],
        "country_ids": [],
        "equipment_classes": [],
        "status_values": [],
    },
}


def _validate_search_document_contract(document: Mapping[str, Any]) -> None:
    """Reuse the frozen reference boundary before any derived-index side effect."""
    execute_reference_lexical_search(documents=[document], query=_VALIDATION_QUERY)


def _validate_search_query_contract(query: Mapping[str, Any]) -> None:
    """Validate exact v0.1 query shape before contacting Typesense."""
    execute_reference_lexical_search(documents=[], query=query)


def trial_collection_schema(collection_name: str) -> dict[str, Any]:
    """Return the explicit schema for the disposable trial collection."""
    if not isinstance(collection_name, str) or not collection_name:
        raise SearchContractError("collection_name is required")
    return {
        "name": collection_name,
        "fields": [
            {"name": "entity_type", "type": "string", "facet": True},
            {"name": "search_ar", "type": "string[]", "locale": "ar", "optional": True},
            {"name": "search_en", "type": "string[]", "optional": True},
            {"name": "search_neutral", "type": "string[]", "optional": True},
            {"name": "service_ids", "type": "string[]", "facet": True, "optional": True},
            {"name": "manufacturer_ids", "type": "string[]", "facet": True, "optional": True},
            {"name": "country_ids", "type": "string[]", "facet": True, "optional": True},
            {"name": "equipment_classes", "type": "string[]", "facet": True, "optional": True},
            {"name": "status_values", "type": "string[]", "facet": True, "optional": True},
        ],
        "metadata": {
            "sda_contract": "m3-search-v0.1",
            "role": "derived-candidate-index",
            "capability_ceiling": "lexical-only-no-typo-no-stemming-no-semantic",
        },
    }


def to_typesense_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Flatten only the minimum approved candidate-search projection."""
    _validate_search_document_contract(document)

    document_id = document["id"]
    entity_type = document["entity_type"]
    terms = document["normalized_terms"]
    facets = document["facets"]

    result: dict[str, Any] = {
        "id": document_id,
        "entity_type": entity_type,
        "search_ar": list(terms["ar"]),
        "search_en": list(terms["en"]),
        "search_neutral": list(terms["neutral"]),
    }
    for key in _FACET_KEYS:
        result[key] = list(facets[key])

    serialized = json.dumps(result, ensure_ascii=False)
    if "backend_identifiers" in serialized or re.search(
        r'(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])', serialized
    ):
        raise SearchContractError("engine projection contains backend/store identity")
    return result


def _compact_candidate_query(normalized_query: str) -> str | None:
    if len(normalized_query) > 64 or not _ASCII_ALNUM_RE.search(normalized_query):
        return None
    if not _ASCII_COMPACT_RE.search(normalized_query):
        return None
    compact = _ASCII_COMPACT_RE.sub("", normalized_query)
    return compact or None


def _escape_filter_value(value: str) -> str:
    # Backticks are Typesense's string-literal delimiter. Canonical public facet
    # values are not allowed to smuggle a delimiter into the engine query.
    if "`" in value or "\n" in value or "\r" in value:
        raise SearchContractError("facet value contains unsupported filter delimiter")
    return f"`{value}`"


def build_typesense_filter(query: Mapping[str, Any]) -> str | None:
    """Map SDA OR-within / AND-across filter semantics to exact Typesense facets."""
    _validate_search_query_contract(query)
    filters = query["filters"]

    clauses: list[str] = []
    entity_types = filters["entity_types"]
    if entity_types:
        values = ",".join(_escape_filter_value(value) for value in entity_types)
        clauses.append(f"entity_type:=[{values}]")

    for key in _FACET_KEYS:
        values_raw = filters[key]
        if not values_raw:
            continue
        values = ",".join(_escape_filter_value(value) for value in values_raw)
        clauses.append(f"{key}:=[{values}]")

    return " && ".join(clauses) if clauses else None


class TypesenseTrialClient:
    """Minimal HTTP client scoped to the bounded M3 trial surface."""

    def __init__(self, *, base_url: str, api_key: str, timeout_seconds: int = 10):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("base_url must use http or https")
        if not api_key:
            raise ValueError("api_key is required")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Any | None = None,
        content_type: str = "application/json",
        expected: tuple[int, ...] = (200, 201),
    ) -> Any:
        body: bytes | None = None
        if payload is not None:
            if content_type == "application/json":
                body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            elif content_type == "text/plain":
                body = str(payload).encode("utf-8")
            else:
                raise ValueError("unsupported content_type")
        request = Request(
            self.base_url + path,
            data=body,
            method=method,
            headers={
                "X-TYPESENSE-API-KEY": self.api_key,
                **({"Content-Type": content_type} if body is not None else {}),
            },
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                status = int(response.status)
                raw = response.read()
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise TypesenseTrialError(
                f"Typesense HTTP {exc.code} for {method} {path}: {detail}"
            ) from exc
        except URLError as exc:
            raise TypesenseTrialError(f"Typesense network error: {exc.reason}") from exc

        if status not in expected:
            raise TypesenseTrialError(
                f"unexpected Typesense status {status} for {method} {path}"
            )
        if not raw:
            return None
        text = raw.decode("utf-8")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return text

    def health(self) -> bool:
        payload = self._request("GET", "/health", expected=(200,))
        return isinstance(payload, Mapping) and payload.get("ok") is True

    def create_collection(self, collection_name: str) -> None:
        self._request("POST", "/collections", payload=trial_collection_schema(collection_name))

    def delete_collection(self, collection_name: str) -> None:
        self._request(
            "DELETE",
            f"/collections/{quote(collection_name, safe='')}",
            expected=(200,),
        )

    def import_documents(
        self, collection_name: str, documents: Sequence[Mapping[str, Any]]
    ) -> None:
        if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
            raise SearchContractError("documents must be an array")
        if not documents:
            return

        projected = [to_typesense_document(document) for document in documents]
        lines = "\n".join(
            json.dumps(document, ensure_ascii=False, sort_keys=True)
            for document in projected
        )
        result = self._request(
            "POST",
            f"/collections/{quote(collection_name, safe='')}/documents/import?action=upsert",
            payload=lines,
            content_type="text/plain",
            expected=(200,),
        )

        rows: list[Mapping[str, Any]] = []
        if isinstance(result, Mapping):
            rows = [result]
        elif isinstance(result, str):
            for line in result.splitlines():
                parsed = json.loads(line)
                if not isinstance(parsed, Mapping):
                    raise TypesenseTrialError("Typesense import row is malformed")
                rows.append(parsed)
        else:
            raise TypesenseTrialError("Typesense import returned unexpected payload")

        if len(rows) != len(projected):
            raise TypesenseTrialError("Typesense import row count differs from submitted documents")
        failures = [json.dumps(row, sort_keys=True) for row in rows if row.get("success") is not True]
        if failures:
            raise TypesenseTrialError("Typesense import failed: " + "; ".join(failures))

    def point_alias(self, alias_name: str, collection_name: str) -> None:
        self._request(
            "PUT",
            f"/aliases/{quote(alias_name, safe='')}",
            payload={"collection_name": collection_name},
            expected=(200,),
        )

    def alias_target(self, alias_name: str) -> str:
        payload = self._request(
            "GET", f"/aliases/{quote(alias_name, safe='')}", expected=(200,)
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("collection_name"), str):
            raise TypesenseTrialError("Typesense alias response is malformed")
        return str(payload["collection_name"])

    def _candidate_ids_for_query(
        self,
        *,
        collection_name: str,
        normalized_query: str,
        locale: str,
        filter_by: str | None,
        candidate_limit: int,
    ) -> list[str]:
        if locale not in {"ar", "en"}:
            raise SearchContractError("resolved locale must be ar or en")
        query_fields = (
            "search_ar,search_neutral,search_en"
            if locale == "ar"
            else "search_en,search_neutral,search_ar"
        )
        params: dict[str, Any] = {
            "q": normalized_query,
            "query_by": query_fields,
            "prefix": "true",
            "infix": "off",
            "num_typos": "0",
            "typo_tokens_threshold": "0",
            "drop_tokens_threshold": "0",
            "split_join_tokens": "off",
            "pre_segmented_query": "true",
            "per_page": str(candidate_limit),
            "include_fields": "id",
            "highlight_fields": "none",
        }
        if filter_by:
            params["filter_by"] = filter_by
        payload = self._request(
            "GET",
            f"/collections/{quote(collection_name, safe='')}/documents/search?{urlencode(params)}",
            expected=(200,),
        )
        if not isinstance(payload, Mapping) or not isinstance(payload.get("hits"), list):
            raise TypesenseTrialError("Typesense search response is malformed")
        found = payload.get("found")
        if not isinstance(found, int) or isinstance(found, bool) or found < 0:
            raise TypesenseTrialError("Typesense search response has invalid found count")
        if found > len(payload["hits"]):
            raise TypesenseTrialError(
                "bounded candidate retrieval would truncate engine matches; "
                "refuse to understate public result totals"
            )

        ids: list[str] = []
        seen: set[str] = set()
        for hit in payload["hits"]:
            if not isinstance(hit, Mapping):
                raise TypesenseTrialError("Typesense hit is malformed")
            doc = hit.get("document")
            if not isinstance(doc, Mapping) or not isinstance(doc.get("id"), str):
                raise TypesenseTrialError("Typesense hit has no SDA id")
            document_id = str(doc["id"])
            if document_id in seen:
                raise TypesenseTrialError(f"Typesense returned duplicate SDA id {document_id}")
            seen.add(document_id)
            ids.append(document_id)
        return ids

    def search(
        self,
        *,
        collection_name: str,
        documents: Sequence[Mapping[str, Any]],
        query: Mapping[str, Any],
        candidate_limit: int = 250,
    ) -> dict[str, Any]:
        """Retrieve candidates from Typesense, then apply SDA public ranking semantics."""
        if candidate_limit < 1 or candidate_limit > 250:
            raise ValueError("candidate_limit must be from 1 to 250 in the bounded trial")
        if not isinstance(query, Mapping):
            raise SearchContractError("query must be an object")
        if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
            raise SearchContractError("documents must be an array")

        # Validate all SDA-owned inputs before the derived engine sees the request.
        _validate_search_query_contract(query)
        documents_by_id: dict[str, Mapping[str, Any]] = {}
        for document in documents:
            if not isinstance(document, Mapping):
                raise SearchContractError("SearchDocument must be an object")
            _validate_search_document_contract(document)
            document_id = str(document["id"])
            if document_id in documents_by_id:
                raise SearchContractError(f"duplicate SearchDocument id: {document_id}")
            documents_by_id[document_id] = document

        raw_query = query["query"]
        requested_locale = query["locale"]
        normalized = normalize_search_text(raw_query)
        locale = resolve_query_locale(raw_query, requested_locale)
        filter_by = build_typesense_filter(query)

        candidate_queries = [normalized]
        compact = _compact_candidate_query(normalized)
        if compact and compact != normalized:
            candidate_queries.append(compact)

        candidate_ids: set[str] = set()
        for candidate_query in candidate_queries:
            candidate_ids.update(
                self._candidate_ids_for_query(
                    collection_name=collection_name,
                    normalized_query=candidate_query,
                    locale=locale,
                    filter_by=filter_by,
                    candidate_limit=candidate_limit,
                )
            )

        unknown = sorted(candidate_ids - set(documents_by_id))
        if unknown:
            raise TypesenseTrialError(
                "derived index returned ids absent from current canonical projection: "
                + ", ".join(unknown)
            )

        candidates = [documents_by_id[document_id] for document_id in sorted(candidate_ids)]
        return execute_reference_lexical_search(documents=candidates, query=query)
