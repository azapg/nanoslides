"""In-memory presentation model and slide operations."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from nanoslides.core.project import ProjectState, SlideEntry, dedupe_slide_id, suggest_slide_id


class Presentation(BaseModel):
    """Presentation state managed fully in memory."""

    name: str
    created_at: datetime
    engine: str
    slides: list[SlideEntry] = Field(default_factory=list)

    @classmethod
    def from_project_state(cls, state: ProjectState) -> Presentation:
        """Build an in-memory presentation from persisted project state."""
        return cls(
            name=state.name,
            created_at=state.created_at,
            engine=state.engine,
            slides=list(state.slides),
        )

    def to_project_state(self) -> ProjectState:
        """Convert this in-memory presentation into serializable project state."""
        return ProjectState(
            name=self.name,
            created_at=self.created_at,
            engine=self.engine,
            slides=list(self.slides),
        )

    @property
    def ordered_slides(self) -> list[SlideEntry]:
        """Return slides ordered for display/export."""
        return sorted(self.slides, key=lambda slide: (slide.order, slide.id))

    @property
    def ordered_main_slides(self) -> list[SlideEntry]:
        """Return non-draft slides ordered for presentation flow."""
        return sorted(
            [slide for slide in self.slides if not slide.is_draft],
            key=lambda slide: (slide.order, slide.id),
        )

    def find_slide(self, slide_id: str) -> SlideEntry | None:
        """Find a slide by ID."""
        return next((slide for slide in self.slides if slide.id == slide_id), None)

    def add_slide(
        self,
        *,
        prompt: str,
        image_path: str | None,
        metadata: dict[str, Any],
        slide_id: str | None = None,
        order: int | None = None,
        is_draft: bool = False,
        draft_of: str | None = None,
    ) -> SlideEntry:
        """Add a slide with deduped IDs and managed ordering."""
        existing_ids = {slide.id for slide in self.slides}
        base_id = slide_id or suggest_slide_id(prompt)
        resolved_id = dedupe_slide_id(base_id, existing_ids)
        resolved_order = order or (max((slide.order for slide in self.slides), default=0) + 1)
        entry = SlideEntry(
            id=resolved_id,
            order=resolved_order,
            prompt=prompt,
            image_path=image_path,
            metadata=metadata,
            is_draft=is_draft,
            draft_of=draft_of,
        )
        self.slides.append(entry)
        return entry

    def remove_slide(self, slide_id: str) -> SlideEntry | None:
        """Remove a slide and compact the remaining ordering."""
        target = self.find_slide(slide_id)
        if target is None:
            return None
        self.slides = [slide for slide in self.slides if slide.id != slide_id]
        if not target.is_draft:
            self._replace_non_draft_slides(self.ordered_main_slides)
        return target

    def move_slide(self, slide_id: str, new_pos: int) -> tuple[int, int]:
        """Move a non-draft slide to a new 1-based position."""
        ordered = self.ordered_main_slides
        index = next((idx for idx, slide in enumerate(ordered) if slide.id == slide_id), None)
        if index is None:
            raise ValueError(f"Slide '{slide_id}' was not found.")
        current_pos = index + 1
        moving = ordered.pop(index)
        ordered.insert(new_pos - 1, moving)
        self._replace_non_draft_slides(ordered)
        return current_pos, new_pos

    def create_draft(
        self,
        *,
        source_slide_id: str,
        prompt: str,
        image_path: str,
        metadata: dict[str, Any],
    ) -> SlideEntry:
        """Create a draft variant linked to a source slide."""
        source = self.find_slide(source_slide_id)
        if source is None:
            raise ValueError(f"Source slide '{source_slide_id}' was not found.")
        return self.add_slide(
            prompt=prompt,
            image_path=image_path,
            metadata=metadata,
            slide_id=f"{source.id}-draft",
            order=source.order,
            is_draft=True,
            draft_of=source.id,
        )

    def apply_draft(self, draft_id: str) -> tuple[SlideEntry, SlideEntry]:
        """Apply a draft onto its source slide and remove draft entry."""
        draft = self.find_slide(draft_id)
        if draft is None or not draft.is_draft or not draft.draft_of:
            raise ValueError(f"Draft '{draft_id}' was not found.")
        source = self.find_slide(draft.draft_of)
        if source is None:
            raise ValueError(f"Source slide '{draft.draft_of}' was not found.")

        updated_metadata = {**draft.metadata}
        updated_metadata.pop("review_status", None)
        source.prompt = draft.prompt
        source.image_path = draft.image_path
        source.metadata = updated_metadata
        source.is_draft = False
        source.draft_of = None
        self.slides = [slide for slide in self.slides if slide.id != draft.id]
        return source, draft

    def _replace_non_draft_slides(self, ordered: list[SlideEntry]) -> None:
        drafts = [slide for slide in self.slides if slide.is_draft]
        for index, slide in enumerate(ordered, start=1):
            slide.order = index
        self.slides = ordered + drafts
