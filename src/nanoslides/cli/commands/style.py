"""Stub style command group."""

import typer
from rich.console import Console

style_app = typer.Typer(help="Style management commands.")
console = Console()


@style_app.command("create")
def style_create_command() -> None:
    """Placeholder command."""
    console.print("[yellow]Coming Soon: style create command.[/]")


@style_app.command("steal")
def style_steal_command() -> None:
    """Placeholder command."""
    console.print("[yellow]Coming Soon: style steal command.[/]")

