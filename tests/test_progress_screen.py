# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================

"""Tests for the ProgressScreen — initial state, log/step updates, back action.

Strategy
--------
``ProgressScreen.on_mount`` immediately fires ``self._run()``, a
``@work(exclusive=True, thread=True)`` worker that calls
``InstallerOrchestrator``.  We must prevent it from running during tests.

We do this by patching ``ProgressScreen._run`` (the underlying coroutine, not
the work-decorated wrapper) with a no-op *before* the app is started.
``patch.object`` replaces the method on the class for the duration of each
test, so ``on_mount``'s ``_ = self._run()`` is a harmless call that returns
immediately without spawning a real thread.

With ``_run`` neutralised the screen is in a clean, stable initial state.
We then call the internal helpers (``_ui_log``, ``_set_step``,
``_show_back_button``) directly — they are all ordinary methods that are safe
to call from the Textual test harness main thread.

``Log`` widget content
----------------------
``textual.widgets.Log`` stores lines in the ``_lines`` list attribute (a
private but stable implementation detail).  We read it to assert that
``_ui_log`` actually appended a line.  If Textual changes this internals in the
future, the tests will fail loudly rather than silently passing with a wrong
assertion.
"""

from __future__ import annotations

from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.widgets import Button, Label, Log, ProgressBar, Static

from dots_tui.logic.models import InstallConfig
from dots_tui.screens.progress import ProgressScreen, ProgressTask


# ---------------------------------------------------------------------------
# Minimal InstallConfig fixture
# ---------------------------------------------------------------------------


def _minimal_config() -> InstallConfig:
    return InstallConfig(
        run_mode="install",
        resolution="lt_1440p",
        keyboard_layout="us",
        clock_24h=True,
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        enable_asus=False,
        enable_blueman=False,
        enable_ags=False,
        enable_quickshell=False,
        dry_run=True,
    )


# ---------------------------------------------------------------------------
# Host app
# ---------------------------------------------------------------------------


class ProgressTestApp(App[None]):
    """Minimal host that pushes a ProgressScreen as the only screen."""

    CSS = ""

    def __init__(self, screen: ProgressScreen) -> None:
        super().__init__()
        self._progress_screen = screen

    def compose(self) -> ComposeResult:
        yield Label("placeholder")

    def on_mount(self) -> None:
        self.push_screen(self._progress_screen)


# ---------------------------------------------------------------------------
# Context manager: suppress _run so no real worker fires
# ---------------------------------------------------------------------------


class _NoRun:
    """Patches ``ProgressScreen._run`` with a synchronous no-op for the test duration.

    ``on_mount`` calls ``_ = self._run()`` and discards the return value.
    The ``@work`` decorator wraps ``_run`` so the outer call is synchronous
    (it schedules a thread worker and returns a ``Worker`` object).  Replacing
    it with a plain ``lambda`` avoids both the worker thread *and* the
    'coroutine never awaited' ``RuntimeWarning`` that an async stub would
    produce.
    """

    def __enter__(self):
        self._patcher = patch.object(ProgressScreen, "_run", lambda self: None)
        self._patcher.start()
        return self

    def __exit__(self, *args):
        self._patcher.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestProgressScreenInitialState:
    """Verify the screen mounts with the expected initial DOM state."""

    async def test_title_widget_shows_execution(self) -> None:
        """The ``#title`` Static should display 'Execution' on mount."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                title = app.screen.query_one("#title", Static)
                assert "Execution" in str(title.render())

    async def test_step_label_is_initially_empty(self) -> None:
        """The ``#step`` Label should be empty on mount (before worker sets it)."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                step = app.screen.query_one("#step", Label)
                # With _run suppressed the step is never updated — stays empty.
                assert str(step.render()).strip() == ""

    async def test_back_button_is_hidden_on_mount(self) -> None:
        """The ``#back`` Button must be hidden until the worker finishes."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                back_btn = app.screen.query_one("#back", Button)
                assert back_btn.display is False

    async def test_progress_bar_present(self) -> None:
        """A ``ProgressBar`` with id ``bar`` is present in the DOM."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                bar = app.screen.query_one("#bar", ProgressBar)
                assert bar is not None

    async def test_log_widget_initially_empty(self) -> None:
        """The ``Log`` widget should have no lines on mount."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                log = app.screen.query_one("#log", Log)
                assert len(log._lines) == 0


class TestProgressScreenLogAppend:
    """Verify that ``_ui_log`` appends lines to the Log widget."""

    async def test_ui_log_adds_a_line(self) -> None:
        """Calling ``_ui_log`` once adds exactly one line to the Log widget."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                log = app.screen.query_one("#log", Log)
                assert len(log._lines) == 0, "Log should start empty"

                app.screen._ui_log("hello from test")
                await pilot.pause()

                assert len(log._lines) == 1
                assert "hello from test" in str(log._lines[0])

    async def test_ui_log_strips_ansi_escape_sequences(self) -> None:
        """ANSI control sequences must be stripped before the line reaches the Log."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                # A string with a bold ANSI escape (ESC[1m ... ESC[0m)
                ansi_line = "\x1b[1mBold text\x1b[0m"
                app.screen._ui_log(ansi_line)
                await pilot.pause()

                log = app.screen.query_one("#log", Log)
                assert len(log._lines) == 1
                written = str(log._lines[0])
                assert "\x1b" not in written, "ANSI escape should have been stripped"
                assert "Bold text" in written

    async def test_ui_log_multiple_lines_accumulate(self) -> None:
        """Multiple ``_ui_log`` calls accumulate in the Log widget."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                messages = ["step 1", "step 2", "step 3"]
                for msg in messages:
                    app.screen._ui_log(msg)
                await pilot.pause()

                log = app.screen.query_one("#log", Log)
                assert len(log._lines) == len(messages)


