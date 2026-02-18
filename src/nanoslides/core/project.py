"""Local project state helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator
import yaml

PROJECT_STATE_FILE = Path("slides.yaml")


def new_slide_id() -> str:
    """Return a unique identifier for a slide entry."""
    return f"slide-{uuid4().hex}"


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
        for index, slide in enumerate(slides, start=1):
            if isinstance(slide, dict) and slide.get("order") in (None, ""):
                slide["order"] = index
    return ProjectState.model_validate(data)


def save_project_state(state: ProjectState, path: Path = PROJECT_STATE_FILE) -> None:
    """Write local project state to YAML."""
    serialized = state.model_dump(mode="json")
    path.write_text(yaml.safe_dump(serialized, sort_keys=False), encoding="utf-8")

