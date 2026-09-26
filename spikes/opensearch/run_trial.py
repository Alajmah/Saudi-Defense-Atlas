#!/usr/bin/env python3
"""Bounded M3 OpenSearch trial against the accepted SDA lexical contract.

The trial treats OpenSearch as a disposable downstream index. Canonical/domain
identity and normalization remain owned by SDA SearchDocument semantics.
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Sequence

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from services.presentation.search_contract import (  # noqa: E402
    build_search_document,
    execute_reference_lexical_search,
    normalize_search_text,
)

BASE_URL = os.environ.get("OPENSEARCH_URL", "http://127.0.0.1:9200").rstrip("/")
INDEX = "sda-m3-search-trial"
_BACKEND_ID_RE = re.compile(r"(?<![A-Za-z0-9_-])[QP]\d+(?![A-Za-z0-9_-])")
_SPLIT_RE = re.compile(r"[-\s]+")
_COMPACT_RE = re.compile(r"[-_\s]+")
_ASCII_ALNUM_RE = re.compile(r"[a-z0-9]")


def request(method: str, path: str, payload: Any | None = None, *, allow_404: bool = False) -> Any:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE_URL}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            raw = response.read()
            return None if not raw else json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if allow_404 and exc.code == 404:
            return None
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenSearch {method} {path} failed: HTTP {exc.code}: {body}") from exc


def variants(value: str, *, compact: bool) -> set[str]:
    normalized = normalize_search_text(value)
    if not normalized:
        return set()
    result = {normalized}
    if (
        compact
        and len(normalized) <= 64
        and _ASCII_ALNUM_RE.search(normalized)
        and _COMPACT_RE.search(normalized)
    ):
        collapsed = _COMPACT_RE.sub("", normalized)
        if collapsed:
            result.add(collapsed)
    return result


def tokens(values: Sequence[str] | set[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(token for token in _SPLIT_RE.split(value) if token)
    return result


def entity(
    entity_id: str,
    entity_type: str,
    *,
    names: Mapping[str, str],
    aliases: Sequence[Mapping[str, Any]] = (),
    descriptions: Mapping[str, str] | None = None,
    subtype: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": subtype,
        "names": dict(names),
        "aliases": [dict(item) for item in aliases],
        "external_identifiers": [],
        "backend_identifiers": [],
        "record_status": "active",
        "merged_into": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-10T00:00:00Z",
    }
    if descriptions is not None:
        result["descriptions"] = dict(descriptions)
    return result


def query(
    text: str,
    *,
    locale: str = "auto",
    entity_types: Sequence[str] = (),
    manufacturer_ids: Sequence[str] = (),
    country_ids: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "query": text,
        "locale": locale,
        "limit": 20,
        "filters": {
            "entity_types": list(entity_types),
            "service_ids": [],
            "manufacturer_ids": list(manufacturer_ids),
            "country_ids": list(country_ids),
            "equipment_classes": [],
            "status_values": [],
        },
    }


def build_documents() -> list[dict[str, Any]]:
    f15 = entity(
        "SDA-EQUIP-F15SA",
        "equipment_variant",
        names={"ar": "إف-15 إس إيه", "en": "F-15SA"},
        aliases=[
            {"value": "F15SA", "language": "en", "kind": "designation"},
            {"value": "Saudi Advanced Eagle", "language": "en", "kind": "common"},
            {"value": "إف 15 إس إيه", "language": "ar", "kind": "search"},
        ],
        descriptions={"en": "Fighter variant represented in the public atlas."},
        subtype="fighter",
    )
    typhoon = entity(
        "SDA-EQUIP-TYPHOON",
        "equipment",
        names={"ar": "تايفون", "en": "Eurofighter Typhoon"},
        aliases=[
            {"value": "يوروفايتر تايفون", "language": "ar", "kind": "common"},
            {"value": "Typhoon", "language": "en", "kind": "common"},
        ],
        descriptions={"en": "Multirole fighter represented in the public atlas."},
        subtype="fighter",
    )
    rsaf = entity(
        "SDA-ORG-RSAF",
        "organization",
        names={"ar": "القوات الجوية الملكية السعودية", "en": "Royal Saudi Air Force"},
        aliases=[
            {"value": "RSAF", "language": "en", "kind": "abbreviation"},
            {"value": "القوات الجوية السعودية", "language": "ar", "kind": "common"},
        ],
    )
    chair = entity(
        "SDA-TEST-CHAIR",
        "equipment",
        names={"en": "Chair System"},
        descriptions={"en": "A chair reference fixture used only to reject substring matching."},
    )

    return [
        build_search_document(
            entity=f15,
            facets={
                "service_ids": ["SDA-ORG-RSAF"],
                "manufacturer_ids": ["SDA-ORG-BOEING"],
                "country_ids": ["SDA-COUNTRY-SA"],
                "equipment_classes": ["fighter"],
                "status_values": ["operational"],
            },
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-OS-F15"],
        ),
        build_search_document(
            entity=typhoon,
            facets={
                "service_ids": ["SDA-ORG-RSAF"],
                "manufacturer_ids": ["SDA-ORG-EUROFIGHTER"],
                "country_ids": ["SDA-COUNTRY-SA"],
                "equipment_classes": ["fighter"],
                "status_values": ["operational"],
            },
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-OS-TYPHOON"],
        ),
        build_search_document(
            entity=rsaf,
            facets={"country_ids": ["SDA-COUNTRY-SA"]},
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-OS-RSAF"],
        ),
        build_search_document(
            entity=chair,
            facets={},
            projected_at="2026-01-12T00:00:00Z",
            revision_ids=["SDA-REV-OS-CHAIR"],
        ),
    ]


def engine_document(document: Mapping[str, Any]) -> dict[str, Any]:
    id_terms = variants(str(document["id"]), compact=True)
    name_terms: set[str] = set()
    alias_terms: set[str] = set()
    description_terms: set[str] = set()

    for value in document["names"].values():
        name_terms.update(variants(str(value), compact=True))
    for alias in document["aliases"]:
        alias_terms.update(variants(str(alias["value"]), compact=True))
    for value in (document.get("descriptions") or {}).values():
        description_terms.update(variants(str(value), compact=False))

    all_tokens = tokens(id_terms | name_terms | alias_terms | description_terms)
    display_name = document["names"].get("en") or document["names"].get("ar") or document["id"]
    arabic_parts = [
        value for value in document["names"].values() if re.search(r"[\u0600-\u06ff]", value)
    ]
    for alias in document["aliases"]:
        value = str(alias["value"])
        if re.search(r"[\u0600-\u06ff]", value):
            arabic_parts.append(value)

    projected = {
        "id": document["id"],
        "entity_type": document["entity_type"],
        "sort_name": normalize_search_text(str(display_name)),
        "id_terms": sorted(id_terms),
        "name_terms": sorted(name_terms),
        "alias_terms": sorted(alias_terms),
        "description_tokens": sorted(tokens(description_terms)),
        "all_tokens": sorted(all_tokens),
        "facets": document["facets"],
        "arabic_fulltext": " ".join(arabic_parts),
    }
    if _BACKEND_ID_RE.search(repr(projected)):
        raise AssertionError("backend Q/P identifier leaked into OpenSearch trial payload")
    return projected


def create_index() -> None:
    request("DELETE", f"/{INDEX}", allow_404=True)
    request(
        "PUT",
        f"/{INDEX}",
        {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0,
                "analysis": {
                    "filter": {
                        "sda_decimal_digit": {"type": "decimal_digit"},
                        "sda_arabic_normalization": {"type": "arabic_normalization"},
                    },
                    "analyzer": {
                        "sda_arabic_conservative": {
                            "type": "custom",
                            "tokenizer": "standard",
                            "filter": [
                                "lowercase",
                                "sda_decimal_digit",
                                "sda_arabic_normalization",
                            ],
                        }
                    },
                },
            },
            "mappings": {
                "dynamic": "strict",
                "properties": {
                    "id": {"type": "keyword"},
                    "entity_type": {"type": "keyword"},
                    "sort_name": {"type": "keyword"},
                    "id_terms": {"type": "keyword"},
                    "name_terms": {"type": "keyword"},
                    "alias_terms": {"type": "keyword"},
                    "description_tokens": {"type": "keyword"},
                    "all_tokens": {"type": "keyword"},
                    "arabic_fulltext": {
                        "type": "text",
                        "analyzer": "sda_arabic_conservative",
                    },
                    "facets": {
                        "properties": {
                            "service_ids": {"type": "keyword"},
                            "manufacturer_ids": {"type": "keyword"},
                            "country_ids": {"type": "keyword"},
                            "equipment_classes": {"type": "keyword"},
                            "status_values": {"type": "keyword"},
                        }
                    },
                },
            },
        },
    )


def index_documents(documents: Sequence[Mapping[str, Any]]) -> None:
    for document in documents:
        body = engine_document(document)
        encoded = urllib.parse.quote(str(document["id"]), safe="")
        request("PUT", f"/{INDEX}/_doc/{encoded}", body)
    request("POST", f"/{INDEX}/_refresh")


def os_query(q: Mapping[str, Any]) -> list[str]:
    normalized = normalize_search_text(str(q["query"]))
    q_tokens = sorted(tokens({normalized}))
    should: list[dict[str, Any]] = [
        {"term": {"id_terms": {"value": normalized, "boost": 100}}},
        {"term": {"name_terms": {"value": normalized, "boost": 80}}},
        {"term": {"alias_terms": {"value": normalized, "boost": 60}}},
        {"prefix": {"name_terms": {"value": normalized, "boost": 40}}},
        {"prefix": {"alias_terms": {"value": normalized, "boost": 40}}},
    ]
    if q_tokens:
        should.append(
            {
                "bool": {
                    "must": [{"term": {"all_tokens": token}} for token in q_tokens],
                    "boost": 20,
                }
            }
        )

    filters = q["filters"]
    filter_clauses: list[dict[str, Any]] = []
    if filters["entity_types"]:
        filter_clauses.append({"terms": {"entity_type": filters["entity_types"]}})
    for key in (
        "service_ids", "manufacturer_ids", "country_ids", "equipment_classes", "status_values"
    ):
        if filters[key]:
            filter_clauses.append({"terms": {f"facets.{key}": filters[key]}})

    result = request(
        "POST",
        f"/{INDEX}/_search",
        {
            "size": q["limit"],
            "track_scores": True,
            "_source": ["id"],
            "query": {
                "bool": {
                    "filter": filter_clauses,
                    "should": should,
                    "minimum_should_match": 1,
                }
            },
            "sort": [
                {"_score": {"order": "desc"}},
                {"sort_name": {"order": "asc"}},
                {"id": {"order": "asc"}},
            ],
        },
    )
    return [hit["_source"]["id"] for hit in result["hits"]["hits"]]


def validate_analyzer() -> dict[str, Any]:
    analyzed = request(
        "POST",
        f"/{INDEX}/_analyze",
        {
            "analyzer": "sda_arabic_conservative",
            "text": "ألقُوَّات والكتاب ۱۵",
        },
    )
    produced = [item["token"] for item in analyzed["tokens"]]
    expected = ["القوات", "والكتاب", "15"]
    if produced != expected:
        raise AssertionError(
            f"conservative Arabic analyzer changed unexpectedly: {produced!r} != {expected!r}"
        )
    return {"input": "ألقُوَّات والكتاب ۱۵", "tokens": produced}


def main() -> int:
    documents = build_documents()
    create_index()
    index_documents(documents)

    cases = [
        query("F-15SA", locale="en"),
        query("F15SA", locale="en"),
        query("تَايْفُون", locale="auto"),
        query("ٱلقوات الجوية الملكية السعودية", locale="auto"),
        query(
            "fighter",
            locale="en",
            entity_types=["equipment_variant"],
            manufacturer_ids=["SDA-ORG-BOEING", "SDA-ORG-NOT-PRESENT"],
            country_ids=["SDA-COUNTRY-SA"],
        ),
        query("air", locale="en"),
        query("fighter", locale="en"),
    ]

    comparisons: list[dict[str, Any]] = []
    for item in cases:
        reference = execute_reference_lexical_search(documents=documents, query=item)
        expected_ids = [hit["id"] for hit in reference["hits"]]
        actual_ids = os_query(item)
        if actual_ids != expected_ids:
            raise AssertionError(
                f"OpenSearch diverged for {item['query']!r}: actual={actual_ids}, expected={expected_ids}"
            )
        comparisons.append(
            {"query": item["query"], "ids": actual_ids, "reference_total": reference["total"]}
        )

    analyzer = validate_analyzer()
    evidence = {
        "result": "PASS",
        "engine": "OpenSearch",
        "version": request("GET", "/")["version"]["number"],
        "contract": "M3 lexical baseline",
        "comparisons": comparisons,
        "conservative_arabic_analyzer": analyzer,
        "claim_ceiling": (
            "Suitability evidence for the bounded M3 downstream lexical-index role only; "
            "not production security/HA/scale or semantic/vector relevance qualification."
        ),
    }
    if evidence["version"] != "3.8.0":
        raise AssertionError(f"trial must run pinned OpenSearch 3.8.0, got {evidence['version']}")
    print(json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
