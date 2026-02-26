# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
"""Tests for the ConfirmScreen modal — click paths, keyboard bindings, focus."""

from __future__ import annotations

import pytest
from textual.app import App, ComposeResult
from textual.widgets import Button, Label, Static

from dots_tui.screens.confirm import ConfirmScreen


class ConfirmTestApp(App[bool | None]):
    """Minimal host app that pushes a ConfirmScreen and records its result."""

    def __init__(self, screen: ConfirmScreen) -> None:
        super().__init__()
        self._confirm_screen = screen
        self.result: bool | None = None

    def compose(self) -> ComposeResult:
        yield Label("Background")

    def on_mount(self) -> None:
        def _callback(val: bool | None) -> None:
            self.result = val
            self.exit(val)

        self.push_screen(self._confirm_screen, callback=_callback)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_app(
    message: str = "Are you sure?",
    yes: str = "Yes",
    no: str = "No",
    default_yes: bool = True,
) -> ConfirmTestApp:
    screen = ConfirmScreen(message=message, yes=yes, no=no, default_yes=default_yes)
    return ConfirmTestApp(screen)


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
class TestConfirmScreen:
    """Full UI coverage for ConfirmScreen."""

    # ------------------------------------------------------------------
    # 1. Rendering
    # ------------------------------------------------------------------

    async def test_renders_message_and_buttons(self) -> None:
        """ConfirmScreen displays the message and both buttons."""
        app = _make_app(message="Delete everything?", yes="Yep", no="Nope")

        async with app.run_test() as pilot:
            await pilot.pause()

            msg = app.screen.query_one("#confirm-message", Static)
            assert "Delete everything?" in str(msg.render())

            yes_btn = app.screen.query_one("#yes", Button)
            no_btn = app.screen.query_one("#no", Button)
            assert str(yes_btn.label) == "Yep"
            assert str(no_btn.label) == "Nope"

    # ------------------------------------------------------------------
    # 2. Click paths
    # ------------------------------------------------------------------

    async def test_click_yes_returns_true(self) -> None:
        """Clicking the #yes button dismisses the screen with True."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.click("#yes")
            await pilot.pause()

        assert app.result is True

    async def test_click_no_returns_false(self) -> None:
        """Clicking the #no button dismisses the screen with False."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.click("#no")
            await pilot.pause()

        assert app.result is False

    # ------------------------------------------------------------------
    # 3. Default focus
    # ------------------------------------------------------------------

    async def test_default_yes_focuses_yes_button(self) -> None:
        """When default_yes=True the #yes button receives focus on mount."""
        app = _make_app(default_yes=True)

        async with app.run_test() as pilot:
            await pilot.pause()
            focused = app.screen.focused
            assert isinstance(focused, Button)
            assert focused.id == "yes"

    async def test_default_no_focuses_no_button(self) -> None:
        """When default_yes=False the #no button receives focus on mount."""
        app = _make_app(default_yes=False)

        async with app.run_test() as pilot:
            await pilot.pause()
            focused = app.screen.focused
            assert isinstance(focused, Button)
            assert focused.id == "no"

    # ------------------------------------------------------------------
    # 4. Keyboard shortcuts — dismiss-to-false
    # ------------------------------------------------------------------

    async def test_escape_returns_false(self) -> None:
        """Pressing Escape dismisses via action_no → False."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.press("escape")
            await pilot.pause()

        assert app.result is False

    async def test_q_key_returns_false(self) -> None:
        """Pressing 'q' dismisses via action_no → False."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.press("q")
            await pilot.pause()

        assert app.result is False

    # ------------------------------------------------------------------
    # 5. Keyboard shortcuts — navigate then accept
    # ------------------------------------------------------------------

    async def test_enter_accepts_focused_yes(self) -> None:
        """Enter confirms whichever button is focused — yes in this case."""
        app = _make_app(default_yes=True)  # #yes has focus

        async with app.run_test() as pilot:
            await pilot.pause()  # let on_mount run
            await pilot.press("enter")
            await pilot.pause()

        assert app.result is True

    async def test_space_accepts_focused_yes(self) -> None:
        """Space also triggers action_accept."""
        app = _make_app(default_yes=True)

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()

        assert app.result is True

    async def test_enter_accepts_focused_no(self) -> None:
        """Enter when #no is focused returns False."""
        app = _make_app(default_yes=False)  # #no has focus

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

        assert app.result is False

    # ------------------------------------------------------------------
    # 6. Navigation keys move focus between buttons
    # ------------------------------------------------------------------

    async def test_right_arrow_key_dismisses_yes(self) -> None:
        """'l' and right-arrow are bound to action_yes → dismiss True."""
        app = _make_app(default_yes=True)

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("l")
            await pilot.pause()

        assert app.result is True

    async def test_left_arrow_key_dismisses_no(self) -> None:
        """'h' and left-arrow are bound to action_no → dismiss False."""
        app = _make_app(default_yes=True)

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("h")
            await pilot.pause()

        assert app.result is False

    # ------------------------------------------------------------------
    # 7. action_yes / action_no keyboard bindings
    # ------------------------------------------------------------------

    async def test_l_key_action_resolves_yes(self) -> None:
        """The 'l' / right binding calls action_yes → True."""
        # Confirm by accepting after navigation: use a fresh app and press 'l'
        # which is bound to action_yes (dismiss True).
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("right")  # same binding as 'l'
            await pilot.pause()

        assert app.result is True

    async def test_h_key_action_resolves_no(self) -> None:
        """The 'h' / left binding calls action_no → False."""
        app = _make_app()

        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("left")  # same binding as 'h'
            await pilot.pause()

        assert app.result is False

    # ------------------------------------------------------------------
    # 8. Custom yes/no labels are displayed
    # ------------------------------------------------------------------

    async def test_custom_labels(self) -> None:
        """Custom yes/no strings appear on the buttons."""
        app = _make_app(yes="Confirm", no="Abort")

        async with app.run_test() as pilot:
            await pilot.pause()
            assert str(app.screen.query_one("#yes", Button).label) == "Confirm"
            assert str(app.screen.query_one("#no", Button).label) == "Abort"
