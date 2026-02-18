"""Generate command implementation."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from nanoslides.core.config import GlobalConfig, get_gemini_api_key, load_global_config
from nanoslides.core.project import (
    PROJECT_STATE_FILE,
    SlideEntry,
    load_project_state,
    save_project_state,
)
from nanoslides.engines.nanobanana import NanoBananaModel, NanoBananaSlideEngine

console = Console()


def generate_command(
    ctx: typer.Context,
    prompt: str = typer.Argument(..., help="Prompt used to generate the slide."),
    model: NanoBananaModel = typer.Option(
        NanoBananaModel.PRO,
        "--model",
        help="NanoBanana model selector.",
        case_sensitive=False,
    ),
    style_id: str = typer.Option("default", "--style-id", help="Style preset ID."),
    ref_image: Path | None = typer.Option(
        None,
        "--ref-image",
        help="Optional reference image path.",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output-dir",
        help="Directory where generated images are saved.",
    ),
) -> None:
    """Generate a slide with the NanoBanana engine."""
    config = _resolve_config(ctx)
    target_output_dir = output_dir or Path(config.default_output_dir)
    api_key = get_gemini_api_key(config)
    try:
        engine = NanoBananaSlideEngine(
            model=model,
            api_key=api_key,
            output_dir=target_output_dir,
        )
        result = engine.generate(
            prompt=prompt,
            style_id=style_id,
            ref_image=ref_image.read_bytes() if ref_image else None,
        )
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(f"[bold red]Generation failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    _append_slide_to_project(result.revised_prompt, result.local_path, result.metadata)

    console.print(
        f"[bold green]Generated slide with NanoBanana ({model.value}).[/]\n"
        f"Saved to [bold]{result.local_path}[/]"
    )


def _resolve_config(ctx: typer.Context) -> GlobalConfig:
    if ctx.obj and isinstance(ctx.obj.get("config"), GlobalConfig):
        return ctx.obj["config"]
    return load_global_config()


def _append_slide_to_project(
    prompt: str,
    local_path: Path | None,
    metadata: dict[str, object],
) -> None:
    if not PROJECT_STATE_FILE.exists():
        return

    project = load_project_state()
    project.slides.append(
        SlideEntry(
            prompt=prompt,
            image_path=str(local_path) if local_path else None,
            metadata=metadata,
        )
    )
    save_project_state(project)
