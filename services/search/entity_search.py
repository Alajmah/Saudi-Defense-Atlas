"""Backend-neutral Arabic/English entity-search baseline for M3.

This module defines deterministic normalization and ordinal matching semantics so
future search engines can be evaluated against the same contract. It is not a
production-scale index and does not assign probabilistic relevance scores.
"""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any


class SearchContractError(ValueError):
    """Raised when canonical entities or search input violate the M3 contract."""


_ARABIC_TRANSLATION = str.maketrans(
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
        "ـ": "",
    }
)


def _collapse_spaces(value: str) -> str:
    return " ".join(value.split())


def fold_search_text(value: str) -> str:
    """Return conservative search folding suitable for Arabic/English lookup.

    Folding is intentionally a search-only derivative. It does not alter the
    canonical name/alias stored in SDA. Arabic alef variants, alif maqsura,
    tatweel, diacritics, punctuation, and Arabic/Persian digits are normalized.
    Taa marbuta and seated hamza forms are deliberately preserved to avoid more
    aggressive semantic conflation in the initial contract.
    """

    if not isinstance(value, str) or not value.strip():
        raise SearchContractError("search text must be a non-empty string")
    normalized = unicodedata.normalize("NFKC", value).casefold().translate(_ARABIC_TRANSLATION)
    without_marks = "".join(
        character
        for character in normalized
        if unicodedata.category(character) not in {"Mn", "Me"}
    )
    separated = "".join(
        character if character.isalnum() else " " for character in without_marks
    )
    folded = _collapse_spaces(separated)
    if not folded:
        raise SearchContractError("search text is empty after normalization")
    return folded


def compact_search_text(value: str) -> str:
    return fold_search_text(value).replace(" ", "")


def _language(value: Any) -> str:
    return value if value in {"ar", "en"} else "und"


def _term(*, language: str, field: str, value: str) -> dict[str, str]:
    return {
        "language": language,
        "field": field,
        "value": value,
        "folded": fold_search_text(value),
        "compact": compact_search_text(value),
    }


