# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
"""Tests for the ConfigScreen — form submission, validation, and config capture.

Strategy
--------
``ConfigScreen`` is a regular ``Screen``, so we host it inside a thin ``App``
subclass.

Two async side-effects happen in ``ConfigScreen.on_mount``:

1. ``self.run_worker(apply_probe)`` — calls ``self.app.get_probe()`` to probe
   the real system.  We override ``get_probe`` on the host app to return a
   hand-crafted ``ProbeResult`` so the worker finishes instantly and
   deterministically.

2. After the user clicks "Next", a ``ConfirmScreen`` is pushed to confirm the
   keyboard layout.  After the user confirms ("Yes"), ``ConfigScreen`` pushes
   ``ProgressScreen.for_install(cfg)``.

   We intercept this second push by patching ``ProgressScreen.for_install``
   with a spy that records the ``InstallConfig`` it receives, and returning a
   ``MagicMock`` screen so Textual never actually mounts the real
   ``ProgressScreen`` (which would start the installer).  We also patch
   ``App.push_screen`` at the point where ProgressScreen would be mounted to
   simply exit the app.

Scrollable widgets
------------------
Many interactive widgets (Blueman, AGS, Quickshell…) live inside a
``VerticalScroll`` and may be below the visible viewport.  ``pilot.click()``
requires widgets to be within the visible screen region and will raise
``OutOfBounds`` for off-screen widgets.  We therefore toggle checkboxes by
directly setting ``widget.value`` and calling ``post_message`` to propagate
the change event instead of using click.
"""

from __future__ import annotations

from unittest.mock import patch

from textual.app import App, ComposeResult
from textual.widgets import Checkbox, Input, Label, RadioButton, RadioSet, Static

from dots_tui.logic.env_probe import ProbeResult
from dots_tui.logic.models import InstallConfig
from dots_tui.screens.config import ConfigScreen
from dots_tui.screens.progress import ProgressScreen


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_probe(
    *,
    keyboard_layout: str | None = "us",
    has_nvim: bool = False,
    has_vim: bool = False,
    distro_id: str | None = "arch",
    distro_like: tuple[str, ...] = (),
    express_supported: bool = False,
) -> ProbeResult:
    """Build a deterministic ``ProbeResult`` for testing."""
    return ProbeResult(
        distro_id=distro_id,
        distro_like=distro_like,
        keyboard_layout=keyboard_layout,
        express_supported=express_supported,
        has_nvim=has_nvim,
        has_vim=has_vim,
    )


class ConfigTestApp(App[None]):
    """Minimal host app that mounts ``ConfigScreen`` as the first screen.

    Overrides ``get_probe()`` to return a fake result so the probe worker
    never touches the real system.

    Attributes
    ----------
    captured_config:
        Set by the ``ProgressScreen.for_install`` patch whenever the full
        submission flow completes.  ``None`` until then.
    """

    CSS = ""

    def __init__(
        self, run_mode: str = "install", probe: ProbeResult | None = None
    ) -> None:
        super().__init__()
        self.probe_result: ProbeResult = probe or _make_probe()
        self.captured_config: InstallConfig | None = None
        self._run_mode = run_mode

    def compose(self) -> ComposeResult:
        yield Label("placeholder")

    def on_mount(self) -> None:
        self.push_screen(ConfigScreen(run_mode=self._run_mode, dry_run=True))  # type: ignore[arg-type]

    async def get_probe(self) -> ProbeResult:
        """Return the fake probe instead of probing the real system."""
        return self.probe_result


# ---------------------------------------------------------------------------
# Helpers: dismiss the keyboard-confirm ConfirmScreen
# ---------------------------------------------------------------------------


async def _dismiss_confirm(pilot, answer: bool) -> None:
    """Click Yes or No on the ConfirmScreen pushed after Next is clicked."""
    await pilot.pause()  # wait for ConfirmScreen to mount
    btn_id = "yes" if answer else "no"
    await pilot.click(f"#{btn_id}")
    await pilot.pause()


def _toggle_checkbox(screen, widget_id: str) -> None:
    """Toggle a Checkbox by setting its value directly (avoids OutOfBounds)."""
    cb: Checkbox = screen.query_one(f"#{widget_id}", Checkbox)
    cb.value = not cb.value


# ---------------------------------------------------------------------------
# Context manager: patch ProgressScreen.for_install and intercept the push
# ---------------------------------------------------------------------------


