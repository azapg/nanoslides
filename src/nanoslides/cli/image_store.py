"""CLI helpers for writing generated image bytes to disk."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from nanoslides.core.interfaces import SlideResult

_EXTENSIONS_BY_MIME_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/webp": "webp",
}


def persist_slide_result(
    result: SlideResult,
    *,
    output_dir: Path,
    file_prefix: str = "slide",
) -> Path:
    """Persist a generated slide image and return the local path."""
    if not result.image_bytes:
        raise ValueError("Slide result has no image bytes.")
    mime_type = (result.mime_type or "image/png").lower()
    extension = _EXTENSIONS_BY_MIME_TYPE.get(mime_type, "png")
    output_dir.mkdir(parents=True, exist_ok=True)
    file_name = (
        f"{file_prefix}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}.{extension}"
    )
    local_path = output_dir / file_name
    local_path.write_bytes(result.image_bytes)
    return local_path