def build_entity_search_documents(
    entities: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project active canonical Entities into deterministic search documents."""

    documents: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for entity in entities:
        entity_id = entity.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise SearchContractError("Entity requires canonical SDA ID")
        if entity_id in seen_ids:
            raise SearchContractError(f"duplicate Entity ID: {entity_id}")
        seen_ids.add(entity_id)

        if entity.get("record_status") != "active":
            continue
        entity_type = entity.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise SearchContractError(f"Entity {entity_id} requires entity_type")
        names = entity.get("names")
        if not isinstance(names, Mapping) or not names:
            raise SearchContractError(f"Entity {entity_id} requires canonical names")

        terms: list[dict[str, str]] = []
        seen_terms: set[tuple[str, str, str]] = set()
        for language in ("ar", "en"):
            value = names.get(language)
            if isinstance(value, str) and value:
                key = (language, "canonical_name", value)
                if key not in seen_terms:
                    terms.append(_term(language=language, field="canonical_name", value=value))
                    seen_terms.add(key)

        aliases = entity.get("aliases", [])
        if not isinstance(aliases, Sequence) or isinstance(aliases, (str, bytes)):
            raise SearchContractError(f"Entity {entity_id} aliases must be an array")
        for alias in aliases:
            if not isinstance(alias, Mapping):
                raise SearchContractError(f"Entity {entity_id} alias must be an object")
            value = alias.get("value")
            if not isinstance(value, str) or not value:
                raise SearchContractError(f"Entity {entity_id} alias requires value")
            language = _language(alias.get("language"))
            key = (language, "alias", value)
            if key not in seen_terms:
                terms.append(_term(language=language, field="alias", value=value))
                seen_terms.add(key)

        if not terms:
            raise SearchContractError(f"Entity {entity_id} produced no search terms")
        terms.sort(
            key=lambda item: (
                0 if item["field"] == "canonical_name" else 1,
                item["language"],
                item["folded"],
                item["value"],
            )
        )
        documents.append(
            {
                "id": entity_id,
                "entity_type": entity_type,
                "subtype": entity.get("subtype") if isinstance(entity.get("subtype"), str) else None,
                "names": dict(names),
                "terms": terms,
                "source_record_ids": [entity_id],
            }
        )

    documents.sort(key=lambda item: item["id"])
    return documents


def _detect_locale(query: str) -> str:
    return "ar" if any("\u0600" <= character <= "\u06ff" for character in query) else "en"


def _raw_exact(query: str, value: str) -> bool:
    return _collapse_spaces(unicodedata.normalize("NFKC", query).casefold()) == _collapse_spaces(
        unicodedata.normalize("NFKC", value).casefold()
    )


def _match_type(query: str, query_folded: str, query_compact: str, term: Mapping[str, str]) -> str | None:
    if _raw_exact(query, term["value"]):
        return "exact"
    if query_folded == term["folded"] or query_compact == term["compact"]:
        return "normalized_exact"

    query_tokens = query_folded.split()
    term_tokens = term["folded"].split()
    if query_tokens and all(
        any(term_token.startswith(query_token) for term_token in term_tokens)
        for query_token in query_tokens
    ):
        return "token_prefix"
    if query_folded in term["folded"] or query_compact in term["compact"]:
        return "contains"
    return None


def search_entity_documents(
    documents: Sequence[Mapping[str, Any]],
    *,
    text: str,
    locale: str = "auto",
    entity_types: Sequence[str] = (),
    limit: int = 20,
) -> dict[str, Any]:
    """Run a deterministic lexical/entity baseline over search documents.

    Result order is ordinal and intended as an acceptance baseline for future
    engines. It is not a calibrated relevance score.
    """

    if locale not in {"ar", "en", "auto"}:
        raise SearchContractError("locale must be ar, en, or auto")
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise SearchContractError("limit must be an integer >= 1")
    if not isinstance(entity_types, Sequence) or isinstance(entity_types, (str, bytes)):
        raise SearchContractError("entity_types must be an array")
    filters = list(entity_types)
    if len(set(filters)) != len(filters) or any(not isinstance(value, str) or not value for value in filters):
        raise SearchContractError("entity_types must contain unique non-empty strings")

    query_folded = fold_search_text(text)
    query_compact = query_folded.replace(" ", "")
    preferred_locale = _detect_locale(text) if locale == "auto" else locale
    match_priority = {"exact": 0, "normalized_exact": 1, "token_prefix": 2, "contains": 3}

    candidates: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    seen_document_ids: set[str] = set()
    for document in documents:
        document_id = document.get("id")
        if not isinstance(document_id, str) or not document_id:
            raise SearchContractError("search document requires SDA ID")
        if document_id in seen_document_ids:
            raise SearchContractError(f"duplicate search document ID: {document_id}")
        seen_document_ids.add(document_id)
        entity_type = document.get("entity_type")
        if not isinstance(entity_type, str) or not entity_type:
            raise SearchContractError(f"search document {document_id} requires entity_type")
        if filters and entity_type not in filters:
            continue
        names = document.get("names")
        terms = document.get("terms")
        if not isinstance(names, Mapping) or not names:
            raise SearchContractError(f"search document {document_id} requires names")
        if not isinstance(terms, Sequence) or isinstance(terms, (str, bytes)) or not terms:
            raise SearchContractError(f"search document {document_id} requires terms")

        best: tuple[tuple[Any, ...], Mapping[str, Any], str] | None = None
        for term in terms:
            if not isinstance(term, Mapping):
                raise SearchContractError(f"search document {document_id} has malformed term")
            if not all(isinstance(term.get(field), str) and term.get(field) for field in ("language", "field", "value", "folded", "compact")):
                raise SearchContractError(f"search document {document_id} has incomplete term")
            match_type = _match_type(text, query_folded, query_compact, term)
            if match_type is None:
                continue
            language = term["language"]
            field = term["field"]
            priority = (
                match_priority[match_type],
                0 if field == "canonical_name" else 1,
                0 if language == preferred_locale else (1 if language == "und" else 2),
                term["folded"],
                term["value"],
            )
            if best is None or priority < best[0]:
                best = (priority, term, match_type)

        if best is None:
            continue
        priority, term, match_type = best
        candidates.append(
            (
                (*priority, document_id),
                {
                    "rank": 0,
                    "id": document_id,
                    "entity_type": entity_type,
                    "subtype": document.get("subtype") if isinstance(document.get("subtype"), str) else None,
                    "names": dict(names),
                    "match": {
                        "type": match_type,
                        "language": term["language"],
                        "field": term["field"],
                        "value": term["value"],
                    },
                },
            )
        )

    candidates.sort(key=lambda item: item[0])
    results = [candidate[1] for candidate in candidates[:limit]]
    for index, result in enumerate(results, start=1):
        result["rank"] = index

    return {
        "query": {
            "text": text,
            "locale": locale,
            "entity_types": filters,
        },
        "normalization": {
            "folded": query_folded,
            "compact": query_compact,
        },
        "results": results,
    }
