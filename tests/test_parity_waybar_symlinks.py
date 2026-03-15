# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dots_tui.logic.models import InstallConfig
from dots_tui.logic.orchestrator import InstallerOrchestrator

from tests.helpers import CmdRecorder, read_text, write_text


def _seed_repo(
    repo_root: Path,
    *,
    include_config_target: bool = True,
    include_style_target: bool = True,
) -> None:
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)
    (repo_root / "config" / "hypr" / "configs").mkdir(parents=True)
    write_text(
        repo_root / "config" / "hypr" / "configs" / "SystemSettings.conf", "kb\n"
    )

    (repo_root / "config" / "waybar" / "configs").mkdir(parents=True)
    if include_config_target:
        write_text(repo_root / "config" / "waybar" / "configs" / "TOP-Default", "{}\n")

    (repo_root / "config" / "waybar" / "style").mkdir(parents=True)
    if include_style_target:
        write_text(
            repo_root / "config" / "waybar" / "style" / "Extra-Prismatic-Glow.css",
            "/* css */\n",
        )


def _base_config() -> InstallConfig:
    return InstallConfig(
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
        enable_quickshell=True,
    )


def _stub_system(monkeypatch: pytest.MonkeyPatch, recorder: CmdRecorder) -> None:
    monkeypatch.setattr("dots_tui.utils.run_cmd", recorder.run)
    monkeypatch.setattr("dots_tui.utils.is_root", lambda: False)
    monkeypatch.setattr("dots_tui.utils.which", lambda _cmd: None)
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.detect_distro", lambda: ("arch", [])
    )
    monkeypatch.setattr("dots_tui.logic.orchestrator.detect_chassis", lambda: "desktop")
    monkeypatch.setattr("dots_tui.logic.orchestrator.detect_nvidia", lambda: False)
    monkeypatch.setattr("dots_tui.logic.orchestrator.detect_vm", lambda: False)
    monkeypatch.setattr("dots_tui.logic.orchestrator.detect_nixos", lambda: False)
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.get_installed_dotfiles_version",
        lambda _root=None: None,
    )


