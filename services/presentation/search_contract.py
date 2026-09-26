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
_TOKEN_SPLIT_RE = re.compile(r"[-\s]+")
_ASCII_ALNUM_RE = re.compile(r"[a-z0-9]")

_TRANSLATION = str.maketrans(
    {
        "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي",
        "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
        "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
        "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
        "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
        "‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "−": "-",
    }
)

_ENTITY_TYPES = {
    "organization", "military_unit", "equipment", "equipment_variant",
    "facility", "exercise", "procurement_program", "contract",
    "localization_program", "country",
}
_ALIAS_KINDS = {
    "official", "abbreviation", "transliteration", "designation",
    "common", "historical", "search",
}
_FACET_KEYS = (
    "service_ids", "manufacturer_ids", "country_ids",
    "equipment_classes", "status_values",
)
_QUERY_FILTER_KEYS = {"entity_types", *_FACET_KEYS}
_QUERY_KEYS = {"query", "locale", "limit", "filters"}

# Keep schema-required and schema-allowed fields separate. subtype/descriptions
# are intentionally optional in search-document.schema.json.
_SEARCH_DOCUMENT_REQUIRED_KEYS = {
    "id", "entity_type", "names", "aliases", "normalized_terms",
    "facets", "projected_at", "revision_ids",
}
_SEARCH_DOCUMENT_ALLOWED_KEYS = {
    *_SEARCH_DOCUMENT_REQUIRED_KEYS, "subtype", "descriptions",
}

_QUALITY_ORDER = {
    "exact_id": 0, "exact_name": 1, "exact_alias": 2,
    "prefix": 3, "token": 4,
}


def normalize_search_text(value: str) -> str:
    """Return conservative orthographic folding for lexical search only."""
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


def _normalized_variants(value: str, *, compact: bool = False) -> set[str]:
    normalized = normalize_search_text(value)
    if not normalized:
        return set()
    variants = {normalized}
    if (
        compact and len(normalized) <= 64
        and _ASCII_ALNUM_RE.search(normalized)
        and _COMPACT_RE.search(normalized)
    ):
        compact_value = _COMPACT_RE.sub("", normalized)
        if compact_value:
            variants.add(compact_value)
    return variants


def _tokens(values: set[str]) -> set[str]:
    result: set[str] = set()
    for value in values:
        result.update(token for token in _TOKEN_SPLIT_RE.split(value) if token)
    return result


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
    unknown = sorted(set(value) - {"ar", "en"})
    if unknown:
        raise SearchContractError(
            f"{label} contains unsupported locales: {', '.join(unknown)}"
        )
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
        unknown = sorted(set(item) - {"value", "language", "kind"})
        if unknown:
            raise SearchContractError("alias contains unknown fields: " + ", ".join(unknown))
        alias_value = item.get("value")
        if not isinstance(alias_value, str) or not alias_value.strip():
            raise SearchContractError("alias.value must be non-empty text")
        language = item.get("language") if "language" in item else None
        if language is not None and (not isinstance(language, str) or not language.strip()):
            raise SearchContractError("alias.language must be null or non-empty text")
        kind = item.get("kind") if "kind" in item else None
        if kind is not None and kind not in _ALIAS_KINDS:
            raise SearchContractError("alias.kind is not in the SDA alias vocabulary")
        projected: dict[str, Any] = {"value": alias_value.strip()}
        if "language" in item:
            projected["language"] = language
        if "kind" in item:
            projected["kind"] = kind
        aliases.append(projected)
    return aliases


def _string_array(
    value: Any,
    label: str,
    *,
    allowed: set[str] | None = None,
    require_unique: bool = True,
) -> list[str]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise SearchContractError(f"{label} must be an array")
    result: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise SearchContractError(f"{label} contains an invalid value")
        normalized = item.strip()
        if allowed is not None and normalized not in allowed:
            raise SearchContractError(f"{label} contains unsupported value {normalized!r}")
        if require_unique and normalized in seen:
            raise SearchContractError(f"{label} contains duplicate value {normalized!r}")
        seen.add(normalized)
        result.append(normalized)
    return result


