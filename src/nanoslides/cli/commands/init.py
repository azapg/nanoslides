"""Implementation of the `nanoslides init` command."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import typer
from rich.console import Console

from nanoslides.core.config import GlobalConfig, load_global_config
from nanoslides.core.project import PROJECT_STATE_FILE, ProjectState, save_project_state

console = Console()


def init_command(
    ctx: typer.Context,
    name: str | None = typer.Argument(
        None,
        help="Optional project name/folder (creates ./<name>/slides.json when provided).",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        help="Overwrite an existing project state file.",
    ),
) -> None:
    """Initialize a new slides project in the current directory."""
    project_name = name or Path.cwd().name
    project_state_path = (Path(name) / PROJECT_STATE_FILE) if name else PROJECT_STATE_FILE

    if project_state_path.exists() and not force:
        console.print(
            f"[bold red]{project_state_path} already exists. Use --force to overwrite.[/]"
        )
        raise typer.Exit(code=1)

    config = _resolve_config(ctx)
    state = ProjectState(
        name=project_name,
        created_at=datetime.now(timezone.utc),
        engine=config.default_engine,
        slides=[],
    )
    save_project_state(state, project_state_path)

    console.print(
        f"[bold green]Initialized slides project '{project_name}' at "
        f"{project_state_path.resolve()}[/]"
    )


def _resolve_config(ctx: typer.Context) -> GlobalConfig:
    if ctx.obj and isinstance(ctx.obj.get("config"), GlobalConfig):
        return ctx.obj["config"]
    return load_global_config()

