"""Shared helpers for provider error inspection."""

from __future__ import annotations

import re
from typing import Any

_STATUS_CODE_PATTERN = re.compile(r"\b(4\d{2}|5\d{2})\b")


def extract_status_code(exc: BaseException) -> int | None:
    """Best-effort extraction of HTTP-like status code from provider exceptions."""
    candidates: list[Any] = [
        getattr(exc, "status_code", None),
        getattr(exc, "code", None),
    ]
    response = getattr(exc, "response", None)
    if response is not None:
        candidates.append(getattr(response, "status_code", None))

    for candidate in candidates:
        if isinstance(candidate, int):
            return candidate
        if isinstance(candidate, str) and candidate.strip().isdigit():
            return int(candidate.strip())

    message = " ".join(
        str(value)
        for value in (
            getattr(exc, "status", ""),
            str(exc),
        )
        if value
    )
    for match in _STATUS_CODE_PATTERN.findall(message):
        value = int(match)
        if 400 <= value <= 599:
            return value
    return None


def is_service_unavailable_error(exc: BaseException) -> bool:
    """Return True when the exception represents a provider availability outage."""
    status_code = extract_status_code(exc)
    if status_code == 503:
        return True

    message = " ".join(
        part
        for part in (
            exc.__class__.__name__,
            str(getattr(exc, "status", "")),
            str(exc),
        )
        if part
    ).lower()
    return "service unavailable" in message or "temporarily unavailable" in message