def _run_install(
    orch: InstallerOrchestrator,
    fake_home,
    *,
    logs: list[str],
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    asyncio.run(
        orch.run_install(
            _base_config(),
            log=logs.append,
            log_file=fake_home.copy_logs / "waybar-symlink-test.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
        )
    )


def test_waybar_regular_files_are_converted_to_canonical_symlinks(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)

    waybar = fake_home.config / "waybar"
    waybar.mkdir(parents=True)
    write_text(waybar / "config", '{"old": true}\n')
    write_text(waybar / "style.css", "/* old css */\n")

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    expected_config = waybar / "configs" / "TOP-Default"
    expected_style = waybar / "style" / "Extra-Prismatic-Glow.css"
    assert (waybar / "config").is_symlink()
    assert (waybar / "style.css").is_symlink()
    assert (waybar / "config").resolve(strict=True) == expected_config.resolve(
        strict=True
    )
    assert (waybar / "style.css").resolve(strict=True) == expected_style.resolve(
        strict=True
    )


def test_waybar_mismatched_symlinks_are_reset_to_canonical_targets(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)

    waybar = fake_home.config / "waybar"
    (waybar / "configs").mkdir(parents=True)
    (waybar / "style").mkdir(parents=True)
    external = fake_home.home / "external"
    external.mkdir(parents=True)
    ext_cfg = external / "cfg.json"
    ext_css = external / "theme.css"
    write_text(ext_cfg, '{"external": true}\n')
    write_text(ext_css, "/* external */\n")
    (waybar / "config").symlink_to(ext_cfg)
    (waybar / "style.css").symlink_to(ext_css)

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    assert (waybar / "config").is_symlink()
    assert (waybar / "style.css").is_symlink()
    assert (waybar / "config").resolve(strict=True) == (
        waybar / "configs" / "TOP-Default"
    ).resolve(strict=True)
    assert (waybar / "style.css").resolve(strict=True) == (
        waybar / "style" / "Extra-Prismatic-Glow.css"
    ).resolve(strict=True)


def test_waybar_broken_symlinks_are_reset_to_canonical_targets(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)

    waybar = fake_home.config / "waybar"
    (waybar / "configs").mkdir(parents=True)
    (waybar / "style").mkdir(parents=True)
    (waybar / "config").symlink_to(fake_home.home / "missing-config")
    (waybar / "style.css").symlink_to(fake_home.home / "missing-style")

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    assert (waybar / "config").is_symlink()
    assert (waybar / "style.css").is_symlink()
    assert (waybar / "config").resolve(strict=True) == (
        waybar / "configs" / "TOP-Default"
    ).resolve(strict=True)
    assert (waybar / "style.css").resolve(strict=True) == (
        waybar / "style" / "Extra-Prismatic-Glow.css"
    ).resolve(strict=True)


def test_waybar_already_canonical_symlinks_are_left_unchanged(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    waybar = fake_home.config / "waybar"
    (waybar / "configs").mkdir(parents=True)
    (waybar / "style").mkdir(parents=True)

    canonical_config = waybar / "configs" / "TOP-Default"
    canonical_style = waybar / "style" / "Extra-Prismatic-Glow.css"
    write_text(canonical_config, "{}\n")
    write_text(canonical_style, "/* css */\n")

    config_link = waybar / "config"
    style_link = waybar / "style.css"
    config_link.symlink_to(canonical_config)
    style_link.symlink_to(canonical_style)

    config_inode_before = config_link.lstat().st_ino
    style_inode_before = style_link.lstat().st_ino
    config_target_before = config_link.readlink()
    style_target_before = style_link.readlink()

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.cleanup_backups", lambda **_kwargs: None
    )

    logs: list[str] = []
    asyncio.run(
        orch._finalize_post_copy(
            _base_config(),
            fake_home.config,
            logs.append,
            prompt_confirm=prompt_confirm_yes,
            prompt_password=None,
        )
    )

    assert config_link.is_symlink()
    assert style_link.is_symlink()
    assert config_link.resolve(strict=True) == canonical_config.resolve(strict=True)
    assert style_link.resolve(strict=True) == canonical_style.resolve(strict=True)
    assert config_link.readlink() == config_target_before
    assert style_link.readlink() == style_target_before
    assert config_link.lstat().st_ino == config_inode_before
    assert style_link.lstat().st_ino == style_inode_before
    assert not any("Failed to enforce Waybar" in line for line in logs)


def test_missing_canonical_targets_warn_and_do_not_mutate_destination(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    waybar = fake_home.config / "waybar"
    waybar.mkdir(parents=True)
    original_config = '{"keep": true}\n'
    write_text(waybar / "config", original_config)
    assert not (waybar / "style.css").exists()

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.cleanup_backups", lambda **_kwargs: None
    )

    logs: list[str] = []
    asyncio.run(
        orch._finalize_post_copy(
            _base_config(),
            fake_home.config,
            logs.append,
            prompt_confirm=prompt_confirm_yes,
            prompt_password=None,
        )
    )

    assert (waybar / "config").is_file()
    assert not (waybar / "config").is_symlink()
    assert read_text(waybar / "config") == original_config
    assert not (waybar / "style.css").exists()
    assert any(
        "canonical target missing" in line and "waybar/config" in line for line in logs
    )
    assert any(
        "canonical target missing" in line and "waybar/style.css" in line
        for line in logs
    )


def test_replacement_error_logs_warning_and_finalization_continues(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    waybar = fake_home.config / "waybar"
    (waybar / "configs").mkdir(parents=True)
    (waybar / "style").mkdir(parents=True)
    write_text(waybar / "configs" / "TOP-Default", "{}\n")
    write_text(waybar / "style" / "Extra-Prismatic-Glow.css", "/* css */\n")
    write_text(waybar / "config", '{"old": true}\n')
    write_text(waybar / "style.css", "/* old css */\n")

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = fake_home.home / "repo"
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)

    original_symlink_to = Path.symlink_to

    def fail_style_symlink(
        self: Path, target: Path, target_is_directory: bool = False
    ) -> None:
        if self.name == "style.css":
            raise PermissionError("permission denied")
        original_symlink_to(self, target, target_is_directory=target_is_directory)

    monkeypatch.setattr(Path, "symlink_to", fail_style_symlink)

    cleanup_called = {"value": False}

    def mark_cleanup(*, mode, log, prompt_confirm) -> None:
        _ = mode
        _ = log
        _ = prompt_confirm
        cleanup_called["value"] = True

    monkeypatch.setattr("dots_tui.logic.orchestrator.cleanup_backups", mark_cleanup)

    logs: list[str] = []
    asyncio.run(
        orch._finalize_post_copy(
            _base_config(),
            fake_home.config,
            logs.append,
            prompt_confirm=prompt_confirm_yes,
            prompt_password=None,
        )
    )

    assert (waybar / "config").is_symlink()
    assert cleanup_called["value"] is True
    assert any("Failed to enforce Waybar style.css symlink" in line for line in logs)
