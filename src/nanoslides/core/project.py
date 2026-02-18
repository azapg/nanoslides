"""Local project state helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any
import unicodedata

from pydantic import BaseModel, Field, field_validator
import yaml

PROJECT_STATE_FILE = Path("slides.yaml")
_SLIDE_ID_TOKEN_PATTERN = re.compile(r"[a-zA-Z0-9]+")
_SLIDE_ID_STOPWORDS = {
    "about",
    "a",
    "an",
    "and",
    "be",
    "for",
    "in",
    "is",
    "of",
    "on",
    "slide",
    "the",
    "this",
    "to",
    "use",
    "with",
}


def new_slide_id() -> str:
    """Return a default slide identifier."""
    return "slide"


def suggest_slide_id(prompt: str, *, max_words: int = 3) -> str:
    """Derive a short, human-readable slide id from a prompt."""
    normalized_prompt = _ascii_normalize(prompt)
    tokens = [token.lower() for token in _SLIDE_ID_TOKEN_PATTERN.findall(normalized_prompt)]
    filtered = [token for token in tokens if token not in _SLIDE_ID_STOPWORDS]
    selected = (filtered or tokens)[:max_words]
    if not selected:
        return "slide"
    return "-".join(selected)


def dedupe_slide_id(base_id: str, existing_ids: set[str]) -> str:
    """Ensure slide id uniqueness by appending numeric suffixes when needed."""
    normalized_base = _normalize_slide_id(base_id)
    candidate = normalized_base
    suffix = 2
    while candidate in existing_ids:
        candidate = f"{normalized_base}-{suffix}"
        suffix += 1
    return candidate


class SlideEntry(BaseModel):
    """Metadata for a generated slide."""

    id: str = Field(default_factory=new_slide_id)
    order: int = Field(default=1, ge=1)
    prompt: str = ""
    image_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("id", mode="before")
    @classmethod
    def normalize_id(cls, value: Any) -> str:
        if value is None or (isinstance(value, str) and not value.strip()):
            return new_slide_id()
        return str(value)

    @field_validator("order", mode="before")
    @classmethod
    def normalize_order(cls, value: Any) -> int:
        if value in (None, ""):
            return 1
        return int(value)


class ProjectState(BaseModel):
    """State file model stored in ./slides.yaml."""

    name: str
    created_at: datetime
    engine: str
    slides: list[SlideEntry] = Field(default_factory=list)


def load_project_state(path: Path = PROJECT_STATE_FILE) -> ProjectState:
    """Load local project state from YAML."""
    raw_data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data = raw_data if raw_data is not None else {}
    slides = data.get("slides")
    if isinstance(slides, list):
        existing_ids: set[str] = set()
        for index, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                continue
            if slide.get("order") in (None, ""):
                slide["order"] = index
            raw_id = slide.get("id")
            if raw_id in (None, ""):
                base_id = suggest_slide_id(str(slide.get("prompt", "")))
            else:
                base_id = str(raw_id)
            unique_id = dedupe_slide_id(base_id, existing_ids)
            slide["id"] = unique_id
            existing_ids.add(unique_id)
    return ProjectState.model_validate(data)


def save_project_state(state: ProjectState, path: Path = PROJECT_STATE_FILE) -> None:
    """Write local project state to YAML."""
    serialized = state.model_dump(mode="json")
    path.write_text(yaml.safe_dump(serialized, sort_keys=False), encoding="utf-8")


def _normalize_slide_id(value: str) -> str:
    normalized = _ascii_normalize(value)
    tokens = [token.lower() for token in _SLIDE_ID_TOKEN_PATTERN.findall(normalized)]
    if not tokens:
        return "slide"
    return "-".join(tokens[:3])


def _ascii_normalize(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")

