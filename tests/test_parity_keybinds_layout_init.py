# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path

import pytest

from dots_tui.logic.models import InstallConfig
from dots_tui.logic.orchestrator import InstallerOrchestrator


def _base_cfg(**kwargs: bool) -> InstallConfig:
    return InstallConfig(
        run_mode="install",
        resolution="gte_1440p",
        keyboard_layout="us",
        clock_24h=True,
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        dry_run=False,
        enable_asus=kwargs.get("enable_asus", False),
        enable_blueman=kwargs.get("enable_blueman", False),
        enable_ags=kwargs.get("enable_ags", False),
        enable_quickshell=kwargs.get("enable_quickshell", False),
    )


def _read_startup(staging_config: Path) -> str:
    return (staging_config / "hypr" / "configs" / "Startup_Apps.conf").read_text(
        encoding="utf-8", errors="replace"
    )


def test_all_optionals_disabled_still_ensures_keybinds_layout_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dots_tui.logic.orchestrator.which", lambda _cmd: None)
    staging_config = tmp_path / "config"

    orch = InstallerOrchestrator()
    orch._apply_user_choices(_base_cfg(), staging_config, log=lambda _line: None)

    text = _read_startup(staging_config)
    assert "exec-once = $scriptsDir/KeybindsLayoutInit.sh\n" in text


def test_all_optionals_disabled_keeps_optional_startup_entries_absent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dots_tui.logic.orchestrator.which", lambda _cmd: None)
    staging_config = tmp_path / "config"

    orch = InstallerOrchestrator()
    orch._apply_user_choices(_base_cfg(), staging_config, log=lambda _line: None)

    text = _read_startup(staging_config)
    assert "exec-once = rog-control-center\n" not in text
    assert "exec-once = blueman-applet\n" not in text
    assert "exec-once = ags\n" not in text
    assert "exec-once = qs\n" not in text


def test_optionals_enabled_with_prereqs_adds_entries_and_keeps_keybind_init(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.which", lambda _cmd: "/usr/bin/mock"
    )
    staging_config = tmp_path / "config"

    orch = InstallerOrchestrator()
    orch._apply_user_choices(
        _base_cfg(
            enable_asus=True,
            enable_blueman=True,
            enable_ags=True,
            enable_quickshell=True,
        ),
        staging_config,
        log=lambda _line: None,
    )

    text = _read_startup(staging_config)
    assert "exec-once = rog-control-center\n" in text
    assert "exec-once = blueman-applet\n" in text
    assert "exec-once = ags\n" in text
    assert "exec-once = qs\n" in text
    assert "exec-once = $scriptsDir/KeybindsLayoutInit.sh\n" in text


def test_keybinds_layout_init_is_idempotent_on_repeated_processing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("dots_tui.logic.orchestrator.which", lambda _cmd: None)
    staging_config = tmp_path / "config"
    startup = staging_config / "hypr" / "configs" / "Startup_Apps.conf"
    startup.parent.mkdir(parents=True, exist_ok=True)
    startup.write_text(
        "exec-once = $scriptsDir/KeybindsLayoutInit.sh\n", encoding="utf-8"
    )

    orch = InstallerOrchestrator()
    cfg = _base_cfg()
    orch._apply_user_choices(cfg, staging_config, log=lambda _line: None)
    orch._apply_user_choices(cfg, staging_config, log=lambda _line: None)

    text = _read_startup(staging_config)
    assert text.count("exec-once = $scriptsDir/KeybindsLayoutInit.sh\n") == 1
