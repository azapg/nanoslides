"""Edit command implementation."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from nanoslides.core.config import GlobalConfig, get_gemini_api_key, load_global_config
from nanoslides.core.project import (
    PROJECT_STATE_FILE,
    ProjectState,
    SlideEntry,
    load_project_state,
    save_project_state,
)
from nanoslides.core.style import merge_style_references, resolve_style_context
from nanoslides.engines.nanobanana import NanoBananaModel, NanoBananaSlideEngine

console = Console()


def edit_command(
    ctx: typer.Context,
    target: str = typer.Argument(
        ...,
        help=f"Slide ID from {PROJECT_STATE_FILE} or source image path to edit.",
    ),
    instruction: str = typer.Argument(..., help="Edit instruction."),
    model: NanoBananaModel | None = typer.Option(
        None,
        "--model",
        help="NanoBanana model selector.",
        case_sensitive=False,
    ),
    style_id: str | None = typer.Option(
        None,
        "--style-id",
        help="Global style preset ID override.",
    ),
    references: list[Path] | None = typer.Option(
        None,
        "--references",
        help="Additional reference image paths (repeat --references for multiple files).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory where edited images are saved.",
    ),
) -> None:
    """Edit an existing slide image from an ID or file path."""
    config = _resolve_config(ctx)
    target_output_dir = output_dir or Path(config.default_output_dir)
    api_key = get_gemini_api_key(config)
    effective_model = model or NanoBananaModel.PRO
    effective_style_id = style_id or "default"
    selected_references = list(references or [])

    try:
        with console.status("[bold cyan]Editing slide...[/]", spinner="dots"):
            source_image_path, project_state, slide_entry = _resolve_edit_target(target)
            resolved_style = resolve_style_context(style_id=effective_style_id)
            merged_style = merge_style_references(resolved_style, selected_references)
            engine = NanoBananaSlideEngine(
                model=effective_model,
                api_key=api_key,
                output_dir=target_output_dir,
            )
            result = engine.edit(
                image=source_image_path.read_bytes(),
                instruction=instruction,
                style=merged_style,
            )
            _update_project_slide(
                project_state=project_state,
                slide_entry=slide_entry,
                source_image_path=source_image_path,
                instruction=instruction,
                edited_image_path=result.local_path,
                metadata=result.metadata,
            )
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(f"[bold red]Edit failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    style_label = merged_style.style_id or "project/default"
    references_count = len(merged_style.reference_images)
    source_label = slide_entry.id if slide_entry else str(source_image_path)
    console.print(
        Panel.fit(
            f"[bold green]Slide edited[/]\n"
            f"Source: [bold]{source_label}[/]\n"
            f"Model: [bold]{effective_model.value}[/]\n"
            f"Style: [bold]{style_label}[/]\n"
            f"References: [bold]{references_count}[/]\n"
            f"Saved to [bold]{result.local_path}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


def _resolve_edit_target(target: str) -> tuple[Path, ProjectState | None, SlideEntry | None]:
    target_path = Path(target).expanduser()
    project_state = load_project_state() if PROJECT_STATE_FILE.exists() else None

    if target_path.exists():
        if not target_path.is_file():
            raise ValueError(f"Edit target is not a file: {target_path}")
        resolved_target = target_path.resolve()
        matched_slide = _find_slide_by_path(project_state, resolved_target)
        return resolved_target, project_state, matched_slide

    matched_slide = _find_slide_by_id(project_state, target)
    if matched_slide is None:
        raise ValueError(
            f"Slide target '{target}' was not found. Use a slide ID from {PROJECT_STATE_FILE} "
            "or an existing image path."
        )
    if not matched_slide.image_path:
        raise ValueError(f"Slide '{target}' has no image path in {PROJECT_STATE_FILE}.")

    resolved_target = _resolve_slide_image_path(matched_slide.image_path)
    if not resolved_target.exists() or not resolved_target.is_file():
        raise ValueError(f"Slide image not found: {resolved_target}")
    return resolved_target, project_state, matched_slide


def _find_slide_by_id(
    project_state: ProjectState | None,
    target_id: str,
) -> SlideEntry | None:
    if project_state is None:
        return None
    for slide in project_state.slides:
        if slide.id == target_id:
            return slide
    return None


def _find_slide_by_path(
    project_state: ProjectState | None,
    image_path: Path,
) -> SlideEntry | None:
    if project_state is None:
        return None
    normalized_target = _normalize_path(image_path)
    for slide in project_state.slides:
        if not slide.image_path:
            continue
        if _normalize_path(_resolve_slide_image_path(slide.image_path)) == normalized_target:
            return slide
    return None


def _resolve_slide_image_path(raw_path: str) -> Path:
    image_path = Path(raw_path).expanduser()
    if not image_path.is_absolute():
        image_path = Path.cwd() / image_path
    return image_path.resolve()


def _normalize_path(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def _update_project_slide(
    *,
    project_state: ProjectState | None,
    slide_entry: SlideEntry | None,
    source_image_path: Path,
    instruction: str,
    edited_image_path: Path | None,
    metadata: dict[str, object],
) -> None:
    if project_state is None or slide_entry is None or edited_image_path is None:
        return

    slide_entry.prompt = instruction
    slide_entry.image_path = str(edited_image_path)
    slide_entry.metadata = {
        **metadata,
        "edited_from": str(source_image_path),
    }
    save_project_state(project_state)


def _resolve_config(ctx: typer.Context) -> GlobalConfig:
    if ctx.obj and isinstance(ctx.obj.get("config"), GlobalConfig):
        return ctx.obj["config"]
    return load_global_config()

