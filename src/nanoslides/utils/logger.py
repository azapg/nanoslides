"""Centralized logging setup."""

from __future__ import annotations

import logging


def configure_logging(*, verbose: bool = False, json_output: bool = False) -> None:
    """Configure root logging for CLI commands."""
    level = logging.DEBUG if verbose else logging.INFO
    fmt = (
        '{"level":"%(levelname)s","message":"%(message)s"}'
        if json_output
        else "%(levelname)s: %(message)s"
    )
    logging.basicConfig(level=level, format=fmt, force=True)