def _facets(value: Any, *, require_complete: bool = False) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        if value is None and not require_complete:
            value = {}
        else:
            raise SearchContractError("facets must be an object")
    provided = dict(value)
    missing = sorted(set(_FACET_KEYS) - set(provided))
    unknown = sorted(set(provided) - set(_FACET_KEYS))
    if require_complete and missing:
        raise SearchContractError("facets missing required keys: " + ", ".join(missing))
    if unknown:
        raise SearchContractError("unknown search facets: " + ", ".join(unknown))
    result: dict[str, list[str]] = {}
    for key in _FACET_KEYS:
        raw = provided[key] if key in provided else ()
        result[key] = sorted(_string_array(raw, f"facet {key}"))
    return result


def _query_filters(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, Mapping):
        raise SearchContractError("filters must be an object")
    missing = sorted(_QUERY_FILTER_KEYS - set(value))
    unknown = sorted(set(value) - _QUERY_FILTER_KEYS)
    if missing:
        raise SearchContractError("filters missing required keys: " + ", ".join(missing))
    if unknown:
        raise SearchContractError("filters contain unknown keys: " + ", ".join(unknown))
    result = {
        "entity_types": _string_array(
            value["entity_types"], "filters.entity_types", allowed=_ENTITY_TYPES
        )
    }
    for key in _FACET_KEYS:
        result[key] = _string_array(value[key], f"filters.{key}")
    return result


def _normalized_terms_from_public_fields(
    *,
    entity_id: str,
    names: Mapping[str, str],
    aliases: Sequence[Mapping[str, Any]],
    descriptions: Mapping[str, str] | None,
) -> dict[str, list[str]]:
    """Derive the one authoritative normalized-term projection."""
    terms: dict[str, set[str]] = {"ar": set(), "en": set(), "neutral": set()}
    terms["neutral"].update(_normalized_variants(entity_id, compact=True))
    for locale, value in names.items():
        terms[locale].update(_normalized_variants(value, compact=True))
    if descriptions:
        for locale, value in descriptions.items():
            terms[locale].update(_normalized_variants(value, compact=False))
    for alias in aliases:
        language = alias.get("language")
        channel = language if language in {"ar", "en"} else "neutral"
        terms[channel].update(_normalized_variants(str(alias["value"]), compact=True))
    return {locale: sorted(values) for locale, values in terms.items()}


def build_search_document(
    *,
    entity: Mapping[str, Any],
    facets: Mapping[str, Sequence[str]] | None,
    projected_at: str,
    revision_ids: Sequence[str],
) -> dict[str, Any]:
    """Project one active public Entity into an engine-neutral search document."""
    entity_id = entity.get("id")
    entity_type = entity.get("entity_type")
    if not isinstance(entity_id, str) or not entity_id:
        raise SearchContractError("Entity requires canonical SDA ID")
    if entity_type not in _ENTITY_TYPES:
        raise SearchContractError("Entity has unsupported entity_type")
    if entity.get("record_status") != "active":
        raise SearchContractError("public search indexes active Entity records only")

    names = _public_localized(entity.get("names"), "names")
    aliases = _aliases(entity.get("aliases", []))
    descriptions_raw = entity.get("descriptions")
    descriptions = None if descriptions_raw is None else _public_localized(
        descriptions_raw, "descriptions"
    )
    revisions = sorted(set(_string_array(revision_ids, "revision_ids")))
    if not revisions:
        raise SearchContractError("search document requires at least one Revision ID")
    subtype = entity.get("subtype")
    if subtype is not None and not isinstance(subtype, str):
        raise SearchContractError("Entity subtype must be string or null")

    document: dict[str, Any] = {
        "id": entity_id,
        "entity_type": entity_type,
        "names": names,
        "aliases": aliases,
        "normalized_terms": _normalized_terms_from_public_fields(
            entity_id=entity_id,
            names=names,
            aliases=aliases,
            descriptions=descriptions,
        ),
        "facets": _facets(facets),
        "projected_at": _parse_utc(projected_at, "projected_at"),
        "revision_ids": revisions,
    }
    if subtype is not None:
        document["subtype"] = subtype
    if descriptions is not None:
        document["descriptions"] = descriptions
    return document


