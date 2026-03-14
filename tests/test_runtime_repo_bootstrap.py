from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from dots_tui.logic.models import InstallConfig
from dots_tui.logic.orchestrator import InstallerOrchestrator
from dots_tui.utils import CmdResult


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
        enable_blueman=False,
        enable_ags=False,
        enable_quickshell=False,
    )


def test_install_bootstraps_repo_when_runtime_sources_are_missing(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    standalone = fake_home.home / "standalone"
    standalone.mkdir(parents=True)

    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.Path.cwd",
        classmethod(lambda _cls: standalone),
    )
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.Path.home",
        classmethod(lambda _cls: fake_home.home),
    )

    calls: list[list[str]] = []

    async def fake_run_cmd(
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        log=None,
        input_text: str | None = None,
    ) -> CmdResult:
        _ = (cwd, env, input_text)
        calls.append(list(argv))
        if argv[:3] == ["git", "clone", "--depth"]:
            target = Path(argv[-1])
            (target / "config").mkdir(parents=True, exist_ok=True)
            (target / "scripts").mkdir(parents=True, exist_ok=True)
        return CmdResult(argv=list(argv), returncode=0, output="")

    monkeypatch.setattr("dots_tui.logic.orchestrator.run_cmd", fake_run_cmd)
    monkeypatch.setattr("dots_tui.logic.orchestrator.is_root", lambda: False)
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.which", lambda _cmd: "/usr/bin/git"
    )
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

    orch = InstallerOrchestrator()

    async def noop_async(*_args, **_kwargs) -> None:
        return None

    monkeypatch.setattr(orch, "_handle_waybar_weather_binary", noop_async)
    monkeypatch.setattr(orch, "_install_wallpapers", noop_async)
    monkeypatch.setattr(orch, "_finalize_post_copy", noop_async)

    asyncio.run(
        orch.run_install(
            _base_config(),
            log=lambda _line: None,
            log_file=fake_home.copy_logs / "bootstrap.log",
            set_step=lambda _message, _percent=None: None,
        )
    )

    expected_repo = fake_home.home / "Hyprland-Dots"
    assert orch.repo_root == expected_repo
    assert any(cmd[:3] == ["git", "clone", "--depth"] for cmd in calls)
    assert (expected_repo / "config").is_dir()
    assert (expected_repo / "scripts").is_dir()
