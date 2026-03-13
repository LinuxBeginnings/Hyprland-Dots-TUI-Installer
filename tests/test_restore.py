# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
"""Unit tests for logic/restore.py — previously-untested code paths.

Covers:
  - restore_user_scripts()
  - restore_hypr_files()
  - _compose_overlay_from_backup() (legacy path, version < 2.3.19)
  - _extract_exec_once()
  - _extract_rules()
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable

import pytest

from dots_tui.logic.restore import (
    _compose_overlay_from_backup,
    _extract_exec_once,
    _extract_rules,
    restore_hypr_files,
    restore_user_scripts,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _logs() -> tuple[list[str], Callable[[str], None]]:
    """Return a (log_list, log_fn) pair for capturing log output."""
    captured: list[str] = []
    return captured, captured.append


def _confirm_yes(_msg: str, _yes: str, _no: str, _default: bool) -> bool:
    return True


def _confirm_no(_msg: str, _yes: str, _no: str, _default: bool) -> bool:
    return False


# ---------------------------------------------------------------------------
# restore_user_scripts()
# ---------------------------------------------------------------------------


class TestRestoreUserScripts:
    """Tests for restore_user_scripts()."""

    def _make_dirs(self, tmp_path: Path) -> tuple[Path, Path]:
        """Return (backup_hypr_dir, hypr_dir) with UserScripts in backup."""
        backup = tmp_path / "backup_hypr"
        hypr = tmp_path / "hypr"
        (backup / "UserScripts").mkdir(parents=True)
        hypr.mkdir(parents=True)
        return backup, hypr

    def test_no_backup_dir_is_noop(self, tmp_path: Path) -> None:
        """If backup_hypr_dir/UserScripts does not exist, the function returns silently."""
        backup = tmp_path / "backup_hypr"  # does not contain UserScripts
        backup.mkdir()
        hypr = tmp_path / "hypr"
        hypr.mkdir()
        logs, log = _logs()

        restore_user_scripts(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=None,
            log=log,
        )

        assert logs == []

    def test_express_mode_skips_and_logs(self, tmp_path: Path) -> None:
        """Express mode should log a note and return without copying anything."""
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "UserScripts" / "RofiBeats.sh").write_text("#!/bin/bash\n")
        logs, log = _logs()

        restore_user_scripts(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=True,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        assert any("Express" in line for line in logs)
        assert not (hypr / "UserScripts" / "RofiBeats.sh").exists()

    def test_user_confirms_restores_script(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the user confirms, the script file is copied to UserScripts/."""
        monkeypatch.setattr("dots_tui.logic.path_safety.Path.home", lambda: tmp_path)
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "UserScripts" / "RofiBeats.sh").write_text("#!/bin/bash\necho hi\n")
        logs, log = _logs()

        restore_user_scripts(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        dst = hypr / "UserScripts" / "RofiBeats.sh"
        assert dst.exists()
        assert dst.read_text() == "#!/bin/bash\necho hi\n"
        assert any("[OK]" in line and "RofiBeats.sh" in line for line in logs)

    def test_user_declines_skips_script(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the user declines, the script is NOT copied."""
        monkeypatch.setattr("dots_tui.logic.path_safety.Path.home", lambda: tmp_path)
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "UserScripts" / "Weather.sh").write_text("#!/bin/bash\n")
        logs, log = _logs()

        restore_user_scripts(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_no,
            log=log,
        )

        assert not (hypr / "UserScripts" / "Weather.sh").exists()
        assert any("[NOTE]" in line and "Weather.sh" in line for line in logs)

    def test_missing_script_in_backup_is_silently_skipped(self, tmp_path: Path) -> None:
        """Scripts listed in the candidate list but absent from backup are ignored."""
        backup, hypr = self._make_dirs(tmp_path)
        # Only RofiBeats.sh is absent — no files at all in UserScripts.
        logs, log = _logs()

        restore_user_scripts(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        # No [OK] lines — nothing to restore, no crash.
        assert not any("[OK]" in line for line in logs)

    def test_no_prompt_handler_uses_default_no(self, tmp_path: Path) -> None:
        """Without a prompt handler, default is False (skip) for user scripts."""
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "UserScripts" / "RofiBeats.sh").write_text("x\n")
        logs, log = _logs()

        restore_user_scripts(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=None,
            log=log,
        )

        # Script should NOT be copied (default_yes=False for scripts).
        assert not (hypr / "UserScripts" / "RofiBeats.sh").exists()
        assert any("[WARN]" in line for line in logs)


# ---------------------------------------------------------------------------
# restore_hypr_files()
# ---------------------------------------------------------------------------


class TestRestoreHyprFiles:
    """Tests for restore_hypr_files() (hyprlock.conf / hypridle.conf)."""

    def _make_dirs(self, tmp_path: Path) -> tuple[Path, Path]:
        backup = tmp_path / "backup_hypr"
        hypr = tmp_path / "hypr"
        backup.mkdir(parents=True)
        hypr.mkdir(parents=True)
        return backup, hypr

    def test_express_mode_skips_and_logs(self, tmp_path: Path) -> None:
        """Express mode logs a note and does not copy any files."""
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "hyprlock.conf").write_text("# lock\n")
        logs, log = _logs()

        restore_hypr_files(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=True,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        assert any("Express" in line for line in logs)
        assert not (hypr / "hyprlock.conf").exists()

    def test_confirms_restores_hyprlock(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """User confirming restores hyprlock.conf."""
        monkeypatch.setattr("dots_tui.logic.path_safety.Path.home", lambda: tmp_path)
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "hyprlock.conf").write_text("# my lock config\n")
        logs, log = _logs()

        restore_hypr_files(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        assert (hypr / "hyprlock.conf").read_text() == "# my lock config\n"
        assert any("[OK]" in line and "hyprlock.conf" in line for line in logs)

    def test_confirms_restores_hypridle(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """User confirming restores hypridle.conf."""
        monkeypatch.setattr("dots_tui.logic.path_safety.Path.home", lambda: tmp_path)
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "hypridle.conf").write_text("# idle\n")
        logs, log = _logs()

        restore_hypr_files(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        assert (hypr / "hypridle.conf").read_text() == "# idle\n"
        assert any("[OK]" in line and "hypridle.conf" in line for line in logs)

    def test_declines_skips_files(self, tmp_path: Path) -> None:
        """User declining leaves files untouched."""
        backup, hypr = self._make_dirs(tmp_path)
        (backup / "hyprlock.conf").write_text("x\n")
        (backup / "hypridle.conf").write_text("y\n")
        logs, log = _logs()

        restore_hypr_files(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_no,
            log=log,
        )

        assert not (hypr / "hyprlock.conf").exists()
        assert not (hypr / "hypridle.conf").exists()
        assert any("[NOTE]" in line and "hyprlock.conf" in line for line in logs)
        assert any("[NOTE]" in line and "hypridle.conf" in line for line in logs)

    def test_missing_files_in_backup_silently_skipped(self, tmp_path: Path) -> None:
        """Files absent from backup are silently skipped without error."""
        backup, hypr = self._make_dirs(tmp_path)
        # No hyprlock.conf or hypridle.conf in backup
        logs, log = _logs()

        restore_hypr_files(
            backup_hypr_dir=backup,
            hypr_dir=hypr,
            express=False,
            prompt_confirm=_confirm_yes,
            log=log,
        )

        assert not any("[OK]" in line for line in logs)
        assert not any("[ERROR]" in line for line in logs)


# ---------------------------------------------------------------------------
# _extract_exec_once()
# ---------------------------------------------------------------------------


class TestExtractExecOnce:
    """Tests for the _extract_exec_once() parser."""

    SAMPLE = """\
exec-once = waybar
exec-once = dunst
# exec-once = disabled-app
exec-once = $scriptsDir/Start.sh
UNRELATED = value
"""

    def test_active_lines_only(self) -> None:
        result = _extract_exec_once(self.SAMPLE, commented=False)
        assert "exec-once = waybar" in result
        assert "exec-once = dunst" in result
        assert "exec-once = $scriptsDir/Start.sh" in result

    def test_no_commented_in_active_mode(self) -> None:
        result = _extract_exec_once(self.SAMPLE, commented=False)
        assert not any("disabled-app" in line for line in result)

    def test_commented_lines_mode(self) -> None:
        result = _extract_exec_once(self.SAMPLE, commented=True)
        # Should return the uncommented form of the commented exec-once
        assert any("disabled-app" in line for line in result)
        # Active lines must NOT appear
        assert not any("waybar" in line for line in result)

    def test_empty_text_returns_empty_list(self) -> None:
        assert _extract_exec_once("", commented=False) == []
        assert _extract_exec_once("", commented=True) == []

    def test_whitespace_only_lines_ignored(self) -> None:
        result = _extract_exec_once("   \n\t\n", commented=False)
        assert result == []

    def test_non_exec_once_active_lines_excluded(self) -> None:
        text = "bind = SUPER, Q, killactive\nexec-once = foo\n"
        result = _extract_exec_once(text, commented=False)
        assert result == ["exec-once = foo"]


# ---------------------------------------------------------------------------
# _extract_rules()
# ---------------------------------------------------------------------------


class TestExtractRules:
    """Tests for the _extract_rules() parser."""

    SAMPLE = """\
windowrule = float, class:pavucontrol
layerrule = blur, waybar
# windowrule = tile, class:kitty
# layerrule = noanim, rofi
exec-once = waybar
RANDOM = stuff
"""

    def test_active_windowrule_and_layerrule(self) -> None:
        result = _extract_rules(self.SAMPLE, commented=False)
        assert "windowrule = float, class:pavucontrol" in result
        assert "layerrule = blur, waybar" in result

    def test_active_excludes_commented(self) -> None:
        result = _extract_rules(self.SAMPLE, commented=False)
        assert not any("kitty" in line for line in result)
        assert not any("rofi" in line for line in result)

    def test_active_excludes_unrelated_lines(self) -> None:
        result = _extract_rules(self.SAMPLE, commented=False)
        assert not any("exec-once" in line for line in result)
        assert not any("RANDOM" in line for line in result)

    def test_commented_windowrule_and_layerrule(self) -> None:
        result = _extract_rules(self.SAMPLE, commented=True)
        assert any("kitty" in line for line in result)
        assert any("rofi" in line for line in result)

    def test_commented_excludes_active(self) -> None:
        result = _extract_rules(self.SAMPLE, commented=True)
        assert not any("pavucontrol" in line for line in result)
        assert not any("waybar" in line for line in result)

    def test_empty_text(self) -> None:
        assert _extract_rules("", commented=False) == []
        assert _extract_rules("", commented=True) == []


# ---------------------------------------------------------------------------
# _compose_overlay_from_backup() — legacy path (startup type)
# ---------------------------------------------------------------------------


class TestComposeOverlayStartup:
    """Tests for _compose_overlay_from_backup() with overlay_type='startup'."""

    def test_user_extras_written_to_overlay(self, tmp_path: Path) -> None:
        """Lines in old user file but not in base are written to new_user_file."""
        base = tmp_path / "Startup_Apps.conf"
        base.write_text("exec-once = waybar\nexec-once = dunst\n")

        old_user = tmp_path / "old_Startup_Apps.conf"
        old_user.write_text(
            "exec-once = waybar\nexec-once = dunst\nexec-once = my-custom-app\n"
        )

        new_user = tmp_path / "UserConfigs" / "Startup_Apps.conf"
        disable = tmp_path / "UserConfigs" / "Startup_Apps.disable"

        _compose_overlay_from_backup(
            overlay_type="startup",
            base_file=base,
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        overlay_txt = new_user.read_text()
        assert "exec-once = my-custom-app" in overlay_txt
        # Base lines must NOT be duplicated in the overlay
        assert overlay_txt.count("exec-once = waybar") == 0
        assert overlay_txt.count("exec-once = dunst") == 0

    def test_commented_lines_written_to_disable_file(self, tmp_path: Path) -> None:
        """Commented exec-once lines (disabled commands) go to the disable file."""
        base = tmp_path / "Startup_Apps.conf"
        base.write_text("")

        old_user = tmp_path / "old_Startup_Apps.conf"
        # A disabled command (commented exec-once)
        old_user.write_text("# exec-once = old-daemon\n")

        new_user = tmp_path / "UserConfigs" / "Startup_Apps.conf"
        disable = tmp_path / "UserConfigs" / "Startup_Apps.disable"

        _compose_overlay_from_backup(
            overlay_type="startup",
            base_file=base,
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        disable_txt = disable.read_text()
        assert "old-daemon" in disable_txt

    def test_keybinds_init_excluded_from_disable(self, tmp_path: Path) -> None:
        """KeybindsLayoutInit.sh is always stripped from the disable file."""
        base = tmp_path / "Startup_Apps.conf"
        base.write_text("")

        old_user = tmp_path / "old_Startup_Apps.conf"
        old_user.write_text("# exec-once = $scriptsDir/KeybindsLayoutInit.sh\n")

        new_user = tmp_path / "UserConfigs" / "Startup_Apps.conf"
        disable = tmp_path / "UserConfigs" / "Startup_Apps.disable"

        _compose_overlay_from_backup(
            overlay_type="startup",
            base_file=base,
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        assert "KeybindsLayoutInit.sh" not in disable.read_text()

    def test_missing_base_file_treated_as_empty(self, tmp_path: Path) -> None:
        """If the base file does not exist, all user extras become overlay lines."""
        old_user = tmp_path / "old_Startup_Apps.conf"
        old_user.write_text("exec-once = only-in-user\n")

        new_user = tmp_path / "UserConfigs" / "Startup_Apps.conf"
        disable = tmp_path / "UserConfigs" / "Startup_Apps.disable"

        _compose_overlay_from_backup(
            overlay_type="startup",
            base_file=tmp_path / "nonexistent.conf",  # does not exist
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        assert "exec-once = only-in-user" in new_user.read_text()


# ---------------------------------------------------------------------------
# _compose_overlay_from_backup() — legacy path (windowrules type)
# ---------------------------------------------------------------------------


class TestComposeOverlayWindowRules:
    """Tests for _compose_overlay_from_backup() with overlay_type='windowrules'."""

    def test_user_extras_written_to_overlay(self, tmp_path: Path) -> None:
        """Rules in old user file but not in base go to new_user_file."""
        base = tmp_path / "WindowRules.conf"
        base.write_text("windowrule = float, class:pavucontrol\n")

        old_user = tmp_path / "old_WindowRules.conf"
        old_user.write_text(
            "windowrule = float, class:pavucontrol\nwindowrule = tile, class:kitty\n"
        )

        new_user = tmp_path / "UserConfigs" / "WindowRules.conf"
        disable = tmp_path / "UserConfigs" / "WindowRules.disable"

        _compose_overlay_from_backup(
            overlay_type="windowrules",
            base_file=base,
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        overlay_txt = new_user.read_text()
        assert "windowrule = tile, class:kitty" in overlay_txt
        assert "windowrule = float, class:pavucontrol" not in overlay_txt

    def test_commented_rules_to_disable_file(self, tmp_path: Path) -> None:
        """Commented windowrule/layerrule lines go to the disable file."""
        base = tmp_path / "WindowRules.conf"
        base.write_text("")

        old_user = tmp_path / "old_WindowRules.conf"
        old_user.write_text("# windowrule = noanim, class:rofi\n")

        new_user = tmp_path / "UserConfigs" / "WindowRules.conf"
        disable = tmp_path / "UserConfigs" / "WindowRules.disable"

        _compose_overlay_from_backup(
            overlay_type="windowrules",
            base_file=base,
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        assert "rofi" in disable.read_text()

    def test_output_files_created_even_if_empty(self, tmp_path: Path) -> None:
        """Both output files are always created, even when there's nothing to write."""
        base = tmp_path / "WindowRules.conf"
        base.write_text("")
        old_user = tmp_path / "old_WindowRules.conf"
        old_user.write_text("")

        new_user = tmp_path / "UserConfigs" / "WindowRules.conf"
        disable = tmp_path / "UserConfigs" / "WindowRules.disable"

        _compose_overlay_from_backup(
            overlay_type="windowrules",
            base_file=base,
            old_user_file=old_user,
            new_user_file=new_user,
            disable_file=disable,
        )

        assert new_user.exists()
        assert disable.exists()