def resolve_query_locale(query: str, requested_locale: str) -> str:
    if requested_locale not in {"ar", "en", "auto"}:
        raise SearchContractError("locale must be ar, en, or auto")
    if requested_locale != "auto":
        return requested_locale
    return "ar" if _ARABIC_RE.search(query) else "en"


def _validate_search_document(document: Mapping[str, Any]) -> dict[str, Any]:
    missing = sorted(_SEARCH_DOCUMENT_REQUIRED_KEYS - set(document))
    unknown = sorted(set(document) - _SEARCH_DOCUMENT_ALLOWED_KEYS)
    if missing:
        raise SearchContractError("search document missing fields: " + ", ".join(missing))
    if unknown:
        raise SearchContractError(
            "search document contains unknown fields: " + ", ".join(unknown)
        )

    entity_id = document.get("id")
    if not isinstance(entity_id, str) or not entity_id:
        raise SearchContractError("search document requires canonical ID")
    entity_type = document.get("entity_type")
    if entity_type not in _ENTITY_TYPES:
        raise SearchContractError("search document has unsupported entity_type")
    subtype = document.get("subtype")
    if "subtype" in document and subtype is not None and not isinstance(subtype, str):
        raise SearchContractError("search document subtype must be string or null")

    names = _public_localized(document.get("names"), "search document names")
    aliases = _aliases(document.get("aliases"))
    descriptions_raw = document.get("descriptions")
    descriptions = None if descriptions_raw is None else _public_localized(
        descriptions_raw, "search document descriptions"
    )
    facets = _facets(document.get("facets"), require_complete=True)
    projected_at = _parse_utc(
        document.get("projected_at"), "search document projected_at"
    )
    revisions = _string_array(
        document.get("revision_ids"), "search document revision_ids"
    )
    if not revisions:
        raise SearchContractError("search document requires at least one Revision ID")

    normalized_terms = document.get("normalized_terms")
    if not isinstance(normalized_terms, Mapping) or set(normalized_terms) != {
        "ar", "en", "neutral"
    }:
        raise SearchContractError("search document normalized_terms is malformed")
    actual_terms: dict[str, list[str]] = {}
    for locale in ("ar", "en", "neutral"):
        actual_terms[locale] = sorted(
            _string_array(normalized_terms[locale], f"normalized_terms.{locale}")
        )
    expected_terms = _normalized_terms_from_public_fields(
        entity_id=entity_id,
        names=names,
        aliases=aliases,
        descriptions=descriptions,
    )
    if actual_terms != expected_terms:
        raise SearchContractError(
            "search document normalized_terms do not match the deterministic public-field projection"
        )

    return {
        "id": entity_id,
        "entity_type": entity_type,
        "subtype": subtype,
        "names": names,
        "aliases": aliases,
        "descriptions": descriptions,
        "normalized_terms": actual_terms,
        "facets": facets,
        "projected_at": projected_at,
        "revision_ids": revisions,
    }


def _filters_match(document: Mapping[str, Any], filters: Mapping[str, list[str]]) -> bool:
    entity_types = filters["entity_types"]
    if entity_types and document.get("entity_type") not in set(entity_types):
        return False
    facets = document["facets"]
    for key in _FACET_KEYS:
        requested = filters[key]
        if requested and not set(requested).intersection(facets[key]):
            return False
    return True


