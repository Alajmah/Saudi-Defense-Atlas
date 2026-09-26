"""Allowlisted HTTP acquisition and canonical-content version classification for M1."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .document_identity import (
    IngestionContractError,
    SourceAcquisitionPolicy,
    build_document_record_from_fingerprint,
    content_sha256,
    is_same_fingerprint,
    validate_policy,
    validate_retrieved_url,
)

DEFAULT_MAX_BYTES = 5 * 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_USER_AGENT = "Saudi-Defense-Atlas/0.1 (+https://github.com/Alajmah/Saudi-Defense-Atlas)"


class AcquisitionError(RuntimeError):
    """Raised when an approved source cannot be safely acquired."""


@dataclass(frozen=True)
class FetchResponse:
    content: bytes
    retrieved_url: str
    status_code: int
    media_type: str | None
    etag: str | None
    last_modified: str | None

    @property
    def raw_content_sha256(self) -> str:
        """Hash the exact HTTP response bytes as a retrieval receipt."""
        return content_sha256(self.content)


@dataclass(frozen=True)
class RetrievalReceipt:
    """Observation metadata for one successful registered-feed fetch.

    This is intentionally distinct from Document identity: raw page chrome may
    change while canonical article content remains unchanged. Source + feed
    identity preserves monitoring coverage even when no new Document is created.
    """

    source_id: str
    document_key: str
    observed_at: str
    requested_url: str
    retrieved_url: str
    status_code: int
    media_type: str | None
    raw_content_sha256: str
    raw_content_length_bytes: int
    etag: str | None
    last_modified: str | None


@dataclass(frozen=True)
class IngestionResult:
    status: str
    document: Mapping[str, Any]
    receipt: RetrievalReceipt


class AllowlistedRedirectHandler(HTTPRedirectHandler):
    """Refuse a redirect before urllib contacts a non-allowlisted host."""

    def __init__(self, policy: SourceAcquisitionPolicy):
        super().__init__()
        self.policy = policy

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        validate_retrieved_url(self.policy, newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_https(
    policy: SourceAcquisitionPolicy,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    max_bytes: int = DEFAULT_MAX_BYTES,
    user_agent: str = DEFAULT_USER_AGENT,
) -> FetchResponse:
    """Fetch one allowlisted HTTPS document with bounded memory consumption."""
    validate_policy(policy)
    if timeout_seconds <= 0:
        raise IngestionContractError("timeout_seconds must be positive")
    if max_bytes <= 0:
        raise IngestionContractError("max_bytes must be positive")

    request = Request(
        policy.canonical_url,
        headers={
            "User-Agent": user_agent,
            "Accept": "text/html,application/xhtml+xml,application/pdf;q=0.8,*/*;q=0.1",
        },
        method="GET",
    )
    opener = build_opener(AllowlistedRedirectHandler(policy))

    try:
        with opener.open(request, timeout=timeout_seconds) as response:
            status = int(getattr(response, "status", response.getcode()))
            if status != 200:
                raise AcquisitionError(f"unexpected HTTP status {status}")

            final_url = response.geturl()
            validate_retrieved_url(policy, final_url)

            content = response.read(max_bytes + 1)
            if len(content) > max_bytes:
                raise AcquisitionError(
                    f"response exceeds configured limit of {max_bytes} bytes"
                )

            media_type = response.headers.get_content_type()
            return FetchResponse(
                content=content,
                retrieved_url=final_url,
                status_code=status,
                media_type=media_type,
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
            )
    except IngestionContractError:
        raise
    except HTTPError as exc:
        raise AcquisitionError(f"HTTP error {exc.code}") from exc
    except URLError as exc:
        raise AcquisitionError(f"network error: {exc.reason}") from exc


def _receipt(
    *, policy: SourceAcquisitionPolicy, response: FetchResponse, observed_at: str
) -> RetrievalReceipt:
    return RetrievalReceipt(
        source_id=policy.source_id,
        document_key=policy.document_key,
        observed_at=observed_at,
        requested_url=policy.canonical_url,
        retrieved_url=response.retrieved_url,
        status_code=response.status_code,
        media_type=response.media_type,
        raw_content_sha256=response.raw_content_sha256,
        raw_content_length_bytes=len(response.content),
        etag=response.etag,
        last_modified=response.last_modified,
    )


def classify_fetch(
    *,
    policy: SourceAcquisitionPolicy,
    response: FetchResponse,
    observed_at: str,
    canonical_content_sha256: str,
    canonical_content_length_bytes: int,
    previous_document: Mapping[str, Any] | None = None,
    title: Mapping[str, str] | None = None,
    published_at: Mapping[str, Any] | None = None,
) -> IngestionResult:
    """Classify canonical source content as new, unchanged, or changed.

    The caller/source adapter owns canonicalization. Raw HTTP bytes are retained
    only in the RetrievalReceipt and never decide Document versioning directly.
    """
    receipt = _receipt(policy=policy, response=response, observed_at=observed_at)

    if previous_document is not None and is_same_fingerprint(
        previous_document, canonical_content_sha256
    ):
        return IngestionResult(
            status="unchanged",
            document=dict(previous_document),
            receipt=receipt,
        )

    previous_id = None if previous_document is None else str(previous_document["id"])
    document = build_document_record_from_fingerprint(
        policy=policy,
        canonical_content_sha256=canonical_content_sha256,
        canonical_content_length_bytes=canonical_content_length_bytes,
        retrieved_at=observed_at,
        retrieved_url=response.retrieved_url,
        media_type=response.media_type,
        title=title,
        published_at=published_at,
        previous_document_id=previous_id,
    )
    return IngestionResult(
        status="new" if previous_document is None else "changed",
        document=document,
        receipt=receipt,
    )
