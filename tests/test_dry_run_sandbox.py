# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
"""Tests for sandbox-based dry-run mode.

Replaces the old PlanCollector-based test_dry_run_plan_mode.py.
The sandbox approach redirects ALL writes to a TemporaryDirectory
so that the real $HOME is never touched.
"""

from __future__ import annotations

import asyncio

import pytest

from dots_tui.logic.models import InstallConfig
from dots_tui.logic.orchestrator import InstallerOrchestrator

from tests.helpers import CmdRecorder, write_text


def _make_config(*, run_mode: str = "install", dry_run: bool = True) -> InstallConfig:
    return InstallConfig(
        run_mode=run_mode,
        resolution="gte_1440p",
        keyboard_layout="us",
        clock_24h=True,
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        dry_run=dry_run,
        enable_asus=False,
        enable_blueman=True,
        enable_ags=False,
        enable_quickshell=True,
    )


def _stub_system(monkeypatch: pytest.MonkeyPatch, recorder: CmdRecorder) -> None:
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


def _seed_repo(fake_home) -> None:
    """Create the minimal repo structure needed for run_install."""
    repo_root = fake_home.home / "repo"
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)

    write_text(
        repo_root / "config" / "hypr" / "configs" / "SystemSettings.conf",
        "  kb_layout = us\n",
    )
    (repo_root / "config" / "rofi" / "themes").mkdir(parents=True)
    (repo_root / "config" / "waybar" / "configs").mkdir(parents=True)
    write_text(repo_root / "config" / "waybar" / "configs" / "[TOP] Default", "{}\n")
    (repo_root / "config" / "waybar" / "style").mkdir(parents=True)
    write_text(
        repo_root / "config" / "waybar" / "style" / "[Extra] Neon Circuit.css",
        "/* css */\n",
    )


def test_dry_run_creates_no_files_under_real_home(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """Dry-run sandbox: nothing is written to fake_home/.config."""
    _seed_repo(fake_home)
    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []

    asyncio.run(
        orch.run_install(
            _make_config(dry_run=True),
            log=logs.append,
            log_file=fake_home.copy_logs / "dry-run.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
            prompt_input=lambda _label: "F",
        )
    )

    # Assert: no config directories created under real home
    assert not (fake_home.config / "hypr").exists()
    assert not (fake_home.config / "waybar").exists()
    assert not (fake_home.config / "rofi").exists()


def test_dry_run_emits_sandbox_log_lines(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """Dry-run logs [DRY-RUN] Sandbox and [DRY-RUN] Complete messages."""
    _seed_repo(fake_home)
    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []

    asyncio.run(
        orch.run_install(
            _make_config(dry_run=True),
            log=logs.append,
            log_file=fake_home.copy_logs / "dry-run.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
            prompt_input=lambda _label: "F",
        )
    )

    assert any("[DRY-RUN] Sandbox:" in line for line in logs), (
        "Expected [DRY-RUN] Sandbox: log line"
    )
    assert any("[DRY-RUN] Complete" in line for line in logs), (
        "Expected [DRY-RUN] Complete log line"
    )


def test_dry_run_skips_sudo_and_external_commands(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """Dry-run skips sudo pre-auth, xdg-user-dirs-update, and SDDM ops."""
    _seed_repo(fake_home)
    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []

    asyncio.run(
        orch.run_install(
            _make_config(dry_run=True),
            log=logs.append,
            log_file=fake_home.copy_logs / "dry-run.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
            prompt_input=lambda _label: "F",
        )
    )

    assert any("[DRY-RUN] Skipped: sudo pre-auth" in line for line in logs)
    assert any("[DRY-RUN] Skipped: xdg-user-dirs-update" in line for line in logs)
    assert any("[DRY-RUN] Skipped: SDDM sudo operations" in line for line in logs)

    # Verify no sudo or xdg-user-dirs-update commands were actually executed
    for cmd_args, _ in recorder.calls:
        assert "sudo" not in cmd_args, (
            f"sudo command executed during dry-run: {cmd_args}"
        )
        assert "xdg-user-dirs-update" not in cmd_args, (
            f"xdg-user-dirs-update executed during dry-run: {cmd_args}"
        )


def test_dry_run_version_detection_uses_real_config_path(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """get_installed_dotfiles_version is called with the REAL config root, not sandbox."""
    _seed_repo(fake_home)
    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    version_check_paths: list[str] = []

    def spy_get_version(root):
        version_check_paths.append(str(root))
        return None

    # Patch in both locations: system module AND orchestrator's local import
    monkeypatch.setattr(
        "dots_tui.logic.system.get_installed_dotfiles_version",
        spy_get_version,
    )
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.get_installed_dotfiles_version",
        spy_get_version,
    )

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    asyncio.run(
        orch.run_install(
            _make_config(dry_run=True),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "dry-run.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
            prompt_input=lambda _label: "F",
        )
    )

    # The version check should use the real config path, not contain "sandbox"
    assert len(version_check_paths) >= 1
    for p in version_check_paths:
        assert "sandbox" not in p, f"Version detection used sandbox path: {p}"


def test_dry_run_express_does_not_prompt_for_weather_units(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """In dry-run express mode, weather binary install is skipped (no prompt)."""
    repo_root = fake_home.home / "repo"
    (repo_root / "config" / "waybar-weather").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)
    write_text(
        repo_root / "config" / "waybar-weather" / "config.toml", 'units = "metric"\n'
    )

    # Also need minimal config for run_install
    write_text(
        repo_root / "config" / "hypr" / "configs" / "SystemSettings.conf",
        "  kb_layout = us\n",
    )
    (repo_root / "config" / "rofi" / "themes").mkdir(parents=True)
    (repo_root / "config" / "waybar" / "configs").mkdir(parents=True)
    write_text(repo_root / "config" / "waybar" / "configs" / "[TOP] Default", "{}\n")
    (repo_root / "config" / "waybar" / "style").mkdir(parents=True)
    write_text(
        repo_root / "config" / "waybar" / "style" / "[Extra] Neon Circuit.css",
        "/* css */\n",
    )

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)
    monkeypatch.setattr(
        "dots_tui.logic.system.get_installed_dotfiles_version",
        lambda _root: "999.0.0",
    )

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    def prompt_input(_label: str) -> str | None:
        raise AssertionError("dry-run must not request weather units input")

    cfg = _make_config(run_mode="express", dry_run=True)

    # Should not raise — dry-run skips the weather binary install prompt
    asyncio.run(
        orch.run_install(
            cfg,
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "dry-run-express.log",
            set_step=lambda _m, _p: None,
            prompt_input=prompt_input,
        )
    )