def _field_terms(document: Mapping[str, Any], locale: str) -> dict[str, set[str]]:
    fields: dict[str, set[str]] = {
        "id": _normalized_variants(str(document["id"]), compact=True),
        "name": set(), "alias": set(), "description": set(),
    }
    for value in document["names"].values():
        fields["name"].update(_normalized_variants(value, compact=True))
    for alias in document["aliases"]:
        fields["alias"].update(_normalized_variants(alias["value"], compact=True))
    descriptions = document.get("descriptions")
    if isinstance(descriptions, Mapping):
        preferred = descriptions.get(locale)
        if isinstance(preferred, str):
            fields["description"].update(_normalized_variants(preferred))
        for other_locale, value in descriptions.items():
            if other_locale != locale:
                fields["description"].update(_normalized_variants(value))

    declared: set[str] = set()
    for values in document["normalized_terms"].values():
        declared.update(values)
    return {field: values.intersection(declared) for field, values in fields.items()}


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
        field for field in ("name", "alias")
        if any(term.startswith(normalized_query) for term in fields[field])
    ]
    if prefix_fields:
        return "prefix", prefix_fields
    query_tokens = _tokens({normalized_query})
    if not query_tokens:
        return None
    field_tokens = {field: _tokens(values) for field, values in fields.items()}
    combined_tokens: set[str] = set()
    for values in field_tokens.values():
        combined_tokens.update(values)
    if query_tokens.issubset(combined_tokens):
        matched_fields = [
            field for field in ("id", "name", "alias", "description")
            if query_tokens.intersection(field_tokens[field])
        ]
        return "token", matched_fields or ["name"]
    return None


def execute_reference_lexical_search(
    *, documents: Sequence[Mapping[str, Any]], query: Mapping[str, Any]
) -> dict[str, Any]:
    """Execute deterministic reference semantics for v0.1 lexical search."""
    if not isinstance(query, Mapping):
        raise SearchContractError("query must be an object")
    missing_query = sorted(_QUERY_KEYS - set(query))
    unknown_query = sorted(set(query) - _QUERY_KEYS)
    if missing_query:
        raise SearchContractError("query missing required fields: " + ", ".join(missing_query))
    if unknown_query:
        raise SearchContractError("query contains unknown fields: " + ", ".join(unknown_query))

    raw_query = query["query"]
    requested_locale = query["locale"]
    limit = query["limit"]
    if not isinstance(raw_query, str) or not raw_query.strip():
        raise SearchContractError("query requires non-empty text")
    if len(raw_query) > 256:
        raise SearchContractError("query exceeds 256 characters")
    if not isinstance(requested_locale, str):
        raise SearchContractError("locale must be ar, en, or auto")
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 50:
        raise SearchContractError("limit must be an integer from 1 to 50")

    filters = _query_filters(query["filters"])
    locale = resolve_query_locale(raw_query, requested_locale)
    normalized_query = normalize_search_text(raw_query)
    if not normalized_query:
        raise SearchContractError("query is empty after normalization")
    if not isinstance(documents, Sequence) or isinstance(documents, (str, bytes)):
        raise SearchContractError("documents must be an array")

    candidates: list[tuple[int, str, str, Mapping[str, Any], str, list[str]]] = []
    seen_ids: set[str] = set()
    for raw_document in documents:
        if not isinstance(raw_document, Mapping):
            raise SearchContractError("search document must be an object")
        document = _validate_search_document(raw_document)
        document_id = str(document["id"])
        if document_id in seen_ids:
            raise SearchContractError(f"duplicate search document ID: {document_id}")
        seen_ids.add(document_id)
        if not _filters_match(document, filters):
            continue
        match = _match_document(document, normalized_query, locale)
        if match is None:
            continue
        quality, matched_fields = match
        names = document["names"]
        display_name = names.get(locale) or names.get("ar") or names.get("en") or document_id
        candidates.append((
            _QUALITY_ORDER[quality], normalize_search_text(str(display_name)),
            document_id, document, quality, matched_fields,
        ))

    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    hits: list[dict[str, Any]] = []
    for rank, (_, _, document_id, document, quality, matched_fields) in enumerate(
        candidates[:limit], start=1
    ):
        descriptions = document.get("descriptions")
        hits.append({
            "rank": rank,
            "id": document_id,
            "entity_type": document["entity_type"],
            "names": dict(document["names"]),
            "descriptions": None if descriptions is None else dict(descriptions),
            "match_quality": quality,
            "matched_fields": sorted(set(matched_fields)),
        })

    return {
        "query": raw_query,
        "normalized_query": normalized_query,
        "locale": locale,
        "total": len(candidates),
        "hits": hits,
    }
