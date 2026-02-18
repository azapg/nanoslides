"""Generate command implementation."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from nanoslides.core.config import GlobalConfig, get_gemini_api_key, load_global_config
from nanoslides.core.project import (
    PROJECT_STATE_FILE,
    SlideEntry,
    load_project_state,
    save_project_state,
)
from nanoslides.core.style import (
    ResolvedStyle,
    load_global_styles,
    load_project_style,
    resolve_style_context,
)
from nanoslides.engines.nanobanana import (
    ImageAspectRatio,
    NanoBananaModel,
    NanoBananaSlideEngine,
)

console = Console()


def generate_command(
    ctx: typer.Context,
    prompt: str | None = typer.Argument(
        None, help="Prompt used to generate the slide (prompted if omitted)."
    ),
    model: NanoBananaModel | None = typer.Option(
        None,
        "--model",
        help="NanoBanana model selector.",
        case_sensitive=False,
    ),
    style_id: str | None = typer.Option(
        None,
        "--style-id",
        help="Global style preset ID override (prompted in interactive mode).",
    ),
    ref_image: Path | None = typer.Option(
        None,
        "--ref-image",
        help="Optional reference image path (prompted in interactive mode).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
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
        help="Directory where generated images are saved.",
    ),
    aspect_ratio: ImageAspectRatio = typer.Option(
        ImageAspectRatio.RATIO_16_9,
        "--aspect-ratio",
        case_sensitive=False,
        help="Output image aspect ratio.",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Disable guided prompts and use only provided arguments/options.",
    ),
) -> None:
    """Generate a slide with the NanoBanana engine."""
    selected_prompt = prompt
    selected_model = model
    selected_style_id = style_id
    selected_ref_image = ref_image
    selected_references = list(references or [])
    if not no_interactive and sys.stdin.isatty() and not selected_prompt:
        (
            selected_prompt,
            selected_model,
            selected_style_id,
            selected_ref_image,
        ) = _collect_interactive_inputs(
            prompt=selected_prompt,
            model=selected_model,
            style_id=selected_style_id,
            ref_image=selected_ref_image,
        )

    if not selected_prompt:
        console.print("[bold red]Prompt is required.[/]")
        raise typer.Exit(code=1)

    config = _resolve_config(ctx)
    target_output_dir = output_dir or Path(config.default_output_dir)
    api_key = get_gemini_api_key(config)
    effective_model = selected_model or NanoBananaModel.PRO
    effective_style_id = selected_style_id or "default"
    try:
        with console.status("[bold cyan]Generating slide...[/]", spinner="dots"):
            resolved_style = resolve_style_context(style_id=effective_style_id)
            merged_style = _merge_style_references(
                resolved_style,
                [*selected_references, *([selected_ref_image] if selected_ref_image else [])],
            )
            engine = NanoBananaSlideEngine(
                model=effective_model,
                api_key=api_key,
                output_dir=target_output_dir,
            )
            result = engine.generate(
                prompt=selected_prompt,
                style=merged_style,
                aspect_ratio=aspect_ratio,
            )
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(f"[bold red]Generation failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    _append_slide_to_project(result.revised_prompt, result.local_path, result.metadata)
    style_label = merged_style.style_id or "project/default"
    references_count = len(merged_style.reference_images)
    console.print(
        Panel.fit(
            f"[bold green]Slide generated[/]\n"
            f"Model: [bold]{effective_model.value}[/]\n"
            f"Style: [bold]{style_label}[/]\n"
            f"References: [bold]{references_count}[/]\n"
            f"Aspect ratio: [bold]{aspect_ratio.value}[/]\n"
            f"Saved to [bold]{result.local_path}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


def _collect_interactive_inputs(
    *,
    prompt: str | None,
    model: NanoBananaModel | None,
    style_id: str | None,
    ref_image: Path | None,
) -> tuple[str, NanoBananaModel, str, Path | None]:
    console.print(
        Panel.fit(
            "[bold cyan]Guided generation[/]\nWe'll configure this slide step by step.",
            title="nanoslides",
            border_style="cyan",
        )
    )
    prompt_value = prompt or Prompt.ask("1) Slide prompt")
    model_value = _prompt_model(model)
    style_value = _prompt_style_id(style_id)
    ref_image_value = ref_image or _prompt_reference_image()
    return prompt_value, model_value, style_value, ref_image_value


def _prompt_model(model: NanoBananaModel | None) -> NanoBananaModel:
    default_model = (model or NanoBananaModel.PRO).value
    selected_model = Prompt.ask(
        "2) Model",
        choices=[selector.value for selector in NanoBananaModel],
        default=default_model,
    )
    return NanoBananaModel(selected_model)


def _prompt_style_id(style_id: str | None) -> str:
    project_style = load_project_style()
    global_styles = sorted(load_global_styles().styles.keys())
    default_style_id = (
        style_id
        or (project_style.style_id if project_style and project_style.style_id else None)
        or "default"
    )

    table = Table(title="3) Available style presets", show_header=True, header_style="bold")
    table.add_column("Preset")
    table.add_column("Scope")
    table.add_row("default", "No global preset")
    for preset in global_styles:
        table.add_row(preset, "global")
    console.print(table)

    selected_style_id = Prompt.ask(
        "Style preset ID",
        default=default_style_id,
    ).strip()
    if not selected_style_id:
        return "default"
    return selected_style_id


def _prompt_reference_image() -> Path | None:
    raw_path = Prompt.ask("4) Reference image path (optional)", default="").strip()
    if not raw_path:
        return None

    path = Path(raw_path).expanduser()
    if not path.exists() or not path.is_file():
        raise ValueError(f"Reference image not found: {path}")
    return path


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
    next_order = max((slide.order for slide in project.slides), default=0) + 1
    project.slides.append(
        SlideEntry(
            order=next_order,
            prompt=prompt,
            image_path=str(local_path) if local_path else None,
            metadata=metadata,
        )
    )
    save_project_state(project)


def _merge_style_references(
    style: ResolvedStyle,
    references: list[Path],
) -> ResolvedStyle:
    if not references:
        return style

    merged_reference_images = _unique_strings(
        [
            *style.reference_images,
            *(str(path.expanduser().resolve()) for path in references),
        ]
    )
    return style.model_copy(update={"reference_images": merged_reference_images})


def _unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique
