# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from dots_tui.logic.models import InstallConfig
from dots_tui.logic.user_config import apply_user_choices


def _base_config(**kwargs: Any) -> InstallConfig:  # type: ignore[no-untyped-def]
    defaults = dict(
        run_mode="install",
        resolution="gte_1440p",
        keyboard_layout="us",
        clock_24h=True,
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        dry_run=False,
        enable_asus=False,
        enable_blueman=False,
        enable_ags=False,
        enable_quickshell=False,
    )
    defaults.update(kwargs)
    return InstallConfig(**defaults)  # type: ignore[arg-type]


def _make_staging(tmp_path: Path) -> Path:
    """Create a minimal staging config tree with commonly needed files."""
    staging = tmp_path / "config"
    hypr_configs = staging / "hypr" / "configs"
    hypr_configs.mkdir(parents=True)
    hypr_userconfigs = staging / "hypr" / "UserConfigs"
    hypr_userconfigs.mkdir(parents=True, exist_ok=True)
    return staging


def _sys_settings(staging: Path) -> Path:
    return staging / "hypr" / "configs" / "SystemSettings.conf"


def _user_defaults(staging: Path) -> Path:
    return staging / "hypr" / "UserConfigs" / "01-UserDefaults.conf"


def _startup_apps(staging: Path) -> Path:
    return staging / "hypr" / "configs" / "Startup_Apps.conf"


def _waybar_modules(staging: Path) -> Path:
    return staging / "waybar" / "Modules"


def _noop_log(msg: str) -> None:
    pass


