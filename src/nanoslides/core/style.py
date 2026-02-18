"""Style persistence and resolution helpers."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

PROJECT_STYLE_PATH = Path("style.json")
GLOBAL_STYLES_PATH = Path.home() / ".nanoslides" / "styles.json"


class StyleDefinition(BaseModel):
    """Reusable style payload used by project and global styles."""

    base_prompt: str = ""
    negative_prompt: str = ""
    reference_images: list[str] = Field(default_factory=list)
    reference_comments: list[str] = Field(default_factory=list)


class ProjectStyleConfig(StyleDefinition):
    """Project style file model stored in ./style.json."""

    style_id: str | None = None


class GlobalStylesConfig(BaseModel):
    """Global style registry stored in ~/.nanoslides/styles.json."""

    styles: dict[str, StyleDefinition] = Field(default_factory=dict)


class ResolvedStyle(StyleDefinition):
    """Effective style context resolved for a generation/edit request."""

    style_id: str | None = None


def merge_style_references(style: ResolvedStyle, references: list[Path]) -> ResolvedStyle:
    """Merge ad-hoc reference paths into a resolved style context."""
    if not references:
        return style

    merged_reference_images = _unique(
        [*style.reference_images, *(str(path.expanduser().resolve()) for path in references)]
    )
    return style.model_copy(update={"reference_images": merged_reference_images})


def load_project_style(path: Path = PROJECT_STYLE_PATH) -> ProjectStyleConfig | None:
    """Load project style config when present."""
    if not path.exists():
        return None
    return ProjectStyleConfig.model_validate(_load_json(path))


def save_project_style(style: ProjectStyleConfig, path: Path = PROJECT_STYLE_PATH) -> None:
    """Persist project style config to JSON."""
    _save_json(path, style.model_dump(mode="json"))


def load_global_styles(path: Path = GLOBAL_STYLES_PATH) -> GlobalStylesConfig:
    """Load global style registry, returning defaults when missing."""
    if not path.exists():
        return GlobalStylesConfig()
    return GlobalStylesConfig.model_validate(_load_json(path))


def save_global_styles(styles: GlobalStylesConfig, path: Path = GLOBAL_STYLES_PATH) -> None:
    """Persist global style registry to JSON."""
    _save_json(path, styles.model_dump(mode="json"))


def resolve_style_context(
    style_id: str | None = None,
    *,
    project_style_path: Path = PROJECT_STYLE_PATH,
    global_styles_path: Path = GLOBAL_STYLES_PATH,
) -> ResolvedStyle:
    """Resolve global + project style settings into a single effective style."""
    project_style = load_project_style(project_style_path)
    global_styles = load_global_styles(global_styles_path)

    requested_id = _normalize_style_id(style_id)
    effective_style_id = requested_id or (
        _normalize_style_id(project_style.style_id) if project_style else None
    )

    global_style = (
        global_styles.styles.get(effective_style_id, StyleDefinition())
        if effective_style_id
        else StyleDefinition()
    )
    project_base = project_style or ProjectStyleConfig()

    return ResolvedStyle(
        style_id=effective_style_id,
        base_prompt=_join_non_empty(global_style.base_prompt, project_base.base_prompt),
        negative_prompt=_join_non_empty(
            global_style.negative_prompt, project_base.negative_prompt
        ),
        reference_images=_unique(
            _resolve_reference_images(
                global_style.reference_images, global_styles_path.parent
            )
            + _resolve_reference_images(
                project_base.reference_images, project_style_path.parent
            )
        ),
        reference_comments=_unique(
            [*global_style.reference_comments, *project_base.reference_comments]
        ),
    )


def _normalize_style_id(style_id: str | None) -> str | None:
    if style_id is None:
        return None
    cleaned = style_id.strip()
    if not cleaned or cleaned == "default":
        return None
    return cleaned


def _join_non_empty(*values: str) -> str:
    return "\n\n".join(value.strip() for value in values if value.strip())


def _resolve_reference_images(paths: list[str], base_dir: Path) -> list[str]:
    resolved_paths: list[str] = []
    for path in paths:
        image_path = Path(path).expanduser()
        if not image_path.is_absolute():
            image_path = (base_dir / image_path).resolve()
        resolved_paths.append(str(image_path))
    return resolved_paths


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _load_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
