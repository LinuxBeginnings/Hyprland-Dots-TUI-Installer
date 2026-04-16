# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path

from dots_tui.logic.tweaks import (
    apply_hyprcursor_tweaks,
    apply_nixos_tweaks,
    apply_nvidia_tweaks,
    apply_vm_tweaks,
)


def _make_staging(tmp_path: Path) -> Path:
    """Create a minimal staging config tree."""
    staging = tmp_path / "config"
    hypr_configs = staging / "hypr" / "configs"
    hypr_configs.mkdir(parents=True)
    (staging / "hypr").mkdir(parents=True, exist_ok=True)
    return staging


def _env_vars_file(staging: Path) -> Path:
    return staging / "hypr" / "configs" / "ENVariables.conf"


def _sys_settings_file(staging: Path) -> Path:
    return staging / "hypr" / "configs" / "SystemSettings.conf"


def _monitors_file(staging: Path) -> Path:
    return staging / "hypr" / "monitors.conf"


# T1: apply_nvidia_tweaks uncomments Nvidia env vars and patches hardware cursors
class TestApplyNvidiaTweaks:
    def test_uncomments_nvidia_env_vars(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        env_file = _env_vars_file(staging)
        env_file.write_text(
            "#env = LIBVA_DRIVER_NAME,nvidia\n"
            "#env = __GLX_VENDOR_LIBRARY_NAME,nvidia\n"
            "#env = NVD_BACKEND,direct\n"
            "#env = GSK_RENDERER,ngl\n"
            "env = SOME_OTHER_VAR,value\n",
            encoding="utf-8",
        )
        apply_nvidia_tweaks(staging)
        result = env_file.read_text(encoding="utf-8")
        assert "env = LIBVA_DRIVER_NAME,nvidia" in result
        assert "env = __GLX_VENDOR_LIBRARY_NAME,nvidia" in result
        assert "env = NVD_BACKEND,direct" in result
        assert "env = GSK_RENDERER,ngl" in result
        # Non-nvidia line stays unchanged
        assert "env = SOME_OTHER_VAR,value" in result

    def test_patches_hardware_cursors_in_system_settings(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        sys_file = _sys_settings_file(staging)
        sys_file.write_text("no_hardware_cursors = 2\n", encoding="utf-8")
        apply_nvidia_tweaks(staging)
        result = sys_file.read_text(encoding="utf-8")
        assert "no_hardware_cursors = 1" in result
        assert "no_hardware_cursors = 2" not in result

    def test_missing_files_do_not_raise(self, tmp_path: Path) -> None:
        """T5: No-op when staging files are absent."""
        staging = _make_staging(tmp_path)
        # No files created — should not raise
        apply_nvidia_tweaks(staging)


# T2: apply_vm_tweaks enables software renderer, patches cursors, uncomments VM monitor
class TestApplyVmTweaks:
    def test_uncomments_wlr_renderer_allow_software(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        env_file = _env_vars_file(staging)
        env_file.write_text(
            "#env = WLR_RENDERER_ALLOW_SOFTWARE,1\n",
            encoding="utf-8",
        )
        apply_vm_tweaks(staging)
        result = env_file.read_text(encoding="utf-8")
        assert "env = WLR_RENDERER_ALLOW_SOFTWARE,1" in result
        assert "#env = WLR_RENDERER_ALLOW_SOFTWARE,1" not in result

    def test_patches_hardware_cursors_in_system_settings(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        sys_file = _sys_settings_file(staging)
        sys_file.write_text("no_hardware_cursors = 2\n", encoding="utf-8")
        apply_vm_tweaks(staging)
        result = sys_file.read_text(encoding="utf-8")
        assert "no_hardware_cursors = 1" in result

    def test_uncomments_vm_monitor_line(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        mon_file = _monitors_file(staging)
        mon_file.write_text(
            "#monitor = Virtual-1, 1920x1080@60,auto,1\n",
            encoding="utf-8",
        )
        apply_vm_tweaks(staging)
        result = mon_file.read_text(encoding="utf-8")
        assert "monitor = Virtual-1, 1920x1080@60,auto,1" in result
        assert "#monitor = Virtual-1" not in result

    def test_missing_files_do_not_raise(self, tmp_path: Path) -> None:
        """T5: No-op when staging files are absent."""
        staging = _make_staging(tmp_path)
        apply_vm_tweaks(staging)


# T3: apply_nixos_tweaks adds NixOS polkit exec-once line
class TestApplyNixosTweaks:
    def test_adds_nixos_polkit_exec_once(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        apply_nixos_tweaks(staging)
        overlay = staging / "hypr" / "configs" / "Startup_Apps.conf"
        assert overlay.is_file()
        content = overlay.read_text(encoding="utf-8")
        assert "exec-once = $scriptsDir/Polkit-NixOS.sh" in content

    def test_adds_polkit_to_disable_list(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        apply_nixos_tweaks(staging)
        disable = staging / "hypr" / "configs" / "Startup_Apps.disable"
        assert disable.is_file()
        content = disable.read_text(encoding="utf-8")
        assert "$scriptsDir/Polkit.sh" in content

    def test_idempotent(self, tmp_path: Path) -> None:
        """Calling twice should not duplicate lines."""
        staging = _make_staging(tmp_path)
        apply_nixos_tweaks(staging)
        apply_nixos_tweaks(staging)
        overlay = staging / "hypr" / "configs" / "Startup_Apps.conf"
        content = overlay.read_text(encoding="utf-8")
        assert content.count("exec-once = $scriptsDir/Polkit-NixOS.sh") == 1


# T4: apply_hyprcursor_tweaks uncomments HYPRCURSOR env vars
class TestApplyHyprcursorTweaks:
    def test_uncomments_hyprcursor_theme(self, tmp_path: Path) -> None:
        staging = _make_staging(tmp_path)
        env_file = _env_vars_file(staging)
        env_file.write_text(
            "#env = HYPRCURSOR_THEME,Bibata-Modern-Ice\n#env = HYPRCURSOR_SIZE,24\n",
            encoding="utf-8",
        )
        apply_hyprcursor_tweaks(staging)
        result = env_file.read_text(encoding="utf-8")
        assert "env = HYPRCURSOR_THEME,Bibata-Modern-Ice" in result
        assert "env = HYPRCURSOR_SIZE,24" in result
        assert "#env = HYPRCURSOR_THEME" not in result
        assert "#env = HYPRCURSOR_SIZE" not in result

    def test_missing_env_file_does_not_raise(self, tmp_path: Path) -> None:
        """T5: No-op when env file is absent."""
        staging = _make_staging(tmp_path)
        apply_hyprcursor_tweaks(staging)
