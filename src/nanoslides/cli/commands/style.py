"""Style command group."""

import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from nanoslides.core.style import (
    GLOBAL_STYLES_PATH,
    PROJECT_STYLE_PATH,
    ProjectStyleConfig,
    StyleDefinition,
    load_global_styles,
    save_global_styles,
    save_project_style,
)

style_app = typer.Typer(help="Style management commands.")
console = Console()


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
    reference_image: list[Path] | None = typer.Option(
        None,
        "--reference-image",
        help="Reference image path (repeat --reference-image for multiple files).",
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
    resolved_reference_images = [str(path) for path in (reference_image or [])]
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
        maybe_image = Prompt.ask("6) Reference image path (optional)", default="").strip()
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


@style_app.command("steal")
def style_steal_command() -> None:
    """Placeholder command."""
    console.print("[yellow]Coming Soon: style steal command.[/]")