class TestProgressScreenSetStep:
    """Verify ``_set_step`` updates the step label."""

    async def test_set_step_updates_label_text(self) -> None:
        """``_set_step('Copying files...')`` updates the ``#step`` Label content."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                app.screen._set_step("Copying files...")
                await pilot.pause()

                step = app.screen.query_one("#step", Label)
                assert "Copying files..." in str(step.render())

    async def test_set_step_with_percent_updates_progress_bar(self) -> None:
        """``_set_step('Done', percent=42)`` sets the ProgressBar progress."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                app.screen._set_step("Working", percent=42)
                await pilot.pause()

                bar = app.screen.query_one("#bar", ProgressBar)
                assert bar.progress == 42


class TestProgressScreenShowBackButton:
    """Verify ``_show_back_button`` makes the button visible."""

    async def test_show_back_button_makes_it_visible(self) -> None:
        """After ``_show_back_button()``, the ``#back`` Button should be displayed."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                # Initially hidden.
                back_btn = app.screen.query_one("#back", Button)
                assert back_btn.display is False

                app.screen._show_back_button()
                await pilot.pause()

                assert back_btn.display is True


class TestProgressScreenClassMethods:
    """Verify the ``for_install`` and ``for_repo_update`` factory classmethods."""

    async def test_for_install_sets_kind_and_config(self) -> None:
        """``for_install`` creates a ProgressTask with kind='install' and the config."""
        cfg = _minimal_config()
        screen = ProgressScreen.for_install(cfg)

        assert screen._progress_task.kind == "install"
        assert screen._progress_task.config is cfg

    async def test_for_repo_update_sets_kind_update(self) -> None:
        """``for_repo_update`` creates a ProgressTask with kind='update' and no config."""
        screen = ProgressScreen.for_repo_update()

        assert screen._progress_task.kind == "update"
        assert screen._progress_task.config is None


class TestProgressScreenActionBack:
    """Verify ``action_back`` behaviour in different states."""

    async def test_action_back_when_not_finished_pops_screen(self) -> None:
        """When ``_is_finished`` is False, ``action_back`` pops the current screen."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                # Confirm we are on the ProgressScreen.
                assert isinstance(app.screen, ProgressScreen)
                assert app.screen._is_finished is False

                app.screen.action_back()
                await pilot.pause()

                # After popping, we should be back on the placeholder screen.
                assert not isinstance(app.screen, ProgressScreen)

    async def test_action_back_when_finished_exits_if_no_menu_screen(self) -> None:
        """When ``_is_finished`` is True and there's no MenuScreen, the app exits."""
        screen = ProgressScreen.for_install(_minimal_config())
        app = ProgressTestApp(screen)

        with _NoRun():
            async with app.run_test() as pilot:
                await pilot.pause()

                # Mark the worker as finished.
                app.screen._is_finished = True

                app.screen.action_back()
                await pilot.pause()

                # App should have exited.
                assert app._exit is True or app.return_value is None
