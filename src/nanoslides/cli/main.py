"""Main Typer application definition."""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nanoslides.cli.commands.edit import edit_command
from nanoslides.cli.commands.export import export_command
from nanoslides.cli.commands.generate import generate_command
from nanoslides.cli.commands.init import init_command
from nanoslides.cli.commands.move import move_command
from nanoslides.cli.commands.presentation import presentation_command
from nanoslides.cli.commands.remove import remove_command
from nanoslides.cli.commands.setup import setup_command
from nanoslides.cli.commands.style import style_app
from nanoslides.cli.errors import render_cli_error
from nanoslides.core.config import load_global_config
from nanoslides.core.presentation import Presentation
from nanoslides.core.project import (
    LEGACY_PROJECT_STATE_FILE,
    PROJECT_STATE_FILE,
    load_project_state,
)
from nanoslides.core.style import resolve_style_context
from nanoslides.utils.logger import configure_logging

console = Console()
app = typer.Typer(
    help="Generate and manage AI-powered presentation slides.",
    invoke_without_command=True,
)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(
        False, "--verbose", "-v", help="Enable verbose logging."
    ),
    json_output: bool = typer.Option(
        False, "--json", help="Emit logs in a JSON-friendly format."
    ),
) -> None:
    """Configure the runtime environment for all commands."""
    load_dotenv()
    configure_logging(verbose=verbose, json_output=json_output)
    ctx.obj = ctx.obj or {}
    ctx.obj["config"] = load_global_config()
    if ctx.resilient_parsing or ctx.invoked_subcommand is not None:
        return
    if not _has_local_project():
        console.print(ctx.get_help())
        raise typer.Exit()

    presentation = Presentation.from_project_state(load_project_state())
    _render_project_summary(presentation)
    console.print("[dim]Use [bold]nanoslides --help[/] for help.[/]")
    raise typer.Exit()


app.command("init")(init_command)
app.command("setup")(setup_command)
app.command("generate", context_settings={"allow_extra_args": True})(generate_command)
app.command("edit")(edit_command)
app.command("remove")(remove_command)
app.command("move")(move_command)
app.command("presentation")(presentation_command)
app.command("export")(export_command)
app.add_typer(style_app, name="styles")


def _has_local_project() -> bool:
    return PROJECT_STATE_FILE.exists() or LEGACY_PROJECT_STATE_FILE.exists()


def _render_project_summary(presentation: Presentation) -> None:
    project_path = (
        PROJECT_STATE_FILE.resolve()
        if PROJECT_STATE_FILE.exists()
        else LEGACY_PROJECT_STATE_FILE.resolve()
    )
    details = Table.grid(padding=(0, 1))
    details.add_column(style="bold cyan")
    details.add_column()
    details.add_row("Name", presentation.name)
    details.add_row("Engine", presentation.engine)
    details.add_row("Path", str(project_path))
    console.print(Panel(details, title="Current project", border_style="cyan", box=box.ROUNDED))

    slides_table = Table(title="Slides", box=box.ROUNDED, header_style="bold")
    slides_table.add_column("Order", justify="right")
    slides_table.add_column("ID")
    slides_table.add_column("Path")
    for slide in presentation.ordered_main_slides:
        slides_table.add_row(str(slide.order), slide.id, slide.image_path or "-")
    if not presentation.ordered_main_slides:
        slides_table.add_row("-", "[dim](no slides yet)[/]", "-")
    console.print(slides_table)

    style_base_prompt = resolve_style_context().base_prompt.strip() or "[dim](not set)[/]"
    console.print(
        Panel(style_base_prompt, title="Style base prompt", border_style="magenta", box=box.ROUNDED)
    )


def run() -> None:
    """CLI entrypoint used by console scripts."""
    try:
        app()
    except typer.Exit as exc:
        raise SystemExit(exc.exit_code) from None
    except KeyboardInterrupt as exc:
        render_cli_error(exc, console=console)
        raise SystemExit(130) from None
    except Exception as exc:
        render_cli_error(exc, console=console)
        raise SystemExit(1) from None

