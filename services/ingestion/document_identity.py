"""Pure deterministic helpers for Document identity and versioning.

A Document fingerprint represents canonicalized source content, not necessarily
raw HTTP response bytes. Web adapters should remove dynamic page chrome before
choosing the fingerprint material. Raw-response hashes belong to retrieval
receipts and must not create false Document versions.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import urlparse

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_SAFE_KEY_RE = re.compile(r"[^A-Za-z0-9]+")


class IngestionContractError(ValueError):
    """Raised when deterministic acquisition inputs violate the M1 contract."""


@dataclass(frozen=True)
class SourceAcquisitionPolicy:
    """Network-independent acquisition policy for one registered document feed."""

    source_id: str
    document_key: str
    canonical_url: str
    allowed_hosts: tuple[str, ...]
    language: str
    document_type: str
    publisher_document_id: str | None = None


def content_sha256(content: bytes) -> str:
    """Return the lowercase SHA-256 digest for exact bytes."""
    return hashlib.sha256(content).hexdigest()


def normalize_document_key(value: str) -> str:
    """Convert a registry document key to a bounded stable ID component."""
    normalized = _SAFE_KEY_RE.sub("-", value.strip()).strip("-").upper()
    if not normalized:
        raise IngestionContractError("document_key must contain an alphanumeric character")
    if len(normalized) <= 48:
        return normalized
    key_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10].upper()
    return f"{normalized[:36]}-{key_hash}"


def _normalize_digest(digest: str) -> str:
    if not _SHA256_RE.fullmatch(digest):
        raise IngestionContractError("digest must be a SHA-256 hex value")
    return digest.lower()


def document_id(document_key: str, digest: str) -> str:
    """Derive a stable SDA Document ID from logical source key + canonical hash."""
    normalized_digest = _normalize_digest(digest)
    return (
        f"SDA-DOC-{normalize_document_key(document_key)}-"
        f"{normalized_digest[:32].upper()}"
    )


def _normalized_host(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise IngestionContractError("registered and retrieved URLs must use HTTPS")
    if not parsed.hostname:
        raise IngestionContractError("URL must contain a hostname")
    return parsed.hostname.lower().rstrip(".")


def validate_policy(policy: SourceAcquisitionPolicy) -> None:
    """Validate source allowlisting rules before any network request occurs."""
    if not policy.source_id:
        raise IngestionContractError("source_id is required")
    normalize_document_key(policy.document_key)

    canonical_host = _normalized_host(policy.canonical_url)
    allowed = {host.lower().rstrip(".") for host in policy.allowed_hosts if host}
    if not allowed:
        raise IngestionContractError("at least one allowed host is required")
    if canonical_host not in allowed:
        raise IngestionContractError("canonical URL host is not allowlisted")


def validate_retrieved_url(policy: SourceAcquisitionPolicy, retrieved_url: str) -> None:
    """Reject redirects outside the source-specific allowlist."""
    validate_policy(policy)
    host = _normalized_host(retrieved_url)
    allowed = {item.lower().rstrip(".") for item in policy.allowed_hosts}
    if host not in allowed:
        raise IngestionContractError(
            f"retrieved URL host {host!r} is outside the source allowlist"
        )


def build_document_record_from_fingerprint(
    *,
    policy: SourceAcquisitionPolicy,
    canonical_content_sha256: str,
    canonical_content_length_bytes: int | None,
    retrieved_at: str,
    retrieved_url: str | None = None,
    media_type: str | None = None,
    title: Mapping[str, str] | None = None,
    published_at: Mapping[str, Any] | None = None,
    previous_document_id: str | None = None,
) -> dict[str, Any]:
    """Build an immutable Document record from a source-adapter fingerprint."""
    validate_policy(policy)
    final_url = retrieved_url or policy.canonical_url
    validate_retrieved_url(policy, final_url)
    digest = _normalize_digest(canonical_content_sha256)
    if canonical_content_length_bytes is not None and canonical_content_length_bytes < 0:
        raise IngestionContractError("canonical_content_length_bytes cannot be negative")

    record: dict[str, Any] = {
        "id": document_id(policy.document_key, digest),
        "source_id": policy.source_id,
        "canonical_url": policy.canonical_url,
        "retrieved_url": final_url,
        "retrieved_at": retrieved_at,
        "language": policy.language,
        "document_type": policy.document_type,
        "media_type": media_type,
        "content_sha256": digest,
        "content_length_bytes": canonical_content_length_bytes,
        "version_of": previous_document_id,
        "publisher_document_id": policy.publisher_document_id,
        "access_notes": None,
        "licensing_notes": None,
    }
    if title:
        record["title"] = dict(title)
    if published_at:
        record["published_at"] = dict(published_at)
    return record


def build_document_record(
    *,
    policy: SourceAcquisitionPolicy,
    content: bytes,
    retrieved_at: str,
    retrieved_url: str | None = None,
    media_type: str | None = None,
    title: Mapping[str, str] | None = None,
    published_at: Mapping[str, Any] | None = None,
    previous_document_id: str | None = None,
) -> dict[str, Any]:
    """Convenience helper when exact bytes are already canonical content material."""
    return build_document_record_from_fingerprint(
        policy=policy,
        canonical_content_sha256=content_sha256(content),
        canonical_content_length_bytes=len(content),
        retrieved_at=retrieved_at,
        retrieved_url=retrieved_url,
        media_type=media_type,
        title=title,
        published_at=published_at,
        previous_document_id=previous_document_id,
    )


def is_same_fingerprint(existing: Mapping[str, Any], digest: str) -> bool:
    """Compare a stored canonical Document fingerprint to a candidate digest."""
    stored = str(existing.get("content_sha256", "")).lower()
    return stored == _normalize_digest(digest)


def is_same_artifact(existing: Mapping[str, Any], content: bytes) -> bool:
    """Convenience comparison when exact bytes are canonical fingerprint material."""
    return is_same_fingerprint(existing, content_sha256(content))