class _CaptureProgress:
    """Patches ``ProgressScreen.for_install`` to spy on the config it receives.

    Usage::

        app = ConfigTestApp(probe=probe)
        with _CaptureProgress(app) as cap:
            async with app.run_test() as pilot:
                ...
        assert cap.config is not None
    """

    def __init__(self, app: ConfigTestApp) -> None:
        self._app = app
        self.config: InstallConfig | None = None
        self._patcher = None

    def __enter__(self):
        # We need to capture the config that is passed to ProgressScreen.for_install.
        # We do this by replacing for_install with a function that saves the arg
        # and returns a stub screen that immediately exits when pushed.
        captured = self  # closure

        def _fake_for_install(cfg: InstallConfig) -> _ExitScreen:
            captured.config = cfg
            # Also store on the app for easy retrieval in tests.
            captured._app.captured_config = cfg
            # Return a stub that Textual will try to push.  We hook the app exit
            # via a side-channel: call app.exit() from a real Screen.
            stub = _ExitScreen()
            return stub

        self._patcher = patch.object(
            ProgressScreen, "for_install", staticmethod(_fake_for_install)
        )
        self._patcher.start()
        return self

    def __exit__(self, *args):
        if self._patcher:
            self._patcher.stop()


class _ExitScreen(ConfigScreen):
    """Stub screen pushed instead of ProgressScreen.  Exits the app immediately."""

    def __init__(self) -> None:  # type: ignore[override]
        # Use minimal args — we only need this to exist for long enough to trigger exit.
        super().__init__(run_mode="install", dry_run=True)

    async def on_mount(self, event) -> None:  # type: ignore[override]
        self.app.exit()


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


