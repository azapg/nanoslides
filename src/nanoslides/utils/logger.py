"""Centralized logging setup."""

from __future__ import annotations

import logging


def configure_logging(*, verbose: bool = False, json_output: bool = False) -> None:
    """Configure root logging for CLI commands."""
    level = logging.DEBUG if verbose else logging.WARNING
    fmt = (
        '{"level":"%(levelname)s","message":"%(message)s"}'
        if json_output
        else "%(levelname)s: %(message)s"
    )
    logging.basicConfig(level=level, format=fmt, force=True)
    library_level = logging.INFO if verbose else logging.WARNING
    for logger_name in ("httpx", "google", "google_genai", "urllib3", "absl"):
        logging.getLogger(logger_name).setLevel(library_level)

