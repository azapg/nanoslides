"""Generate command implementation."""

from __future__ import annotations

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from nanoslides.cli.image_store import persist_slide_result
from nanoslides.cli.reference_files import (
    add_reference_file_metadata,
    inject_reference_file_context,
    resolve_reference_files,
)
from nanoslides.core.config import GlobalConfig, get_gemini_api_key, load_global_config
from nanoslides.core.presentation import Presentation
from nanoslides.core.project import (
    PROJECT_STATE_FILE,
    load_project_state,
    save_project_state,
)
from nanoslides.core.style import (
    load_global_styles,
    merge_style_references,
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
    references: list[Path] | None = typer.Option(
        None,
        "--references",
        help="Additional reference image paths (e.g. --references file1.png file2.png).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    reference_file: list[Path] | None = typer.Option(
        None,
        "--reference-file",
        help="Text file path used as context (repeat --reference-file for multiple files).",
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
    variations: int = typer.Option(
        1,
        "--variations",
        min=1,
        help="Number of variations to generate before choosing one to save.",
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
    selected_reference_files = resolve_reference_files(reference_file)
    try:
        selected_references = _resolve_cli_references(references, ctx.args)
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    if not no_interactive and sys.stdin.isatty() and not selected_prompt:
        (
            selected_prompt,
            selected_model,
            selected_style_id,
            selected_references,
        ) = _collect_interactive_inputs(
            prompt=selected_prompt,
            model=selected_model,
            style_id=selected_style_id,
            references=selected_references,
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
        contextual_prompt = inject_reference_file_context(
            selected_prompt,
            selected_reference_files,
        )
        resolved_style = resolve_style_context(style_id=effective_style_id)
        merged_style = merge_style_references(resolved_style, selected_references)
        engine = NanoBananaSlideEngine(
            model=effective_model,
            api_key=api_key,
        )
        results = []
        for index in range(variations):
            status_message = (
                f"[bold cyan]Generating slide variation {index + 1}/{variations}...[/]"
                if variations > 1
                else "[bold cyan]Generating slide...[/]"
            )
            with console.status(status_message, spinner="dots"):
                results.append(
                    engine.generate(
                        prompt=contextual_prompt,
                        style=merged_style,
                        aspect_ratio=aspect_ratio,
                    )
                )
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except RuntimeError as exc:
        console.print(f"[bold red]Generation failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    selected_index = _select_variation_index(
        count=len(results),
        no_interactive=no_interactive,
    )
    selected_result = results[selected_index]
    selected_metadata = add_reference_file_metadata(
        selected_result.metadata,
        selected_reference_files,
    )
    persisted_path = persist_slide_result(selected_result, output_dir=target_output_dir)
    final_local_path, slide_id = _append_slide_to_project(
        selected_result.revised_prompt,
        persisted_path,
        selected_metadata,
    )
    saved_path = final_local_path or persisted_path
    style_label = merged_style.style_id or "project/default"
    references_count = len(merged_style.reference_images)
    console.print(
        Panel.fit(
            f"[bold green]Slide generated[/]\n"
            f"Slide ID: [bold]{slide_id or 'untracked'}[/]\n"
            f"Model: [bold]{effective_model.value}[/]\n"
            f"Style: [bold]{style_label}[/]\n"
            f"References: [bold]{references_count}[/]\n"
            f"Reference files: [bold]{len(selected_reference_files)}[/]\n"
            f"Variation: [bold]{selected_index + 1}/{len(results)}[/]\n"
            f"Saved to [bold]{saved_path}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


def _collect_interactive_inputs(
    *,
    prompt: str | None,
    model: NanoBananaModel | None,
    style_id: str | None,
    references: list[Path],
) -> tuple[str, NanoBananaModel, str, list[Path]]:
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
    references_value = references or _prompt_references()
    return prompt_value, model_value, style_value, references_value


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


def _prompt_references() -> list[Path]:
    raw_paths = Prompt.ask(
        "4) Reference image paths (optional, comma-separated)",
        default="",
    ).strip()
    if not raw_paths:
        return []

    references: list[Path] = []
    for raw_path in raw_paths.split(","):
        path = Path(raw_path.strip()).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"Reference image not found: {path}")
        references.append(path)
    return references


def _resolve_config(ctx: typer.Context) -> GlobalConfig:
    if ctx.obj and isinstance(ctx.obj.get("config"), GlobalConfig):
        return ctx.obj["config"]
    return load_global_config()


def _select_variation_index(*, count: int, no_interactive: bool) -> int:
    if count <= 1:
        return 0
    if no_interactive or not sys.stdin.isatty():
        console.print(
            "[yellow]Generated multiple variations in non-interactive mode; "
            "saving variation 1.[/]"
        )
        return 0

    choices = [str(index) for index in range(1, count + 1)]
    selected = Prompt.ask(
        "Select variation to save",
        choices=choices,
        default="1",
    )
    return int(selected) - 1


def _append_slide_to_project(
    prompt: str,
    local_path: Path | None,
    metadata: dict[str, object],
) -> tuple[Path | None, str | None]:
    if not PROJECT_STATE_FILE.exists():
        return local_path, None

    presentation = Presentation.from_project_state(load_project_state())
    slide_entry = presentation.add_slide(
        prompt=prompt,
        image_path=None,
        metadata=metadata,
    )
    renamed_path = _rename_slide_file(local_path, slide_entry.order, slide_entry.id)
    slide_entry.image_path = str(renamed_path) if renamed_path else None
    save_project_state(presentation.to_project_state())
    return renamed_path, slide_entry.id


def _resolve_cli_references(
    references: list[Path] | None,
    extra_args: list[str],
) -> list[Path]:
    resolved = list(references or [])
    for extra_arg in extra_args:
        if extra_arg.startswith("-"):
            raise ValueError(f"Unexpected option: {extra_arg}")
        path = Path(extra_arg).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"Reference image not found: {path}")
        resolved.append(path)
    return _unique_paths(resolved)


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    unique: list[Path] = []
    for path in paths:
        normalized = str(path.expanduser().resolve())
        if normalized in seen:
            continue
        seen.add(normalized)
        unique.append(Path(normalized))
    return unique


def _rename_slide_file(local_path: Path | None, order: int, slide_id: str) -> Path | None:
    if local_path is None or not local_path.exists():
        return local_path

    suffix = local_path.suffix
    target = local_path.with_name(f"{order}_{slide_id}{suffix}")
    if target == local_path:
        return local_path

    if target.exists():
        counter = 2
        while True:
            candidate = local_path.with_name(f"{order}_{slide_id}-{counter}{suffix}")
            if not candidate.exists():
                target = candidate
                break
            counter += 1

    local_path.rename(target)
    return target


