"""Helpers for injecting text file context into CLI prompts."""

from __future__ import annotations

from pathlib import Path

_MAX_REFERENCE_FILE_CHARS = 12000


def resolve_reference_files(reference_files: list[Path] | None) -> list[Path]:
    """Resolve and deduplicate ad-hoc reference files."""
    seen: set[str] = set()
    resolved: list[Path] = []
    for raw_path in reference_files or []:
        path = raw_path.expanduser().resolve()
        normalized = str(path)
        if normalized in seen:
            continue
        seen.add(normalized)
        resolved.append(path)
    return resolved


def inject_reference_file_context(text: str, reference_files: list[Path]) -> str:
    """Append referenced file contents to prompt/instruction text."""
    if not reference_files:
        return text

    sections = []
    for path in reference_files:
        content, truncated = _read_text_file(path)
        truncated_note = "\n[...truncated...]" if truncated else ""
        sections.append(
            f"Reference file: {path}\n"
            "----- BEGIN FILE -----\n"
            f"{content}{truncated_note}\n"
            "----- END FILE -----"
        )

    references_block = "\n\n".join(sections)
    return (
        f"{text}\n\n"
        "Use the following reference files as factual context for this slide. "
        "If the prompt conflicts with the files, prefer file details.\n\n"
        f"{references_block}"
    )


def add_reference_file_metadata(
    metadata: dict[str, object],
    reference_files: list[Path],
) -> dict[str, object]:
    """Record reference file paths in slide metadata."""
    if not reference_files:
        return metadata
    return {
        **metadata,
        "reference_files": [str(path) for path in reference_files],
    }


def _read_text_file(path: Path) -> tuple[str, bool]:
    raw_bytes = path.read_bytes()
    if b"\x00" in raw_bytes:
        raise ValueError(f"Reference file appears to be binary and cannot be used: {path}")
    decoded = raw_bytes.decode("utf-8", errors="replace")
    if len(decoded) <= _MAX_REFERENCE_FILE_CHARS:
        return decoded, False
    return decoded[:_MAX_REFERENCE_FILE_CHARS], True
