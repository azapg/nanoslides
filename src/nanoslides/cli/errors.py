"""Shared CLI error rendering helpers."""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from rich.console import Console
from rich.panel import Panel


@dataclass(frozen=True)
class ErrorInfo:
    code: int | None
    status: str
    message: str


def render_cli_error(
    exc: BaseException,
    *,
    console: Console,
    action: str | None = None,
) -> None:
    """Render a friendly TUI panel for a command failure."""
    info = _extract_error_info(exc)
    title, summary, hint = _classify_error(exc, info)

    lines: list[str] = []
    if action:
        lines.append(f"[bold]{action}[/]")
        lines.append("")
    lines.append(f"[bold red]{title}[/]")
    lines.append(summary)

    status_bits: list[str] = []
    if info.code is not None:
        status_bits.append(str(info.code))
    if info.status:
        status_bits.append(info.status)
    if status_bits:
        lines.append(f"[dim]Provider status: {' '.join(status_bits)}[/]")
    if hint:
        lines.append(f"[dim]{hint}[/]")
    if info.message and info.message.lower() not in summary.lower():
        lines.append(f"[dim]Details: {info.message}[/]")

    console.print(
        Panel.fit(
            "\n".join(lines),
            title="nanoslides",
            border_style="red",
        )
    )


def _classify_error(exc: BaseException, info: ErrorInfo) -> tuple[str, str, str]:
    if isinstance(exc, KeyboardInterrupt):
        return (
            "Command cancelled",
            "The command was cancelled before it finished.",
            "",
        )

    haystack = " ".join(
        bit
        for bit in (
            exc.__class__.__name__,
            info.status,
            info.message,
        )
        if bit
    ).lower()

    if info.code == 503 or "unavailable" in haystack or "high demand" in haystack:
        return (
            "Model temporarily unavailable",
            "The model provider is currently experiencing high demand.",
            "Spikes are usually temporary. Please try the command again shortly.",
        )
    if (
        info.code == 429
        or "rate limit" in haystack
        or "resource_exhausted" in haystack
        or "quota" in haystack
    ):
        return (
            "Rate limit reached",
            "The provider rejected this request because usage limits were hit.",
            "Wait a moment, then retry. If this keeps happening, check your API quota.",
        )
    if info.code in {401, 403} or "api key" in haystack or "permission" in haystack:
        return (
            "Authentication problem",
            "The provider rejected authentication for this request.",
            "Verify your Gemini key with `nanoslides setup` and retry.",
        )
    if isinstance(exc, TimeoutError) or "timed out" in haystack or "timeout" in haystack:
        return (
            "Request timed out",
            "The provider took too long to respond.",
            "Retry now, or increase timeout options when available.",
        )
    if "connection" in haystack and (
        "refused" in haystack or "reset" in haystack or "dns" in haystack
    ):
        return (
            "Network connection issue",
            "A network problem interrupted communication with the provider.",
            "Check your connection and retry.",
        )
    return (
        "Command failed",
        "An unexpected error occurred while running this command.",
        "Try again. If the issue persists, rerun with --verbose for more context.",
    )


def _extract_error_info(exc: BaseException) -> ErrorInfo:
    raw_message = str(exc)
    normalized_message = _normalize_text(raw_message)
    code = _coerce_int(getattr(exc, "status_code", None))
    status = _normalize_text(str(getattr(exc, "status", "")))
    message = normalized_message

    payload = _extract_payload_from_text(raw_message) or _extract_payload_from_response(exc)
    if isinstance(payload, dict):
        error_payload = payload.get("error", payload)
        if isinstance(error_payload, dict):
            payload_code = _coerce_int(error_payload.get("code"))
            if payload_code is not None:
                code = payload_code
            payload_status = _normalize_text(str(error_payload.get("status", "")))
            if payload_status:
                status = payload_status
            payload_message = _normalize_text(str(error_payload.get("message", "")))
            if payload_message:
                message = payload_message

    return ErrorInfo(code=code, status=status, message=message)


def _extract_payload_from_text(raw_message: str) -> dict[str, Any] | None:
    payload_start = raw_message.find("{")
    if payload_start < 0:
        return None
    payload_text = raw_message[payload_start:]
    try:
        payload = ast.literal_eval(payload_text)
    except (SyntaxError, ValueError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _extract_payload_from_response(exc: BaseException) -> dict[str, Any] | None:
    response = getattr(exc, "response", None)
    if response is None:
        return None
    response_json = getattr(response, "json", None)
    if not callable(response_json):
        return None
    try:
        payload = response_json()
    except (TypeError, ValueError):
        return None
    if isinstance(payload, dict):
        return payload
    return None


def _coerce_int(value: Any) -> int | None:
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _normalize_text(text: str) -> str:
    collapsed = " ".join(text.split())
    if len(collapsed) <= 240:
        return collapsed
    return f"{collapsed[:237]}..."
