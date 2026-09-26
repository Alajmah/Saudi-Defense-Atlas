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


_ENTITY_TYPES = {
    "organization",
    "military_unit",
    "equipment",
    "equipment_variant",
    "facility",
    "exercise",
    "procurement_program",
    "contract",
    "localization_program",
    "country",
}
_FIELD_PRIORITY = {
    "canonical_name": 0,
    "alias": 1,
    "merged_name": 2,
    "merged_alias": 3,
}
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


def _term(
    *, language: str, field: str, value: str, source_record_id: str
) -> dict[str, str]:
    return {
        "language": language,
        "field": field,
        "value": value,
        "folded": fold_search_text(value),
        "compact": compact_search_text(value),
        "source_record_id": source_record_id,
    }


def _add_entity_terms(
    target: dict[str, Any],
    source_entity: Mapping[str, Any],
    *,
    name_field: str,
    alias_field: str,
) -> None:
    source_id = source_entity.get("id")
    if not isinstance(source_id, str) or not source_id:
        raise SearchContractError("search term source requires canonical Entity ID")
    names = source_entity.get("names")
    if not isinstance(names, Mapping) or not names:
        raise SearchContractError(f"Entity {source_id} requires canonical names")

    existing = {
        (
            item["language"],
            item["field"],
            item["value"],
            item["source_record_id"],
        )
        for item in target["terms"]
    }
    for language in ("ar", "en"):
        value = names.get(language)
        if isinstance(value, str) and value:
            key = (language, name_field, value, source_id)
            if key not in existing:
                target["terms"].append(
                    _term(
                        language=language,
                        field=name_field,
                        value=value,
                        source_record_id=source_id,
                    )
                )
                existing.add(key)

    aliases = source_entity.get("aliases", [])
    if not isinstance(aliases, Sequence) or isinstance(aliases, (str, bytes)):
        raise SearchContractError(f"Entity {source_id} aliases must be an array")
    for alias in aliases:
        if not isinstance(alias, Mapping):
            raise SearchContractError(f"Entity {source_id} alias must be an object")
        value = alias.get("value")
        if not isinstance(value, str) or not value:
            raise SearchContractError(f"Entity {source_id} alias requires value")
        language = _language(alias.get("language"))
        key = (language, alias_field, value, source_id)
        if key not in existing:
            target["terms"].append(
                _term(
                    language=language,
                    field=alias_field,
                    value=value,
                    source_record_id=source_id,
                )
            )
            existing.add(key)


