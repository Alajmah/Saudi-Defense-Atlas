"""Bounded deterministic parser for the first M1 official release.

Phase 1 analyzes source content and produces a canonical article fingerprint plus
Evidence candidates without assigning project IDs. Phase 2 materializes Evidence
after the caller has derived the final Document ID. This avoids circular identity.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .html_paragraphs import (
    TextBlock,
    extract_text_blocks,
    extract_visible_text,
    normalize_text,
    text_sha256,
)

_EXPECTED_TITLE = "AFLCMC delivers final F-15SA to Royal Saudi Air Force"
_MONTHS = {
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "may": 5,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}
_PUBLISHED_RE = re.compile(
    r"\bPublished\s+([A-Za-z]{3})\.?\s+(\d{1,2}),\s+(\d{4})\b",
    re.IGNORECASE,
)
_DELIVERY_DAY_RE = re.compile(r"\bdelivered\s+(?:on\s+)?Dec\.?\s+10\b", re.IGNORECASE)


class SourceParseError(ValueError):
    """Raised when the registered page no longer satisfies parser assumptions."""


@dataclass(frozen=True)
class EvidenceCandidate:
    label: str
    selector: str
    text_sha256: str
    notes: str


@dataclass(frozen=True)
class ParsedF15SARelease:
    title: str
    published_date: str
    reported_delivery_date: str
    delivery_year_derived_from_publication: bool
    canonical_content_sha256: str
    canonical_content_length_bytes: int
    evidence_candidates: tuple[EvidenceCandidate, ...]


def _unique_block(
    blocks: Iterable[TextBlock], *, label: str, required_tokens: tuple[str, ...]
) -> TextBlock:
    lowered_tokens = tuple(token.casefold() for token in required_tokens)
    matches = [
        block
        for block in blocks
        if all(token in block.text.casefold() for token in lowered_tokens)
    ]
    if len(matches) != 1:
        raise SourceParseError(
            f"expected exactly one {label} block, found {len(matches)}"
        )
    return matches[0]


def _parse_publication_date(visible_text: str) -> tuple[date, str]:
    matches = list(_PUBLISHED_RE.finditer(visible_text))
    if len(matches) != 1:
        raise SourceParseError(
            f"expected exactly one publication-date marker, found {len(matches)}"
        )
    match = matches[0]
    month = _MONTHS.get(match.group(1).lower())
    if month is None:
        raise SourceParseError(f"unsupported publication month: {match.group(1)}")
    parsed = date(int(match.group(3)), month, int(match.group(2)))
    return parsed, normalize_text(match.group(0))


def _evidence_id(document_id: str, label: str, digest: str) -> str:
    raw = f"{document_id}|{label}|{digest}".encode("utf-8")
    suffix = hashlib.sha256(raw).hexdigest()[:20].upper()
    return f"SDA-EVID-{suffix}"


def _block_candidate(
    *, label: str, block: TextBlock, article_relative_index: int
) -> EvidenceCandidate:
    return EvidenceCandidate(
        label=label,
        selector=(
            f"article-block:{block.tag}:{article_relative_index}:"
            f"sha256:{block.sha256}"
        ),
        text_sha256=block.sha256,
        notes=(
            "Text is identified by normalized article-relative block hash; "
            "source prose is not copied by default."
        ),
    )


def _metadata_candidate(*, label: str, matched_text: str) -> EvidenceCandidate:
    digest = text_sha256(matched_text)
    return EvidenceCandidate(
        label=label,
        selector=f"visible-text-regex:{label}:sha256:{digest}",
        text_sha256=digest,
        notes=(
            "Publication metadata match; exact source text is represented by hash, "
            "not stored excerpt."
        ),
    )


def _article_material(
    *, title: str, published_marker: str, body_blocks: list[TextBlock]
) -> bytes:
    normalized = "\n".join(
        [
            normalize_text(title),
            normalize_text(published_marker),
            *(normalize_text(block.text) for block in body_blocks),
        ]
    )
    return normalized.encode("utf-8")


def analyze_release(content: bytes) -> ParsedF15SARelease:
    """Analyze registered source bytes without assigning project record IDs."""
    blocks = extract_text_blocks(content)
    visible_text = extract_visible_text(content)

    title_matches = [block for block in blocks if block.text == _EXPECTED_TITLE]
    if len(title_matches) != 1:
        raise SourceParseError(
            f"expected registered title exactly once, found {len(title_matches)}"
        )

    published, published_marker = _parse_publication_date(visible_text)

    delivery = _unique_block(
        blocks,
        label="delivery",
        required_tokens=("F-15SA", "delivered", "Dec. 10", "Royal Saudi Air Force"),
    )
    if not _DELIVERY_DAY_RE.search(delivery.text):
        raise SourceParseError("delivery block does not contain the expected Dec. 10 date form")

    variant = _unique_block(
        blocks,
        label="variant relationship",
        required_tokens=("F-15SA", "advanced version", "F-15S", "Royal Saudi Air Force"),
    )
    producer = _unique_block(
        blocks,
        label="producer",
        required_tokens=("Boeing-produced", "aircraft"),
    )
    article_end = _unique_block(
        blocks,
        label="article end",
        required_tokens=(
            "spares",
            "simulators",
            "training",
            "technical documentation",
            "program support",
        ),
    )

    if not (delivery.index <= producer.index <= article_end.index):
        raise SourceParseError("producer evidence falls outside the bounded article body")
    if not (delivery.index <= variant.index <= article_end.index):
        raise SourceParseError("variant evidence falls outside the bounded article body")

    body_blocks = [
        block for block in blocks if delivery.index <= block.index <= article_end.index
    ]
    if not body_blocks or body_blocks[0] != delivery or body_blocks[-1] != article_end:
        raise SourceParseError("could not form a stable bounded article body")

    article_relative = {
        block.index: index for index, block in enumerate(body_blocks, start=1)
    }

    canonical_material = _article_material(
        title=_EXPECTED_TITLE,
        published_marker=published_marker,
        body_blocks=body_blocks,
    )
    canonical_digest = hashlib.sha256(canonical_material).hexdigest()

    delivery_date = date(published.year, 12, 10)
    delta_days = (published - delivery_date).days
    if delta_days < 0 or delta_days > 31:
        raise SourceParseError(
            "cannot safely derive delivery year from publication context"
        )

    candidates = (
        _metadata_candidate(label="publication-date", matched_text=published_marker),
        _block_candidate(
            label="final-delivery",
            block=delivery,
            article_relative_index=article_relative[delivery.index],
        ),
        _block_candidate(
            label="variant-and-operator",
            block=variant,
            article_relative_index=article_relative[variant.index],
        ),
        _block_candidate(
            label="manufacturer-context",
            block=producer,
            article_relative_index=article_relative[producer.index],
        ),
    )

    return ParsedF15SARelease(
        title=_EXPECTED_TITLE,
        published_date=published.isoformat(),
        reported_delivery_date=delivery_date.isoformat(),
        delivery_year_derived_from_publication=True,
        canonical_content_sha256=canonical_digest,
        canonical_content_length_bytes=len(canonical_material),
        evidence_candidates=candidates,
    )


def materialize_evidence(
    parsed: ParsedF15SARelease, *, document_id: str, captured_at: str
) -> tuple[dict, ...]:
    """Assign stable Evidence IDs after the final Document ID is known."""
    records: list[dict] = []
    for candidate in parsed.evidence_candidates:
        records.append(
            {
                "id": _evidence_id(
                    document_id, candidate.label, candidate.text_sha256
                ),
                "document_id": document_id,
                "locator": {
                    "fragment": candidate.label,
                    "selector": candidate.selector,
                },
                "excerpt": None,
                "excerpt_sha256": candidate.text_sha256,
                "language": "en",
                "captured_at": captured_at,
                "capture_method": "deterministic_parser",
                "notes": candidate.notes,
            }
        )
    return tuple(records)
