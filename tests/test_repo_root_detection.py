from __future__ import annotations

from pathlib import Path

from dots_tui.logic.orchestrator import InstallerOrchestrator


def _patch_cwd_and_home(monkeypatch, *, cwd: Path, home: Path) -> None:
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.Path.cwd",
        classmethod(lambda _cls: cwd),
    )
    monkeypatch.setattr(
        "dots_tui.logic.orchestrator.Path.home",
        classmethod(lambda _cls: home),
    )


def test_detect_repo_root_finds_parent_repo(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "my-repo"
    (repo / "config").mkdir(parents=True)
    (repo / "scripts").mkdir(parents=True)
    cwd = repo / "tui-installer"
    cwd.mkdir(parents=True)

    _patch_cwd_and_home(monkeypatch, cwd=cwd, home=tmp_path / "home")

    orch = InstallerOrchestrator()

    assert orch.repo_root == repo


def test_detect_repo_root_falls_back_to_home_hyprland_dots(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home_repo = home / "Hyprland-Dots"
    (home_repo / "config").mkdir(parents=True)
    (home_repo / "scripts").mkdir(parents=True)
    cwd = tmp_path / "standalone-tui"
    cwd.mkdir(parents=True)

    _patch_cwd_and_home(monkeypatch, cwd=cwd, home=home)

    orch = InstallerOrchestrator()

    assert orch.repo_root == home_repo


def test_detect_repo_root_falls_back_to_home_hyprland_dots_lowercase(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    home_repo = home / "hyprland-dots"
    (home_repo / "config").mkdir(parents=True)
    (home_repo / "scripts").mkdir(parents=True)
    cwd = tmp_path / "standalone-tui"
    cwd.mkdir(parents=True)

    _patch_cwd_and_home(monkeypatch, cwd=cwd, home=home)

    orch = InstallerOrchestrator()

    assert orch.repo_root == home_repo


def test_detect_repo_root_finds_child_hyprland_dots_dir(
    tmp_path: Path,
    monkeypatch,
) -> None:
    home = tmp_path / "home"
    cwd = tmp_path / "standalone-tui"
    cwd.mkdir(parents=True)
    child_repo = cwd / "Hyprland-Dots"
    (child_repo / "config").mkdir(parents=True)
    (child_repo / "scripts").mkdir(parents=True)

    _patch_cwd_and_home(monkeypatch, cwd=cwd, home=home)

    orch = InstallerOrchestrator()

    assert orch.repo_root == child_repo