# UC1: keyboard layout patching
class TestKeyboardLayout:
    def test_patches_kb_layout_when_non_us(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = _make_staging(tmp_path)
        sys_file = _sys_settings(staging)
        sys_file.write_text(
            "kb_layout = us\nkb_variant =\n",
            encoding="utf-8",
        )
        calls: list[tuple[Path, str]] = []
        monkeypatch.setattr(
            "dots_tui.logic.user_config.replace_kb_layout",
            lambda path, layout: calls.append((path, layout)),
        )
        cfg = _base_config(keyboard_layout="de")
        apply_user_choices(cfg, staging, _noop_log)
        assert len(calls) == 1
        assert calls[0] == (sys_file, "de")

    def test_calls_replace_kb_layout_even_for_us(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = _make_staging(tmp_path)
        sys_file = _sys_settings(staging)
        sys_file.write_text("kb_layout = us\n", encoding="utf-8")
        calls: list[tuple[Path, str]] = []
        monkeypatch.setattr(
            "dots_tui.logic.user_config.replace_kb_layout",
            lambda path, layout: calls.append((path, layout)),
        )
        cfg = _base_config(keyboard_layout="us")
        apply_user_choices(cfg, staging, _noop_log)
        assert len(calls) == 1

    def test_missing_sys_settings_does_not_call_replace(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """UC8: Graceful no-op when staging file is absent."""
        staging = _make_staging(tmp_path)
        calls: list[tuple[Path, str]] = []
        monkeypatch.setattr(
            "dots_tui.logic.user_config.replace_kb_layout",
            lambda path, layout: calls.append((path, layout)),
        )
        cfg = _base_config(keyboard_layout="de")
        apply_user_choices(cfg, staging, _noop_log)
        assert len(calls) == 0


# UC4: default editor
class TestDefaultEditor:
    def test_patches_editor_env_var(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        defaults_file = _user_defaults(staging)
        defaults_file.write_text(
            "env = EDITOR,nano #default editor\n",
            encoding="utf-8",
        )
        cfg = _base_config(default_editor="vim")
        apply_user_choices(cfg, staging, _noop_log)
        result = defaults_file.read_text(encoding="utf-8")
        assert "env = EDITOR,vim #default editor" in result
        assert "nano" not in result

    def test_prepends_editor_when_not_found(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        defaults_file = _user_defaults(staging)
        defaults_file.write_text("env = SOME_OTHER_VAR,value\n", encoding="utf-8")
        cfg = _base_config(default_editor="vim")
        apply_user_choices(cfg, staging, _noop_log)
        result = defaults_file.read_text(encoding="utf-8")
        assert "env = EDITOR,vim" in result

    def test_no_editor_set_does_not_modify_defaults(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        defaults_file = _user_defaults(staging)
        defaults_file.write_text(
            "env = EDITOR,nano #default editor\n", encoding="utf-8"
        )
        cfg = _base_config(default_editor=None)
        apply_user_choices(cfg, staging, _noop_log)
        result = defaults_file.read_text(encoding="utf-8")
        assert "nano" in result

    def test_missing_defaults_file_does_not_raise(self, tmp_path: Path) -> None:
        """UC8: Graceful no-op when staging file is absent."""
        staging = _make_staging(tmp_path)
        cfg = _base_config(default_editor="vim")
        apply_user_choices(cfg, staging, _noop_log)  # Should not raise


# UC3: resolution patching
class TestResolutionPatch:
    def test_lt_1440p_patches_kitty_font_size(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        kitty_dir = staging / "kitty"
        kitty_dir.mkdir(parents=True)
        kitty_conf = kitty_dir / "kitty.conf"
        kitty_conf.write_text("font_size 16.0\n", encoding="utf-8")
        cfg = _base_config(resolution="lt_1440p")
        apply_user_choices(cfg, staging, _noop_log)
        result = kitty_conf.read_text(encoding="utf-8")
        assert "font_size 14.0" in result
        assert "font_size 16.0" not in result

    def test_lt_1440p_patches_rofi_fonts(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        rofi_dir = staging / "rofi"
        rofi_dir.mkdir(parents=True)
        rofi_fonts = rofi_dir / "0-shared-fonts.rasi"
        rofi_fonts.write_text(
            'font: "JetBrainsMono Nerd Font SemiBold 13";\n'
            'font: "JetBrainsMono Nerd Font SemiBold 15";\n',
            encoding="utf-8",
        )
        cfg = _base_config(resolution="lt_1440p")
        apply_user_choices(cfg, staging, _noop_log)
        result = rofi_fonts.read_text(encoding="utf-8")
        assert 'SemiBold 11";' in result
        assert 'SemiBold 13";' in result
        assert 'SemiBold 15";' not in result

    def test_gte_1440p_does_not_patch_kitty(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        kitty_dir = staging / "kitty"
        kitty_dir.mkdir(parents=True)
        kitty_conf = kitty_dir / "kitty.conf"
        kitty_conf.write_text("font_size 16.0\n", encoding="utf-8")
        cfg = _base_config(resolution="gte_1440p")
        apply_user_choices(cfg, staging, _noop_log)
        result = kitty_conf.read_text(encoding="utf-8")
        assert "font_size 16.0" in result


# UC2: clock format
class TestClockFormat:
    def test_12h_mode_uncomments_12h_lines_in_waybar_modules(
        self, tmp_path: Path
    ) -> None:
        staging = _make_staging(tmp_path)
        waybar_dir = staging / "waybar"
        waybar_dir.mkdir(parents=True)
        modules = waybar_dir / "Modules"
        modules.write_text(
            '// "{:%I:%M %p}",\n"{:%H:%M}",\n',
            encoding="utf-8",
        )
        cfg = _base_config(clock_24h=False)
        apply_user_choices(cfg, staging, _noop_log)
        result = modules.read_text(encoding="utf-8")
        # 12h line should be uncommented
        assert '"{:%I:%M %p}",' in result
        # 24h line should be commented
        assert "//" in result

    def test_24h_mode_does_not_modify_modules(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        waybar_dir = staging / "waybar"
        waybar_dir.mkdir(parents=True)
        modules = waybar_dir / "Modules"
        original = '"{:%H:%M}",\n// "{:%I:%M %p}",\n'
        modules.write_text(original, encoding="utf-8")
        cfg = _base_config(clock_24h=True)
        apply_user_choices(cfg, staging, _noop_log)
        result = modules.read_text(encoding="utf-8")
        assert result == original

    def test_missing_modules_file_does_not_raise(self, tmp_path: Path) -> None:
        """UC8: Graceful no-op when Modules file is absent."""
        staging = _make_staging(tmp_path)
        cfg = _base_config(clock_24h=False)
        apply_user_choices(cfg, staging, _noop_log)  # Should not raise


# UC5-UC7: startup app entries
class TestStartupApps:
    def test_enable_ags_adds_exec_once_when_binary_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = _make_staging(tmp_path)
        monkeypatch.setattr("dots_tui.utils.which", lambda cmd: f"/usr/bin/{cmd}")
        cfg = _base_config(enable_ags=True)
        apply_user_choices(cfg, staging, _noop_log)
        startup = _startup_apps(staging)
        content = startup.read_text(encoding="utf-8")
        assert "exec-once = ags\n" in content

    def test_enable_ags_skipped_when_binary_absent(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = _make_staging(tmp_path)
        monkeypatch.setattr("dots_tui.utils.which", lambda cmd: None)
        cfg = _base_config(enable_ags=True)
        apply_user_choices(cfg, staging, _noop_log)
        startup = _startup_apps(staging)
        content = startup.read_text(encoding="utf-8")
        assert "exec-once = ags\n" not in content

    def test_enable_quickshell_adds_exec_once_when_binary_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = _make_staging(tmp_path)
        monkeypatch.setattr("dots_tui.utils.which", lambda cmd: f"/usr/bin/{cmd}")
        cfg = _base_config(enable_quickshell=True)
        apply_user_choices(cfg, staging, _noop_log)
        startup = _startup_apps(staging)
        content = startup.read_text(encoding="utf-8")
        assert "exec-once = qs\n" in content

    def test_enable_asus_adds_rog_control_center_when_binary_present(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        staging = _make_staging(tmp_path)
        monkeypatch.setattr("dots_tui.utils.which", lambda cmd: f"/usr/bin/{cmd}")
        cfg = _base_config(enable_asus=True)
        apply_user_choices(cfg, staging, _noop_log)
        startup = _startup_apps(staging)
        content = startup.read_text(encoding="utf-8")
        assert "exec-once = rog-control-center\n" in content

    def test_keybinds_layout_init_always_added(self, tmp_path: Path) -> None:
        """KeybindsLayoutInit.sh is always appended regardless of optional apps."""
        staging = _make_staging(tmp_path)
        cfg = _base_config()
        apply_user_choices(cfg, staging, _noop_log)
        startup = _startup_apps(staging)
        content = startup.read_text(encoding="utf-8")
        assert "exec-once = $scriptsDir/KeybindsLayoutInit.sh\n" in content

    def test_keybinds_layout_init_not_duplicated(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        cfg = _base_config()
        apply_user_choices(cfg, staging, _noop_log)
        apply_user_choices(cfg, staging, _noop_log)
        startup = _startup_apps(staging)
        content = startup.read_text(encoding="utf-8")
        assert content.count("exec-once = $scriptsDir/KeybindsLayoutInit.sh\n") == 1
