"""Remove command implementation."""

from __future__ import annotations

import typer
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from nanoslides.core.project import PROJECT_STATE_FILE, SlideEntry, load_project_state, save_project_state

console = Console()


def remove_command(
    slide_id: str = typer.Argument(..., help=f"Slide ID from {PROJECT_STATE_FILE} to remove."),
) -> None:
    """Remove a slide from the local project state."""
    try:
        project = load_project_state()
    except FileNotFoundError as exc:
        console.print(
            f"[bold red]{PROJECT_STATE_FILE} not found. Run `nanoslides init` first.[/]"
        )
        raise typer.Exit(code=1) from exc

    ordered_slides = sorted(project.slides, key=lambda slide: (slide.order, slide.id))
    target_slide = next((slide for slide in ordered_slides if slide.id == slide_id), None)
    if target_slide is None:
        console.print(f"[bold red]Slide '{slide_id}' was not found in {PROJECT_STATE_FILE}.[/]")
        raise typer.Exit(code=1)

    project.slides = [slide for slide in ordered_slides if slide.id != slide_id]
    _reindex_slide_orders(project.slides)
    save_project_state(project)

    console.print(
        Panel.fit(
            f"[bold green]Removed slide[/]\n"
            f"ID: [bold]{target_slide.id}[/]\n"
            f"Previous order: [bold]{target_slide.order}[/]",
            title="nanoslides",
            border_style="green",
        )
    )
    console.print(_slides_table(project.slides))


def _reindex_slide_orders(slides: list[SlideEntry]) -> None:
    for index, slide in enumerate(slides, start=1):
        slide.order = index


def _slides_table(slides: list[SlideEntry]) -> Table:
    table = Table(title="Updated slide order", box=box.ROUNDED, header_style="bold")
    table.add_column("Order", justify="right")
    table.add_column("ID")
    table.add_column("Path")
    if not slides:
        table.add_row("-", "[dim](no slides left)[/]", "-")
        return table
    for slide in slides:
        table.add_row(str(slide.order), slide.id, slide.image_path or "-")
    return table
