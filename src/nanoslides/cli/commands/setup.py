"""Setup command for configuring API keys."""

from __future__ import annotations

from pathlib import Path

import click
import typer
from click import Choice
from rich.console import Console

from nanoslides.core.config import (
    GEMINI_API_KEY_NAME,
    GLOBAL_CONFIG_PATH,
    OPENAI_API_KEY_NAME,
    apply_provider_api_key,
    load_global_config,
    save_global_config,
)

console = Console()
_PROVIDER_OPTIONS = [
    ("openai", OPENAI_API_KEY_NAME),
    ("gemini", GEMINI_API_KEY_NAME),
]
_PROVIDER_KEYS = [provider_key for _, provider_key in _PROVIDER_OPTIONS]
_PROVIDER_ALIASES = {
    **{label: provider_key for label, provider_key in _PROVIDER_OPTIONS},
    **{provider_key.lower(): provider_key for provider_key in _PROVIDER_KEYS},
}


def _normalize_provider(provider: str) -> str | None:
    return _PROVIDER_ALIASES.get(provider.strip().lower())


def _provider_label(provider_key: str) -> str:
    for label, candidate_key in _PROVIDER_OPTIONS:
        if candidate_key == provider_key:
            return label
    return provider_key.lower()


def _select_provider_key() -> str:
    selected_index = 0
    while True:
        click.clear()
        console.print("[bold]Select your provider[/] (↑/↓ then Enter)")
        for index, (label, _) in enumerate(_PROVIDER_OPTIONS):
            marker = "❯" if index == selected_index else " "
            console.print(f"{marker} {label}")

        key = click.getchar()
        if key in ("\r", "\n"):
            return _PROVIDER_OPTIONS[selected_index][1]
        if key in ("\x1b[A", "\xe0H", "\x00H"):
            selected_index = (selected_index - 1) % len(_PROVIDER_OPTIONS)
            continue
        if key in ("\x1b[B", "\xe0P", "\x00P"):
            selected_index = (selected_index + 1) % len(_PROVIDER_OPTIONS)
            continue
        if key in ("\x03", "\x04"):
            raise typer.Abort()


def setup_command(
    provider: str | None = typer.Option(
        None,
        "--provider",
        click_type=Choice(list(_PROVIDER_ALIASES), case_sensitive=False),
        show_choices=True,
        help="Provider to configure (openai or gemini).",
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="Provider API key value (prompted if omitted).",
        hide_input=True,
    ),
    config_path: Path = typer.Option(
        GLOBAL_CONFIG_PATH,
        "--config-path",
        hidden=True,
    ),
) -> None:
    """Configure provider API keys and default engine."""
    provider_key = _select_provider_key() if provider is None else _normalize_provider(provider)
    if provider_key not in _PROVIDER_KEYS:
        console.print(f"[bold red]Unsupported provider key: {provider}[/]")
        raise typer.Exit(code=1)

    key_value = api_key or typer.prompt(
        f"Enter API key for {_provider_label(provider_key)}",
        hide_input=True,
        confirmation_prompt=True,
    )
    config = load_global_config(path=config_path)
    try:
        apply_provider_api_key(
            config,
            provider_key=provider_key,
            api_key=key_value,
        )
    except ValueError as exc:
        console.print(f"[bold red]{exc}[/]")
        raise typer.Exit(code=1) from exc

    save_global_config(config, path=config_path)
    console.print(
        f"[bold green]Saved {provider_key} to {config_path}.[/]\n"
        f"Default engine: [bold]{config.default_engine}[/]"
    )

