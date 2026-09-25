"""Small deterministic HTML text/paragraph extractor for M1.

This is intentionally not a general article-extraction framework. It provides a
stable, testable primitive for the first source adapter and may later be replaced
behind the same Evidence contract if a dedicated parser is explicitly adopted.
"""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser

_WHITESPACE = re.compile(r"\s+")
_BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "noscript", "svg"}


def normalize_text(value: str) -> str:
    return _WHITESPACE.sub(" ", html.unescape(value)).strip()


def text_sha256(value: str) -> str:
    return hashlib.sha256(normalize_text(value).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class TextBlock:
    index: int
    tag: str
    text: str
    sha256: str


class _BlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[TextBlock] = []
        self._active_tag: str | None = None
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        tag = tag.lower()
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS and self._active_tag is None:
            self._active_tag = tag
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._skip_depth or self._active_tag is None:
            return
        self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if self._active_tag == tag:
            text = normalize_text(" ".join(self._parts))
            if text:
                self.blocks.append(
                    TextBlock(
                        index=len(self.blocks) + 1,
                        tag=tag,
                        text=text,
                        sha256=text_sha256(text),
                    )
                )
            self._active_tag = None
            self._parts = []


def extract_text_blocks(content: bytes, *, encoding: str = "utf-8") -> list[TextBlock]:
    """Extract normalized heading/paragraph blocks in document order."""
    parser = _BlockParser()
    parser.feed(content.decode(encoding, errors="replace"))
    parser.close()
    return parser.blocks
