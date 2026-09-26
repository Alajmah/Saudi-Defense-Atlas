"""Backend-neutral M3 public search contract and deterministic lexical reference.

This module defines the minimum semantics a future search adapter must preserve.
It does not select a search engine and does not claim fuzzy, stemming, or semantic
retrieval. Canonical/display text is never rewritten by normalization; folded
terms exist only in the search projection.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


class SearchContractError(ValueError):
    """Raised when public search inputs violate the M3 contract."""


_ARABIC_RE = re.compile(r"[\u0600-\u06ff]")
_ARABIC_DIACRITICS_RE = re.compile(
    r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]"
)
_WHITESPACE_RE = re.compile(r"\s+")
_COMPACT_RE = re.compile(r"[-_\s]+")
_ASCII_ALNUM_RE = re.compile(r"[a-z0-9]")

_TRANSLATION = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "٠": "0",
        "١": "1",
        "٢": "2",
        "٣": "3",
        "٤": "4",
        "٥": "5",
        "٦": "6",
        "٧": "7",
        "٨": "8",
        "٩": "9",
        "۰": "0",
        "۱": "1",
        "۲": "2",
        "۳": "3",
        "۴": "4",
        "۵": "5",
        "۶": "6",
        "۷": "7",
        "۸": "8",
        "۹": "9",
        "‐": "-",
        "‑": "-",
        "‒": "-",
        "–": "-",
        "—": "-",
        "−": "-",
    }
)

_FACET_KEYS = (
    "service_ids",
    "manufacturer_ids",
    "country_ids",
    "equipment_classes",
    "status_values",
)

_QUALITY_ORDER = {
    "exact_id": 0,
    "exact_name": 1,
    "exact_alias": 2,
    "prefix": 3,
    "token": 4,
}


def normalize_search_text(value: str) -> str:
    """Return conservative orthographic folding for lexical search only.

    The fold intentionally does not stem Arabic, strip the definite article,
    transliterate between scripts, or merge taa marbuta/haa. Those behaviors
    require separate evidence because they can change meaning or recall/precision.
    """

    if not isinstance(value, str):
        raise SearchContractError("search text must be a string")
    text = unicodedata.normalize("NFKC", value).casefold()
    text = text.replace("ـ", "")
    text = _ARABIC_DIACRITICS_RE.sub("", text).translate(_TRANSLATION)

    folded: list[str] = []
    for char in text:
        if char == "-" or char.isalnum() or _ARABIC_RE.fullmatch(char):
            folded.append(char)
            continue
        category = unicodedata.category(char)
        folded.append(" " if category.startswith(("P", "S", "Z")) else char)

    return _WHITESPACE_RE.sub(" ", "".join(folded)).strip()


def _normalized_variants(value: str) -> set[str]:
    normalized = normalize_search_text(value)
    if not normalized:
        return set()
    variants = {normalized}
    if _ASCII_ALNUM_RE.search(normalized):
        compact = _COMPACT_RE.sub("", normalized)
        if compact:
            variants.add(compact)
    return variants


def _parse_utc(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise SearchContractError(f"{label} requires an ISO date-time string")
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SearchContractError(f"{label} is not a valid ISO date-time") from exc
    if parsed.tzinfo is None:
        raise SearchContractError(f"{label} must be timezone-aware")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _public_localized(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, Mapping):
        raise SearchContractError(f"{label} must be localized text")
    result: dict[str, str] = {}
    for locale in ("ar", "en"):
        item = value.get(locale)
        if item is not None:
            if not isinstance(item, str) or not item.strip():
                raise SearchContractError(f"{label}.{locale} must be non-empty text")
            result[locale] = item.strip()
    if not result:
        raise SearchContractError(f"{label} requires Arabic or English text")
    return result


def _aliases(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SearchContractError("aliases must be an array")
    aliases: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise SearchContractError("alias must be an object")
        alias_value = item.get("value")
        if not isinstance(alias_value, str) or not alias_value.strip():
            raise SearchContractError("alias.value must be non-empty text")
        aliases.append(
            {
                "value": alias_value.strip(),
                **({"language": item.get("language")} if "language" in item else {}),
                **({"kind": item.get("kind")} if "kind" in item else {}),
            }
        )
    return aliases


def _facets(value: Mapping[str, Sequence[str]] | None) -> dict[str, list[str]]:
    provided = dict(value or {})
    unknown = sorted(set(provided) - set(_FACET_KEYS))
    if unknown:
        raise SearchContractError("unknown search facets: " + ", ".join(unknown))
    result: dict[str, list[str]] = {}
    for key in _FACET_KEYS:
        raw_values = provided.get(key, ())
        if not isinstance(raw_values, Sequence) or isinstance(raw_values, (str, bytes)):
            raise SearchContractError(f"facet {key} must be an array")
        normalized: set[str] = set()
        for item in raw_values:
            if not isinstance(item, str) or not item.strip():
                raise SearchContractError(f"facet {key} contains an invalid value")
            normalized.add(item.strip())
        result[key] = sorted(normalized)
    return result


def build_search_document(
    *,
    entity: Mapping[str, Any],
    facets: Mapping[str, Sequence[str]] | None,
    projected_at: str,
    revision_ids: Sequence[str],
) -> dict[str, Any]:
    """Project one active public Entity into an engine-neutral search document.

    Facets are caller-supplied projections. This function never infers service,
    manufacturer, country, status, or equipment class from raw claims.
    """

    entity_id = entity.get("id")
    entity_type = entity.get("entity_type")
    if not isinstance(entity_id, str) or not entity_id:
        raise SearchContractError("Entity requires canonical SDA ID")
    if not isinstance(entity_type, str) or not entity_type:
        raise SearchContractError("Entity requires entity_type")
    if entity.get("record_status") != "active":
        raise SearchContractError("public search indexes active Entity records only")

    names = _public_localized(entity.get("names"), "names")
    aliases = _aliases(entity.get("aliases", []))
    descriptions_raw = entity.get("descriptions")
    descriptions = (
        None
        if descriptions_raw is None
        else _public_localized(descriptions_raw, "descriptions")
    )

    revisions: set[str] = set()
    if not isinstance(revision_ids, Sequence) or isinstance(revision_ids, (str, bytes)):
        raise SearchContractError("revision_ids must be an array")
    for revision_id in revision_ids:
        if not isinstance(revision_id, str) or not revision_id:
            raise SearchContractError("revision_ids must contain canonical IDs")
        revisions.add(revision_id)
    if not revisions:
        raise SearchContractError("search document requires at least one Revision ID")

    terms: dict[str, set[str]] = {"ar": set(), "en": set(), "neutral": set()}
    terms["neutral"].update(_normalized_variants(entity_id))

    for locale, value in names.items():
        terms[locale].update(_normalized_variants(value))
    if descriptions:
        for locale, value in descriptions.items():
            terms[locale].update(_normalized_variants(value))

    for alias in aliases:
        language = alias.get("language")
        channel = language if language in {"ar", "en"} else "neutral"
        terms[channel].update(_normalized_variants(str(alias["value"])))

    return {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": entity.get("subtype"),
        "names": names,
        "aliases": aliases,
        "descriptions": descriptions,
        "normalized_terms": {
            locale: sorted(values) for locale, values in terms.items()
        },
        "facets": _facets(facets),
        "projected_at": _parse_utc(projected_at, "projected_at"),
        "revision_ids": sorted(revisions),
    }


def resolve_query_locale(query: str, requested_locale: str) -> str:
    if requested_locale not in {"ar", "en", "auto"}:
        raise SearchContractError("locale must be ar, en, or auto")
    if requested_locale != "auto":
        return requested_locale
    return "ar" if _ARABIC_RE.search(query) else "en"


def _filters_match(document: Mapping[str, Any], filters: Mapping[str, Any]) -> bool:
    entity_types = filters.get("entity_types", [])
    if entity_types and document.get("entity_type") not in set(entity_types):
        return False

    facets = document.get("facets")
    if not isinstance(facets, Mapping):
        raise SearchContractError("search document is missing facets")
    for key in _FACET_KEYS:
        requested = filters.get(key, [])
        if not requested:
            continue
        actual = facets.get(key, [])
        if not isinstance(actual, Sequence) or isinstance(actual, (str, bytes)):
            raise SearchContractError(f"search document facet {key} is malformed")
        # OR within one facet, AND across different facet categories.
        if not set(requested).intersection(actual):
            return False
    return True


def _field_terms(document: Mapping[str, Any], locale: str) -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {
        "id": _normalized_variants(str(document.get("id", ""))),
        "name": set(),
        "alias": set(),
        "description": set(),
    }
    names = document.get("names")
    if isinstance(names, Mapping):
        for value in names.values():
            if isinstance(value, str):
                fields["name"].update(_normalized_variants(value))

    aliases = document.get("aliases")
    if isinstance(aliases, Sequence) and not isinstance(aliases, (str, bytes)):
        for alias in aliases:
            if isinstance(alias, Mapping) and isinstance(alias.get("value"), str):
                fields["alias"].update(_normalized_variants(alias["value"]))

    descriptions = document.get("descriptions")
    if isinstance(descriptions, Mapping):
        preferred = descriptions.get(locale)
        if isinstance(preferred, str):
            fields["description"].update(_normalized_variants(preferred))
        for other_locale, value in descriptions.items():
            if other_locale != locale and isinstance(value, str):
                fields["description"].update(_normalized_variants(value))
    return fields


def _match_document(
    document: Mapping[str, Any], normalized_query: str, locale: str
) -> tuple[str, list[str]] | None:
    fields = _field_terms(document, locale)

    if normalized_query in fields["id"]:
        return "exact_id", ["id"]
    if normalized_query in fields["name"]:
        return "exact_name", ["name"]
    if normalized_query in fields["alias"]:
        return "exact_alias", ["alias"]

    prefix_fields = [
        field
        for field in ("name", "alias")
        if any(term.startswith(normalized_query) for term in fields[field])
    ]
    if prefix_fields:
        return "prefix", prefix_fields

    query_tokens = [token for token in normalized_query.split(" ") if token]
    if not query_tokens:
        return None
    matched_fields: list[str] = []
    searchable_by_field: dict[str, str] = {
        field: " ".join(sorted(values)) for field, values in fields.items()
    }
    combined = " ".join(searchable_by_field.values())
    if all(token in combined for token in query_tokens):
        for field in ("id", "name", "alias", "description"):
            if any(token in searchable_by_field[field] for token in query_tokens):
                matched_fields.append(field)
        return "token", matched_fields or ["name"]
    return None


def execute_reference_lexical_search(
    *,
    documents: Sequence[Mapping[str, Any]],
    query: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute the deterministic reference semantics for the v0.1 lexical contract.

    This function is an acceptance oracle, not the chosen production search engine.
    Future adapters may rank more intelligently, but must preserve identity, filters,
    locale/display behavior, and must not claim unsupported semantic/fuzzy behavior.
    """

    raw_query = query.get("query")
    requested_locale = query.get("locale")
    limit = query.get("limit")
    filters = query.get("filters")
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise SearchContractError("query requires non-empty text")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise SearchContractError("limit must be an integer from 1 to 50")
    if not isinstance(filters, Mapping):
        raise SearchContractError("filters must be an object")

    locale = resolve_query_locale(raw_query, str(requested_locale))
    normalized_query = normalize_search_text(raw_query)
    if not normalized_query:
        raise SearchContractError("query is empty after normalization")

    candidates: list[tuple[int, str, str, Mapping[str, Any], list[str]]] = []
    seen_ids: set[str] = set()
    for document in documents:
        document_id = document.get("id")
        if not isinstance(document_id, str) or not document_id:
            raise SearchContractError("search document requires canonical ID")
        if document_id in seen_ids:
            raise SearchContractError(f"duplicate search document ID: {document_id}")
        seen_ids.add(document_id)
        if not _filters_match(document, filters):
            continue
        match = _match_document(document, normalized_query, locale)
        if match is None:
            continue
        quality, matched_fields = match
        names = document.get("names") if isinstance(document.get("names"), Mapping) else {}
        display_name = names.get(locale) or names.get("ar") or names.get("en") or document_id
        candidates.append(
            (
                _QUALITY_ORDER[quality],
                normalize_search_text(str(display_name)),
                document_id,
                document,
                matched_fields,
            )
        )

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    hits: list[dict[str, Any]] = []
    for rank, (_, _, document_id, document, matched_fields) in enumerate(
        candidates[:limit], start=1
    ):
        match = _match_document(document, normalized_query, locale)
        if match is None:  # pragma: no cover - guarded by candidate construction
            continue
        quality, _ = match
        hits.append(
            {
                "rank": rank,
                "id": document_id,
                "entity_type": document["entity_type"],
                "names": dict(document["names"]),
                "descriptions": (
                    None
                    if document.get("descriptions") is None
                    else dict(document["descriptions"])
                ),
                "match_quality": quality,
                "matched_fields": sorted(set(matched_fields)),
            }
        )

    return {
        "query": raw_query,
        "normalized_query": normalized_query,
        "locale": locale,
        "total": len(candidates),
        "hits": hits,
    }
