"""Two chunking strategies used to build comparable retrieval experiments.

Both strategies return a list of ``Chunk`` so downstream code (embedding,
indexing, BM25) doesn't need to know which strategy produced the text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

import tiktoken

_ENCODING = tiktoken.get_encoding("cl100k_base")


@dataclass
class Chunk:
    text: str
    chunk_idx: int


def _encode(text: str) -> list[int]:
    return _ENCODING.encode(text)


def _decode(tokens: list[int]) -> str:
    return _ENCODING.decode(tokens)


def fixed_size_chunks(text: str, chunk_tokens: int = 500, overlap_tokens: int = 50) -> list[Chunk]:
    """Sliding window over token ids, wrapping at chunk_tokens with overlap_tokens overlap."""
    if overlap_tokens >= chunk_tokens:
        raise ValueError("overlap_tokens must be smaller than chunk_tokens")

    text = text.strip()
    if not text:
        return []

    tokens = _encode(text)
    if len(tokens) <= chunk_tokens:
        return [Chunk(text=text, chunk_idx=0)]

    chunks: list[Chunk] = []
    start = 0
    idx = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunk_text = _decode(tokens[start:end]).strip()
        if chunk_text:
            chunks.append(Chunk(text=chunk_text, chunk_idx=idx))
            idx += 1
        if end == len(tokens):
            break
        start = end - overlap_tokens

    return chunks


_HEADING_RE = re.compile(r"^(#{1,6})\s+.*$", re.MULTILINE)


def _split_sections(markdown_text: str) -> list[str]:
    """Split markdown into sections at heading boundaries; falls back to paragraphs."""
    headings = list(_HEADING_RE.finditer(markdown_text))
    if not headings:
        return [part.strip() for part in re.split(r"\n{2,}", markdown_text) if part.strip()]

    sections = []
    for i, match in enumerate(headings):
        start = match.start()
        end = headings[i + 1].start() if i + 1 < len(headings) else len(markdown_text)
        section = markdown_text[start:end].strip()
        if section:
            sections.append(section)

    if headings[0].start() > 0:
        preamble = markdown_text[: headings[0].start()].strip()
        if preamble:
            sections.insert(0, preamble)

    return sections


def structural_chunks(markdown_text: str, max_tokens: int = 500) -> list[Chunk]:
    """Split on heading/paragraph boundaries, merging adjacent small sections up to max_tokens.

    Oversized sections (a single heading whose body alone exceeds max_tokens)
    fall back to fixed_size_chunks for that section only.
    """
    markdown_text = markdown_text.strip()
    if not markdown_text:
        return []

    sections = _split_sections(markdown_text)
    if not sections:
        return []

    chunks: list[Chunk] = []
    buffer = ""
    idx = 0

    def flush():
        nonlocal buffer, idx
        if buffer.strip():
            chunks.append(Chunk(text=buffer.strip(), chunk_idx=idx))
            idx += 1
        buffer = ""

    for section in sections:
        if len(_encode(section)) > max_tokens:
            flush()
            for sub in fixed_size_chunks(section, chunk_tokens=max_tokens, overlap_tokens=0):
                chunks.append(Chunk(text=sub.text, chunk_idx=idx))
                idx += 1
            continue

        candidate = f"{buffer}\n\n{section}".strip() if buffer else section
        if len(_encode(candidate)) > max_tokens:
            flush()
            buffer = section
        else:
            buffer = candidate

    flush()
    return chunks


STRATEGIES = {
    "fixed": fixed_size_chunks,
    "structural": structural_chunks,
}