def _resolve_merged_target(
    entity_id: str,
    entities_by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    visited: set[str] = set()
    current_id = entity_id
    while True:
        if current_id in visited:
            raise SearchContractError(
                "merged Entity cycle detected: " + " -> ".join(sorted(visited | {current_id}))
            )
        visited.add(current_id)
        entity = entities_by_id.get(current_id)
        if entity is None:
            raise SearchContractError(f"merged Entity target is unknown: {current_id}")
        status = entity.get("record_status")
        if status == "active":
            return current_id
        if status != "merged":
            raise SearchContractError(
                f"merged Entity chain resolves to non-active record {current_id} ({status!r})"
            )
        target_id = entity.get("merged_into")
        if not isinstance(target_id, str) or not target_id:
            raise SearchContractError(f"merged Entity {current_id} requires merged_into")
        current_id = target_id


def build_entity_search_documents(
    entities: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Project canonical Entity identity into deterministic search documents.

    Active records own result identity. Names/aliases from `merged` records are
    retained as lower-priority search terms on their resolved active target so a
    historical/duplicate identity remains discoverable without returning an
    obsolete SDA ID.
    """

    entities_by_id: dict[str, Mapping[str, Any]] = {}
    for entity in entities:
        entity_id = entity.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise SearchContractError("Entity requires canonical SDA ID")
        if entity_id in entities_by_id:
            raise SearchContractError(f"duplicate Entity ID: {entity_id}")
        entities_by_id[entity_id] = entity

    documents_by_id: dict[str, dict[str, Any]] = {}
    for entity_id, entity in entities_by_id.items():
        if entity.get("record_status") != "active":
            continue
        entity_type = entity.get("entity_type")
        if entity_type not in _ENTITY_TYPES:
            raise SearchContractError(f"Entity {entity_id} requires recognized entity_type")
        names = entity.get("names")
        if not isinstance(names, Mapping) or not names:
            raise SearchContractError(f"Entity {entity_id} requires canonical names")
        document: dict[str, Any] = {
            "id": entity_id,
            "entity_type": entity_type,
            "subtype": entity.get("subtype") if isinstance(entity.get("subtype"), str) else None,
            "names": dict(names),
            "terms": [],
            "source_record_ids": [entity_id],
        }
        _add_entity_terms(
            document,
            entity,
            name_field="canonical_name",
            alias_field="alias",
        )
        documents_by_id[entity_id] = document

    for entity_id, entity in entities_by_id.items():
        if entity.get("record_status") != "merged":
            continue
        target_id = _resolve_merged_target(entity_id, entities_by_id)
        target = documents_by_id.get(target_id)
        if target is None:
            raise SearchContractError(
                f"merged Entity {entity_id} did not resolve to an indexed active Entity"
            )
        _add_entity_terms(
            target,
            entity,
            name_field="merged_name",
            alias_field="merged_alias",
        )
        target["source_record_ids"].append(entity_id)

    documents = list(documents_by_id.values())
    for document in documents:
        if not document["terms"]:
            raise SearchContractError(f"Entity {document['id']} produced no search terms")
        document["terms"].sort(
            key=lambda item: (
                _FIELD_PRIORITY[item["field"]],
                item["language"],
                item["folded"],
                item["value"],
                item["source_record_id"],
            )
        )
        document["source_record_ids"] = sorted(set(document["source_record_ids"]))

    documents.sort(key=lambda item: item["id"])
    return documents


def _detect_locale(query: str) -> str:
    return "ar" if any("\u0600" <= character <= "\u06ff" for character in query) else "en"


def _raw_exact(query: str, value: str) -> bool:
    return _collapse_spaces(unicodedata.normalize("NFKC", query).casefold()) == _collapse_spaces(
        unicodedata.normalize("NFKC", value).casefold()
    )


def _match_type(
    query: str,
    query_folded: str,
    query_compact: str,
    term: Mapping[str, str],
) -> str | None:
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
    raw_filters = list(entity_types)
    if (
        len(set(raw_filters)) != len(raw_filters)
        or any(not isinstance(value, str) or value not in _ENTITY_TYPES for value in raw_filters)
    ):
        raise SearchContractError("entity_types must contain unique recognized Entity types")
    filters = sorted(raw_filters)

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
        if entity_type not in _ENTITY_TYPES:
            raise SearchContractError(f"search document {document_id} requires recognized entity_type")
        if filters and entity_type not in filters:
            continue
        names = document.get("names")
        terms = document.get("terms")
        source_record_ids = document.get("source_record_ids")
        if not isinstance(names, Mapping) or not names:
            raise SearchContractError(f"search document {document_id} requires names")
        if not isinstance(terms, Sequence) or isinstance(terms, (str, bytes)) or not terms:
            raise SearchContractError(f"search document {document_id} requires terms")
        if not isinstance(source_record_ids, Sequence) or isinstance(source_record_ids, (str, bytes)):
            raise SearchContractError(f"search document {document_id} requires source_record_ids")
        source_ids = {value for value in source_record_ids if isinstance(value, str) and value}
        if len(source_ids) != len(source_record_ids):
            raise SearchContractError(f"search document {document_id} has invalid source_record_ids")

        best: tuple[tuple[Any, ...], Mapping[str, Any], str] | None = None
        for term in terms:
            if not isinstance(term, Mapping):
                raise SearchContractError(f"search document {document_id} has malformed term")
            required = ("language", "field", "value", "folded", "compact", "source_record_id")
            if not all(isinstance(term.get(field), str) and term.get(field) for field in required):
                raise SearchContractError(f"search document {document_id} has incomplete term")
            field = term["field"]
            if field not in _FIELD_PRIORITY:
                raise SearchContractError(f"search document {document_id} has unknown term field")
            if term["source_record_id"] not in source_ids:
                raise SearchContractError(
                    f"search document {document_id} term references unlisted source record"
                )
            match_type = _match_type(text, query_folded, query_compact, term)
            if match_type is None:
                continue
            language = term["language"]
            priority = (
                match_priority[match_type],
                _FIELD_PRIORITY[field],
                0 if language == preferred_locale else (1 if language == "und" else 2),
                term["folded"],
                term["value"],
                term["source_record_id"],
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
                        "source_record_id": term["source_record_id"],
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