class TestConfigScreenFormSubmission:
    """End-to-end tests for ConfigScreen form submission and validation."""

    # ------------------------------------------------------------------
    # 1. Happy path — default US keyboard layout
    # ------------------------------------------------------------------

    async def test_submit_default_us_layout_produces_correct_config(self) -> None:
        """Clicking Next (default state) then confirming yields a valid InstallConfig.

        Default state:
        - Resolution: < 1440p (radio index 0)
        - Keyboard: us (with US detected)
        - Extra wallpapers: unchecked
        - SDDM wallpaper: checked
        - Blueman: checked
        - Quickshell: checked
        - AGS: unchecked
        - AsusCtl: unchecked
        - no nvim / vim
        """
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()  # let worker+probe settle

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None, "InstallConfig was never captured — Next flow broken"

        assert cfg.run_mode == "install"
        assert cfg.keyboard_layout == "us"
        assert cfg.resolution == "lt_1440p"
        assert cfg.dry_run is True
        assert cfg.default_editor is None  # no nvim/vim in probe
        assert cfg.download_wallpapers is False
        assert cfg.apply_sddm_wallpaper is True
        assert cfg.enable_blueman is True
        assert cfg.enable_quickshell is True
        assert cfg.enable_ags is False
        assert cfg.enable_asus is False

    # ------------------------------------------------------------------
    # 2. Resolution — select >= 1440p
    # ------------------------------------------------------------------

    async def test_submit_high_resolution_option(self) -> None:
        """Selecting '>= 1440p' radio produces resolution='gte_1440p' in config."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                # Select the second RadioButton in #resolution (">= 1440p").
                rs = app.screen.query_one("#resolution", RadioSet)
                buttons = list(rs.query(RadioButton))
                assert len(buttons) >= 2, "Expected at least 2 resolution options"
                buttons[1].value = True
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None
        assert cfg.resolution == "gte_1440p"

    # ------------------------------------------------------------------
    # 3. Keyboard layout cancelled → stays on config screen
    # ------------------------------------------------------------------

    async def test_cancel_confirm_returns_to_config_and_shows_validation(self) -> None:
        """When user clicks No on the keyboard confirm, a validation message appears."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=False)

                # App should still be on ConfigScreen — no config captured.
                assert app.captured_config is None, (
                    "InstallConfig should not be captured when user cancels"
                )

                # Validation message must appear.
                validation = app.screen.query_one("#validation", Static)
                content = str(validation.render())
                assert "Keyboard layout not confirmed" in content

    # ------------------------------------------------------------------
    # 4. Validation — empty keyboard layout blocks submit
    # ------------------------------------------------------------------

    async def test_empty_custom_keyboard_layout_shows_validation(self) -> None:
        """Selecting 'Other' with an empty layout field blocks submission."""
        # Probe returns None so the UI starts with 'Other' pre-selected and warns.
        probe = _make_probe(keyboard_layout=None)
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                # Force the custom input to be empty.
                inp = app.screen.query_one("#kb_layout_custom", Input)
                inp.value = ""

                # Try to click Next — should be blocked.
                await pilot.click("#next")
                await pilot.pause()

                # Config must NOT have been captured.
                assert app.captured_config is None

                # A helpful validation message should appear.
                validation = app.screen.query_one("#validation", Static)
                content = str(validation.render())
                assert "keyboard layout" in content.lower()

    # ------------------------------------------------------------------
    # 5. Extras checkboxes — disable blueman and quickshell
    # ------------------------------------------------------------------

    async def test_unchecking_blueman_and_quickshell_reflected_in_config(self) -> None:
        """Unchecking Blueman and Quickshell before Next produces False in config."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                # Blueman and Quickshell default to True — set to False directly.
                app.screen.query_one("#enable_blueman", Checkbox).value = False
                app.screen.query_one("#enable_quickshell", Checkbox).value = False
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None
        assert cfg.enable_blueman is False
        assert cfg.enable_quickshell is False

    # ------------------------------------------------------------------
    # 6. Enable AGS (off by default)
    # ------------------------------------------------------------------

    async def test_enabling_ags_reflected_in_config(self) -> None:
        """Enabling AGS before Next sets enable_ags=True in the config."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                app.screen.query_one("#enable_ags", Checkbox).value = True
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None
        assert cfg.enable_ags is True

    # ------------------------------------------------------------------
    # 7. Upgrade run_mode is preserved in config
    # ------------------------------------------------------------------

    async def test_upgrade_mode_preserved_in_config(self) -> None:
        """run_mode='upgrade' passed to ConfigScreen is forwarded to InstallConfig."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="upgrade", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None
        assert cfg.run_mode == "upgrade"

    # ------------------------------------------------------------------
    # 8. Debian/Ubuntu distro warning — must check box before proceeding
    # ------------------------------------------------------------------

    async def test_debian_distro_blocks_next_without_confirm_checkbox(self) -> None:
        """On Debian/Ubuntu, clicking Next without the distro checkbox blocks submit."""
        probe = _make_probe(
            keyboard_layout="us",
            distro_id="ubuntu",
            distro_like=("debian",),
        )
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                # Two pauses: one for on_mount, one for the run_worker to finish.
                await pilot.pause()
                await pilot.pause()

                # The distro-confirm checkbox is now visible.
                # Do NOT check it — click Next immediately.
                await pilot.click("#next")
                await pilot.pause()

                # Config should NOT have been captured.
                assert app.captured_config is None

                # Validation message must mention the UBD/Debian requirement.
                validation = app.screen.query_one("#validation", Static)
                content = str(validation.render())
                assert any(
                    kw in content for kw in ("Ubuntu", "Debian", "confirm", "continue")
                ), f"Expected Debian/Ubuntu validation message, got: {content!r}"

    # ------------------------------------------------------------------
    # 9. Weather Units — Celsius (default)
    # ------------------------------------------------------------------

    async def test_weather_units_default_celsius(self) -> None:
        """By default, weather_units is set to 'C' (Celsius)."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None
        assert cfg.weather_units == "C"

    # ------------------------------------------------------------------
    # 10. Weather Units — Fahrenheit selection
    # ------------------------------------------------------------------

    async def test_weather_units_fahrenheit_selection(self) -> None:
        """Selecting Fahrenheit (F) radio button sets weather_units='F'."""
        probe = _make_probe(keyboard_layout="us")
        app = ConfigTestApp(run_mode="install", probe=probe)

        with _CaptureProgress(app):
            async with app.run_test() as pilot:
                await pilot.pause()

                # Select the Fahrenheit (F) radio button.
                rs = app.screen.query_one("#weather_units", RadioSet)
                buttons = list(rs.query(RadioButton))
                assert len(buttons) >= 2, "Expected Celsius and Fahrenheit options"
                buttons[1].value = True  # Fahrenheit is second option
                await pilot.pause()

                await pilot.click("#next")
                await _dismiss_confirm(pilot, answer=True)

        cfg = app.captured_config
        assert cfg is not None
        assert cfg.weather_units == "F"
