# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
"""Test that ghostty config directory is backed up before copying."""

from __future__ import annotations

import asyncio
import pytest

from dots_tui.logic.models import InstallConfig
from dots_tui.logic.orchestrator import InstallerOrchestrator

from tests.helpers import CmdRecorder, read_text, write_text


def test_ghostty_backup_before_install(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """Verify ~/.config/ghostty is backed up before copying ghostty config."""

    # Seed fake repo with ghostty config
    repo_root = fake_home.home / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)

    # Ghostty source config (named ghostty.config in repo, installed as config)
    write_text(
        repo_root / "config" / "ghostty" / "ghostty.config",
        "font-size = 14\ntheme = dark\n",
    )

    # Required hypr config to avoid errors
    write_text(repo_root / "config" / "hypr" / "v2.3.19", "")
    write_text(
        repo_root / "config" / "hypr" / "configs" / "SystemSettings.conf",
        "  kb_layout = us\n",
    )
    write_text(
        repo_root / "config" / "hypr" / "UserConfigs" / "01-UserDefaults.conf",
        "#env = EDITOR,nvim\n",
    )

    # Seed existing ghostty config that should be backed up
    existing_ghostty = fake_home.config / "ghostty"
    write_text(existing_ghostty / "config", "font-size = 12\ntheme = light\n")
    write_text(existing_ghostty / "themes" / "custom.conf", "custom theme\n")

    # Stub system/commands
    recorder = CmdRecorder()
    monkeypatch.setattr("dots_tui.utils.run_cmd", recorder.run)
    monkeypatch.setattr("dots_tui.utils.is_root", lambda: False)
    monkeypatch.setattr("dots_tui.utils.which", lambda _cmd: None)

    monkeypatch.setattr("dots_tui.logic.system.detect_distro", lambda: ("arch", []))
    monkeypatch.setattr("dots_tui.logic.system.detect_chassis", lambda: "desktop")
    monkeypatch.setattr("dots_tui.logic.system.detect_nvidia", lambda: False)
    monkeypatch.setattr("dots_tui.logic.system.detect_vm", lambda: False)
    monkeypatch.setattr("dots_tui.logic.system.detect_nixos", lambda: False)
    monkeypatch.setattr(
        "dots_tui.logic.system.get_installed_dotfiles_version",
        lambda _root: None,
    )

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []

    def log(line: str) -> None:
        logs.append(line)

    cfg = InstallConfig(
        run_mode="install",
        resolution="gte_1440p",
        keyboard_layout="us",
        clock_24h=True,
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        dry_run=False,
        enable_asus=False,
        enable_blueman=True,
        enable_ags=False,
        enable_quickshell=False,
    )

    asyncio.run(
        orch.run_install(
            cfg,
            log=log,
            log_file=fake_home.copy_logs / "ghostty-test.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
        )
    )

    # Verify: Backup was created
    assert any("Backed up ghostty" in line for line in logs), (
        "Expected ghostty backup log message"
    )

    # Verify: Backup directory exists with pattern ghostty-backup-*
    backups = list(fake_home.config.glob("ghostty-backup-*"))
    assert len(backups) == 1, f"Expected 1 ghostty backup, found {len(backups)}"

    backup_dir = backups[0]
    assert backup_dir.is_dir()

    # Verify: Original files are in backup
    assert (backup_dir / "config").is_file()
    assert "font-size = 12" in read_text(backup_dir / "config")
    assert (backup_dir / "themes" / "custom.conf").is_file()
    assert "custom theme" in read_text(backup_dir / "themes" / "custom.conf")

    # Verify: New config was installed
    assert (fake_home.config / "ghostty" / "config").is_file()
    assert "font-size = 14" in read_text(fake_home.config / "ghostty" / "config")

    # Verify: Install log message
    assert any("Installed ghostty config" in line for line in logs)


def test_ghostty_no_backup_when_no_existing_config(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """Verify no backup attempt when ghostty config doesn't exist."""

    # Seed fake repo with ghostty config
    repo_root = fake_home.home / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)

    write_text(
        repo_root / "config" / "ghostty" / "ghostty.config",
        "font-size = 14\n",
    )

    # Required hypr config
    write_text(repo_root / "config" / "hypr" / "v2.3.19", "")
    write_text(
        repo_root / "config" / "hypr" / "configs" / "SystemSettings.conf",
        "  kb_layout = us\n",
    )
    write_text(
        repo_root / "config" / "hypr" / "UserConfigs" / "01-UserDefaults.conf",
        "#env = EDITOR,nvim\n",
    )

    # NO existing ghostty config

    # Stub system/commands
    recorder = CmdRecorder()
    monkeypatch.setattr("dots_tui.utils.run_cmd", recorder.run)
    monkeypatch.setattr("dots_tui.utils.is_root", lambda: False)
    monkeypatch.setattr("dots_tui.utils.which", lambda _cmd: None)

    monkeypatch.setattr("dots_tui.logic.system.detect_distro", lambda: ("arch", []))
    monkeypatch.setattr("dots_tui.logic.system.detect_chassis", lambda: "desktop")
    monkeypatch.setattr("dots_tui.logic.system.detect_nvidia", lambda: False)
    monkeypatch.setattr("dots_tui.logic.system.detect_vm", lambda: False)
    monkeypatch.setattr("dots_tui.logic.system.detect_nixos", lambda: False)
    monkeypatch.setattr(
        "dots_tui.logic.system.get_installed_dotfiles_version",
        lambda _root: None,
    )

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []

    def log(line: str) -> None:
        logs.append(line)

    cfg = InstallConfig(
        run_mode="install",
        resolution="gte_1440p",
        keyboard_layout="us",
        clock_24h=True,
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        dry_run=False,
        enable_asus=False,
        enable_blueman=True,
        enable_ags=False,
        enable_quickshell=False,
    )

    asyncio.run(
        orch.run_install(
            cfg,
            log=log,
            log_file=fake_home.copy_logs / "ghostty-test.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
        )
    )

    # Verify: No backup message (no existing config)
    assert not any("Backed up ghostty" in line for line in logs)

    # Verify: No backup directories
    backups = list(fake_home.config.glob("ghostty-backup-*"))
    assert len(backups) == 0

    # Verify: Config was still installed
    assert (fake_home.config / "ghostty" / "config").is_file()
    assert "font-size = 14" in read_text(fake_home.config / "ghostty" / "config")

    # Verify: Install log message
    assert any("Installed ghostty config" in line for line in logs)
