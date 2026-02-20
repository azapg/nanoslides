from __future__ import annotations

from datetime import datetime, timezone

import pytest

from nanoslides.cli.commands import clearall as clearall_commands
from nanoslides.core.presentation import Presentation


def _seed_presentation() -> Presentation:
    presentation = Presentation(
        name="Roadmap Deck",
        created_at=datetime.now(timezone.utc),
        engine="nanobanana",
    )
    first = presentation.add_slide(
        prompt="Company vision overview",
        image_path="slides/1.png",
        metadata={},
    )
    presentation.add_slide(
        prompt="Market opportunity",
        image_path="slides/2.png",
        metadata={},
    )
    presentation.create_draft(
        source_slide_id=first.id,
        prompt="Updated draft vision slide",
        image_path="slides/1-draft.png",
        metadata={},
    )
    return presentation


def test_clearall_command_removes_all_slides_when_confirmed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    presentation = _seed_presentation()
    saved_states: list[object] = []
    monkeypatch.setattr(
        clearall_commands,
        "load_project_state",
        presentation.to_project_state,
    )
    monkeypatch.setattr(clearall_commands.Confirm, "ask", lambda *args, **kwargs: True)
    monkeypatch.setattr(clearall_commands, "save_project_state", saved_states.append)

    clearall_commands.clearall_command()

    assert len(saved_states) == 1
    saved_state = saved_states[0]
    assert getattr(saved_state, "slides") == []


def test_clearall_command_does_not_delete_when_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    presentation = _seed_presentation()
    saved_states: list[object] = []
    monkeypatch.setattr(
        clearall_commands,
        "load_project_state",
        presentation.to_project_state,
    )
    monkeypatch.setattr(clearall_commands.Confirm, "ask", lambda *args, **kwargs: False)
    monkeypatch.setattr(clearall_commands, "save_project_state", saved_states.append)

    clearall_commands.clearall_command()

    assert saved_states == []
