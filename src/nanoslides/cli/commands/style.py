"""Style command group."""

import sys
from pathlib import Path

import typer
from google.genai.errors import APIError
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from nanoslides.cli.errors import render_cli_error
from nanoslides.core.config import get_gemini_api_key, load_global_config
from nanoslides.core.style import (
    GLOBAL_STYLES_PATH,
    PROJECT_STYLE_PATH,
    ProjectStyleConfig,
    StyleDefinition,
    load_global_styles,
    load_project_style,
    save_global_styles,
    save_project_style,
)
from nanoslides.core.style_steal import (
    GeminiStyleStealAnalyzer,
    infer_project_style_from_instruction,
    infer_project_style_from_source,
    load_style_steal_source,
)

style_app = typer.Typer(
    help="Style management commands.",
    invoke_without_command=True,
)
console = Console()


@style_app.callback()
def style_callback(ctx: typer.Context) -> None:
    """List styles when no subcommand is provided."""
    if ctx.invoked_subcommand is not None:
        return
    _render_style_listing()


@style_app.command("create")
def style_create_command(
    style_id: str | None = typer.Argument(
        None,
        help="Style ID (required with --global, optional for project style).",
    ),
    base_prompt: str = typer.Option(
        "",
        "--base-prompt",
        help="Base prompt included in every generation/edit call.",
    ),
    negative_prompt: str = typer.Option(
        "",
        "--negative-prompt",
        help="Negative prompt included in every generation/edit call.",
    ),
    slides_base_reference: list[Path] | None = typer.Option(
        None,
        "--slides-base-reference",
        help=(
            "Image sent with every slide request for style consistency "
            "(repeat --slides-base-reference for multiple files)."
        ),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    reference_comment: list[str] | None = typer.Option(
        None,
        "--reference-comment",
        help="Reference comment (repeat --reference-comment for multiple entries).",
    ),
    global_scope: bool = typer.Option(
        False,
        "--global",
        help="Save style to ~/.nanoslides/styles.json instead of ./style.json.",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Disable guided prompts and use only provided arguments/options.",
    ),
) -> None:
    """Create/update a project style or a global style preset."""
    resolved_global_scope = global_scope
    resolved_style_id = style_id
    resolved_base_prompt = base_prompt.strip()
    resolved_negative_prompt = negative_prompt.strip()
    resolved_reference_images = [str(path) for path in (slides_base_reference or [])]
    resolved_reference_comments = [
        comment.strip() for comment in (reference_comment or []) if comment.strip()
    ]

    if not no_interactive and sys.stdin.isatty():
        (
            resolved_global_scope,
            resolved_style_id,
            resolved_base_prompt,
            resolved_negative_prompt,
            resolved_reference_images,
            resolved_reference_comments,
        ) = _collect_style_inputs(
            global_scope=resolved_global_scope,
            style_id=resolved_style_id,
            base_prompt=resolved_base_prompt,
            negative_prompt=resolved_negative_prompt,
            reference_images=resolved_reference_images,
            reference_comments=resolved_reference_comments,
        )

    if resolved_global_scope:
        resolved_reference_images = [
            str(Path(path).expanduser().resolve()) for path in resolved_reference_images
        ]

    style = StyleDefinition(
        base_prompt=resolved_base_prompt,
        negative_prompt=resolved_negative_prompt,
        reference_images=resolved_reference_images,
        reference_comments=resolved_reference_comments,
    )

    if resolved_global_scope:
        if not resolved_style_id:
            console.print("[bold red]A style_id is required when using --global.[/]")
            raise typer.Exit(code=1)
        styles = load_global_styles()
        styles.styles[resolved_style_id] = style
        save_global_styles(styles)
        console.print(
            f"[bold green]Saved global style '{resolved_style_id}' to {GLOBAL_STYLES_PATH}.[/]"
        )
        return

    project_style = ProjectStyleConfig(
        style_id=resolved_style_id,
        base_prompt=style.base_prompt,
        negative_prompt=style.negative_prompt,
        reference_images=style.reference_images,
        reference_comments=style.reference_comments,
    )
    save_project_style(project_style)
    console.print(f"[bold green]Saved project style to {PROJECT_STYLE_PATH}.[/]")


@style_app.command("edit")
def style_edit_command(
    style_id: str = typer.Argument(..., help="Global style ID to modify."),
    base_prompt: str | None = typer.Option(
        None,
        "--base-prompt",
        help="Updated base prompt included in every generation/edit call.",
    ),
    negative_prompt: str | None = typer.Option(
        None,
        "--negative-prompt",
        help="Updated negative prompt included in every generation/edit call.",
    ),
    slides_base_reference: list[Path] | None = typer.Option(
        None,
        "--slides-base-reference",
        help=(
            "Image sent with every slide request for style consistency "
            "(repeat --slides-base-reference for multiple files)."
        ),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    reference_comment: list[str] | None = typer.Option(
        None,
        "--reference-comment",
        help="Updated reference comments (repeat --reference-comment for multiple entries).",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Disable guided prompts and use only provided arguments/options.",
    ),
) -> None:
    """Edit an existing global style preset."""
    styles = load_global_styles()
    existing = styles.styles.get(style_id)
    if existing is None:
        console.print(f"[bold red]Global style '{style_id}' was not found.[/]")
        raise typer.Exit(code=1)

    use_guided_edit = (
        not no_interactive
        and sys.stdin.isatty()
        and base_prompt is None
        and negative_prompt is None
        and slides_base_reference is None
        and reference_comment is None
    )

    if use_guided_edit:
        (
            resolved_base_prompt,
            resolved_negative_prompt,
            resolved_reference_images,
            resolved_reference_comments,
        ) = _collect_style_edit_inputs(existing)
    else:
        resolved_base_prompt = (
            existing.base_prompt if base_prompt is None else base_prompt.strip()
        )
        resolved_negative_prompt = (
            existing.negative_prompt if negative_prompt is None else negative_prompt.strip()
        )
        resolved_reference_images = (
            existing.reference_images
            if slides_base_reference is None
            else [str(path.expanduser().resolve()) for path in slides_base_reference]
        )
        resolved_reference_comments = (
            existing.reference_comments
            if reference_comment is None
            else [comment.strip() for comment in reference_comment if comment.strip()]
        )

    styles.styles[style_id] = StyleDefinition(
        base_prompt=resolved_base_prompt,
        negative_prompt=resolved_negative_prompt,
        reference_images=resolved_reference_images,
        reference_comments=resolved_reference_comments,
    )
    save_global_styles(styles)
    console.print(f"[bold green]Updated global style '{style_id}'.[/]")


def _render_style_listing() -> None:
    project_style = load_project_style()
    global_styles = load_global_styles().styles

    table = Table(title="Available styles", show_header=True, header_style="bold")
    table.add_column("Style")
    table.add_column("Scope")
    table.add_column("Details")

    if project_style is not None:
        project_label = project_style.style_id or "project-default"
        table.add_row(
            project_label,
            "project",
            _style_summary(project_style),
        )

    for style_id in sorted(global_styles.keys()):
        table.add_row(style_id, "global", _style_summary(global_styles[style_id]))

    if table.row_count:
        console.print(table)
    else:
        console.print("[yellow]No styles found yet.[/]")
    console.print("[dim]Hint: run `nanoslides styles --help` for help.[/]")


def _style_summary(style: StyleDefinition) -> str:
    bits: list[str] = []
    if style.base_prompt:
        bits.append("base prompt")
    if style.negative_prompt:
        bits.append("negative prompt")
    if style.reference_images:
        bits.append(f"{len(style.reference_images)} slides base refs")
    if style.reference_comments:
        bits.append(f"{len(style.reference_comments)} comment refs")
    return ", ".join(bits) if bits else "empty"


def _collect_style_edit_inputs(
    existing: StyleDefinition,
) -> tuple[str, str, list[str], list[str]]:
    console.print(
        Panel.fit(
            "[bold cyan]Guided style edit[/]\nWe'll update this global style step by step.",
            title="nanoslides",
            border_style="cyan",
        )
    )

    resolved_base_prompt = Prompt.ask(
        "1) Base prompt (optional)",
        default=existing.base_prompt,
    ).strip()
    resolved_negative_prompt = Prompt.ask(
        "2) Negative prompt (optional)",
        default=existing.negative_prompt,
    ).strip()

    current_references = ", ".join(existing.reference_images)
    raw_references = Prompt.ask(
        "3) Slides base references (comma-separated paths, optional)",
        default=current_references,
    ).strip()
    if raw_references == current_references:
        resolved_reference_images = existing.reference_images
    else:
        resolved_reference_images = _parse_slides_base_reference_input(raw_references)

    current_comments = ", ".join(existing.reference_comments)
    raw_comments = Prompt.ask(
        "4) Reference comments (comma-separated, optional)",
        default=current_comments,
    ).strip()
    resolved_reference_comments = [
        comment.strip() for comment in raw_comments.split(",") if comment.strip()
    ]

    return (
        resolved_base_prompt,
        resolved_negative_prompt,
        resolved_reference_images,
        resolved_reference_comments,
    )


def _collect_style_inputs(
    *,
    global_scope: bool,
    style_id: str | None,
    base_prompt: str,
    negative_prompt: str,
    reference_images: list[str],
    reference_comments: list[str],
) -> tuple[bool, str | None, str, str, list[str], list[str]]:
    console.print(
        Panel.fit(
            "[bold cyan]Guided style setup[/]\nWe'll configure your style step by step.",
            title="nanoslides",
            border_style="cyan",
        )
    )

    resolved_global_scope = global_scope
    if not global_scope:
        resolved_global_scope = Confirm.ask(
            "1) Save as global reusable preset?", default=False
        )

    resolved_style_id = style_id
    if resolved_global_scope and not resolved_style_id:
        resolved_style_id = Prompt.ask("2) Style ID").strip()
    elif not resolved_global_scope and resolved_style_id is None:
        maybe_style_id = Prompt.ask(
            "2) Project default global style ID (optional)",
            default="",
        ).strip()
        resolved_style_id = maybe_style_id or None

    resolved_base_prompt = base_prompt or Prompt.ask("3) Base prompt (optional)", default="")
    resolved_negative_prompt = negative_prompt or Prompt.ask(
        "4) Negative prompt (optional)",
        default="",
    )

    resolved_reference_comments = reference_comments
    if not resolved_reference_comments:
        maybe_comment = Prompt.ask("5) Reference comment (optional)", default="").strip()
        if maybe_comment:
            resolved_reference_comments = [maybe_comment]

    resolved_reference_images = reference_images
    if not resolved_reference_images:
        maybe_image = Prompt.ask(
            "6) Slides base reference image path (optional)",
            default="",
        ).strip()
        if maybe_image:
            image_path = Path(maybe_image).expanduser()
            if not image_path.exists() or not image_path.is_file():
                raise ValueError(f"Reference image not found: {image_path}")
            resolved_reference_images = [str(image_path)]

    return (
        resolved_global_scope,
        resolved_style_id,
        resolved_base_prompt.strip(),
        resolved_negative_prompt.strip(),
        resolved_reference_images,
        resolved_reference_comments,
    )


def _parse_slides_base_reference_input(raw_value: str) -> list[str]:
    references: list[str] = []
    for token in raw_value.split(","):
        cleaned = token.strip()
        if not cleaned:
            continue
        path = Path(cleaned).expanduser()
        if not path.exists() or not path.is_file():
            raise ValueError(f"Reference image not found: {path}")
        references.append(str(path.resolve()))
    return references


@style_app.command("steal")
def style_steal_command(
    source: Path = typer.Argument(
        ...,
        help="Source asset path for style extraction (image for now).",
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    set_base_reference: bool = typer.Option(
        False,
        "--set-base-reference",
        help="Force using the source as slides base reference in output style.json.",
    ),
    output: Path = typer.Option(
        PROJECT_STYLE_PATH,
        "--output",
        help="Output style config path (defaults to ./style.json).",
    ),
    timeout_seconds: int = typer.Option(
        120,
        "--timeout-seconds",
        min=10,
        help="Gemini analysis timeout in seconds.",
    ),
) -> None:
    """Extract a reusable project style from a source asset."""
    config = load_global_config()
    api_key = get_gemini_api_key(config)
    if not api_key:
        console.print(
            "[bold red]Missing Gemini API key. Run `nanoslides setup` first.[/]"
        )
        raise typer.Exit(code=1)

    try:
        source_asset = load_style_steal_source(source)
        analyzer = GeminiStyleStealAnalyzer(
            api_key=api_key,
            timeout_seconds=float(timeout_seconds),
        )
        with console.status(
            f"[bold cyan]Analyzing style with Gemini 3 Pro (timeout: {timeout_seconds}s)...[/]"
        ):
            inferred_style = infer_project_style_from_source(
                analyzer=analyzer,
                source=source_asset,
                set_base_reference=set_base_reference,
            )
        used_model = getattr(analyzer, "last_model_used", "gemini-3-pro-preview")
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except APIError as exc:
        render_cli_error(exc, console=console, action="Style extraction failed.")
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        console.print(f"[bold red]Style extraction failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    output_path = output.expanduser().resolve()
    project_style = _project_style_for_output(inferred_style.project_style, output_path)
    save_project_style(project_style, path=output_path)

    recommendation = "yes" if inferred_style.suggestion.use_as_base_reference else "no"
    if set_base_reference:
        recommendation = f"{recommendation} (overridden to yes by --set-base-reference)"
    console.print(
        Panel.fit(
            f"[bold green]Style extracted[/]\n"
            f"Source: [bold]{source_asset.path}[/]\n"
            f"Model: [bold]{used_model}[/]\n"
            f"Recommended base reference: [bold]{recommendation}[/]\n"
            f"Reason: {inferred_style.suggestion.base_reference_reason}\n"
            f"Saved to [bold]{output_path}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


@style_app.command("generate")
def style_generate_command(
    instruction: str = typer.Argument(
        ...,
        help="Instruction describing the desired reusable visual style.",
    ),
    reference_image: list[Path] | None = typer.Option(
        None,
        "--reference-image",
        help=(
            "Optional style reference image path (repeat --reference-image for multiple files)."
        ),
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
    ),
    set_base_reference: bool = typer.Option(
        False,
        "--set-base-reference",
        help="Force using provided reference images as slides base references.",
    ),
    global_scope: bool = typer.Option(
        False,
        "--global",
        help="Save as a global reusable style preset.",
    ),
    style_id: str | None = typer.Option(
        None,
        "--style-id",
        help="Global style ID used with --global.",
    ),
    output: Path = typer.Option(
        PROJECT_STYLE_PATH,
        "--output",
        help="Output style config path (defaults to ./style.json).",
    ),
    timeout_seconds: int = typer.Option(
        120,
        "--timeout-seconds",
        min=10,
        help="Gemini analysis timeout in seconds.",
    ),
    no_interactive: bool = typer.Option(
        False,
        "--no-interactive",
        help="Skip review prompts and save directly using provided options.",
    ),
) -> None:
    """Generate a project style from an instruction and optional reference images."""
    config = load_global_config()
    api_key = get_gemini_api_key(config)
    if not api_key:
        console.print(
            "[bold red]Missing Gemini API key. Run `nanoslides setup` first.[/]"
        )
        raise typer.Exit(code=1)

    try:
        reference_sources = [
            load_style_steal_source(path) for path in (reference_image or [])
        ]
        analyzer = GeminiStyleStealAnalyzer(
            api_key=api_key,
            timeout_seconds=float(timeout_seconds),
        )
        with console.status(
            f"[bold cyan]Generating style with Gemini 3 Pro (timeout: {timeout_seconds}s)...[/]"
        ):
            inferred_style = infer_project_style_from_instruction(
                analyzer=analyzer,
                instruction=instruction,
                reference_sources=reference_sources,
                set_base_reference=set_base_reference,
            )
        used_model = getattr(analyzer, "last_model_used", "gemini-3-pro-preview")
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc
    except APIError as exc:
        render_cli_error(exc, console=console, action="Style generation failed.")
        raise typer.Exit(code=1)
    except RuntimeError as exc:
        console.print(f"[bold red]Style generation failed: {exc}[/]")
        raise typer.Exit(code=1) from exc

    _render_generated_style_preview(
        inferred_style.project_style,
        recommendation=inferred_style.suggestion.base_reference_reason,
        recommendation_uses_reference=inferred_style.suggestion.use_as_base_reference,
        reference_count=len(reference_sources),
    )

    should_save = True
    resolved_global_scope = global_scope
    resolved_style_id = style_id.strip() if style_id else None
    if not no_interactive and sys.stdin.isatty():
        should_save = Confirm.ask("Save this generated style?", default=True)
        if should_save and not resolved_global_scope:
            resolved_global_scope = Confirm.ask(
                "Save as global reusable preset?",
                default=False,
            )
        if should_save and resolved_global_scope and not resolved_style_id:
            resolved_style_id = Prompt.ask("Global style ID").strip()

    if not should_save:
        console.print("[yellow]Generated style was not saved.[/]")
        return

    if resolved_global_scope:
        if not resolved_style_id:
            console.print("[bold red]A style ID is required when using --global.[/]")
            raise typer.Exit(code=1)
        style_definition = _style_definition_for_global(inferred_style.project_style)
        styles = load_global_styles()
        styles.styles[resolved_style_id] = style_definition
        save_global_styles(styles)
        console.print(
            Panel.fit(
                f"[bold green]Style generated[/]\n"
                f"Model: [bold]{used_model}[/]\n"
                f"Saved global style [bold]{resolved_style_id}[/] to [bold]{GLOBAL_STYLES_PATH}[/]",
                title="nanoslides",
                border_style="green",
            )
        )
        return

    output_path = output.expanduser().resolve()
    project_style = _project_style_for_output(inferred_style.project_style, output_path)
    save_project_style(project_style, path=output_path)

    recommendation = "yes" if inferred_style.suggestion.use_as_base_reference else "no"
    if not reference_sources:
        recommendation = "n/a (no reference images provided)"
    elif set_base_reference:
        recommendation = f"{recommendation} (overridden to yes by --set-base-reference)"
    console.print(
        Panel.fit(
            f"[bold green]Style generated[/]\n"
            f"Model: [bold]{used_model}[/]\n"
            f"Reference images analyzed: [bold]{len(reference_sources)}[/]\n"
            f"Recommended base reference: [bold]{recommendation}[/]\n"
            f"Reason: {inferred_style.suggestion.base_reference_reason}\n"
            f"Saved to [bold]{output_path}[/]",
            title="nanoslides",
            border_style="green",
        )
    )


def _render_generated_style_preview(
    project_style: ProjectStyleConfig,
    *,
    recommendation: str,
    recommendation_uses_reference: bool,
    reference_count: int,
) -> None:
    table = Table(title="Generated style preview", show_header=False, box=None)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("Base prompt", project_style.base_prompt or "[dim](empty)[/]")
    table.add_row("Negative prompt", project_style.negative_prompt or "[dim](empty)[/]")
    table.add_row(
        "Reference images",
        str(len(project_style.reference_images)) + f" kept from {reference_count} analyzed",
    )
    comments = (
        "\n".join(f"- {comment}" for comment in project_style.reference_comments)
        if project_style.reference_comments
        else "[dim](none)[/]"
    )
    table.add_row("Reference comments", comments)
    table.add_row(
        "Base reference recommendation",
        "yes" if recommendation_uses_reference else "no",
    )
    table.add_row("Recommendation reason", recommendation)
    console.print(table)


def _style_definition_for_global(project_style: ProjectStyleConfig) -> StyleDefinition:
    return StyleDefinition(
        base_prompt=project_style.base_prompt,
        negative_prompt=project_style.negative_prompt,
        reference_images=[
            str(Path(path).expanduser().resolve()) for path in project_style.reference_images
        ],
        reference_comments=project_style.reference_comments,
    )


def _project_style_for_output(
    project_style: ProjectStyleConfig,
    output_path: Path,
) -> ProjectStyleConfig:
    if not project_style.reference_images:
        return project_style
    return project_style.model_copy(
        update={
            "reference_images": [
                _style_reference_path_for_output(Path(path), output_path)
                for path in project_style.reference_images
            ]
        }
    )


def _style_reference_path_for_output(source_path: Path, output_path: Path) -> str:
    base_dir = output_path.parent.resolve()
    resolved_source = source_path.resolve()
    try:
        return str(resolved_source.relative_to(base_dir))
    except ValueError:
        return str(resolved_source)

