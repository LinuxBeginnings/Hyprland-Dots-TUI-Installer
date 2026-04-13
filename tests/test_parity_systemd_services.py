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
from dots_tui.utils import CmdResult

from tests.helpers import CmdCall, CmdRecorder, write_text


def _seed_repo(repo_root: Path, *, include_systemd: bool = True) -> None:
    """Seed a minimal repository structure with optional systemd configs."""
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)
    (repo_root / "config" / "hypr" / "configs").mkdir(parents=True)
    write_text(
        repo_root / "config" / "hypr" / "configs" / "SystemSettings.conf", "kb\n"
    )

    if include_systemd:
        systemd_dir = (
            repo_root / "config" / "systemd" / "user" / "hyprpolkitagent.service.d"
        )
        systemd_dir.mkdir(parents=True)
        write_text(
            systemd_dir / "override.conf",
            "[Service]\nExecStart=/usr/bin/hyprpolkitagent\n",
        )


def _base_config(*, dry_run: bool = False) -> InstallConfig:
    """Return a base configuration for testing."""
    return InstallConfig(
        run_mode="install",
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


class SystemdCmdRecorder(CmdRecorder):
    """Extended CmdRecorder with systemd-specific command mocking."""

    def __init__(
        self,
        *,
        systemctl_exists: bool = True,
        pgrep_exists: bool = True,
        service_exists: bool = True,
        conflict_detected: bool = False,
        daemon_reload_fails: bool = False,
    ) -> None:
        super().__init__()
        self.systemctl_exists = systemctl_exists
        self.pgrep_exists = pgrep_exists
        self.service_exists = service_exists
        self.conflict_detected = conflict_detected
        self.daemon_reload_fails = daemon_reload_fails

    async def run(
        self,
        argv: list[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        log=None,
        input_text: str | None = None,
    ) -> CmdResult:
        """Mock systemctl and pgrep commands with configurable responses."""
        self.calls.append(CmdCall(argv=list(argv), cwd=cwd))

        if log is not None:
            log(f"$ {' '.join(argv)}")

        # Mock systemctl list-unit-files
        if argv == ["systemctl", "--user", "list-unit-files"]:
            if self.service_exists:
                output = "hyprpolkitagent.service        static\nother.service        enabled\n"
            else:
                output = "other.service        enabled\n"
            return CmdResult(argv=list(argv), returncode=0, output=output)

        # Mock systemctl daemon-reload
        if argv == ["systemctl", "--user", "daemon-reload"]:
            if self.daemon_reload_fails:
                return CmdResult(
                    argv=list(argv), returncode=1, output="Failed to reload\n"
                )
            return CmdResult(argv=list(argv), returncode=0, output="")

        # Mock pgrep
        if argv[0] == "pgrep":
            if self.conflict_detected:
                return CmdResult(argv=list(argv), returncode=0, output="1234\n")
            else:
                return CmdResult(argv=list(argv), returncode=1, output="")

        # Mock systemctl enable/start
        if argv[0:2] == ["systemctl", "--user"] and argv[2] in ["enable", "start"]:
            return CmdResult(argv=list(argv), returncode=0, output="")

        # Default
        return CmdResult(argv=list(argv), returncode=0, output="")


def _stub_system(
    monkeypatch: pytest.MonkeyPatch,
    recorder: SystemdCmdRecorder,
) -> None:
    """Stub system detection and command execution."""
    monkeypatch.setattr("dots_tui.utils.run_cmd", recorder.run)
    monkeypatch.setattr("dots_tui.utils.is_root", lambda: False)

    # Mock which() for systemctl and pgrep
    def mock_which(cmd: str) -> str | None:
        if cmd == "systemctl" and recorder.systemctl_exists:
            return "/usr/bin/systemctl"
        if cmd == "pgrep" and recorder.pgrep_exists:
            return "/usr/bin/pgrep"
        return None

    monkeypatch.setattr("dots_tui.utils.which", mock_which)
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
    dry_run: bool = False,
) -> None:
    """Run the installer with test configuration."""
    asyncio.run(
        orch.run_install(
            _base_config(dry_run=dry_run),
            log=logs.append,
            log_file=fake_home.copy_logs / "systemd-test.log",
            set_step=lambda _m, _p: None,
            prompt_replace=prompt_replace_yes,
            prompt_confirm=prompt_confirm_yes,
        )
    )


# ============================================================================
# Test Cases - Happy Path and Edge Cases
# ============================================================================


def test_systemd_directory_copied_when_present(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """TS-1 partial: Verify systemd directory is copied from staging to ~/.config/systemd/."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify systemd directory was copied
    systemd_dest = fake_home.config / "systemd" / "user" / "hyprpolkitagent.service.d"
    assert systemd_dest.exists(), "systemd directory should be copied"
    override_conf = systemd_dest / "override.conf"
    assert override_conf.is_file(), "override.conf should exist"
    assert "[Service]" in override_conf.read_text()


def test_daemon_reload_and_service_enabled_when_unit_file_exists(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """TS-1 complete: Verify full happy path - daemon-reload, enable, and start."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=True,
        service_exists=True,
        conflict_detected=False,
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify command sequence
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]

    # Check daemon-reload was called
    assert any("systemctl --user daemon-reload" in cmd for cmd in cmd_strs), (
        "daemon-reload should be executed"
    )

    # Check list-unit-files was called
    assert any("systemctl --user list-unit-files" in cmd for cmd in cmd_strs), (
        "list-unit-files should be executed"
    )

    # Check pgrep was called for conflict detection
    assert any("pgrep" in cmd for cmd in cmd_strs), (
        "pgrep should be executed for conflict detection"
    )

    # Check enable was called
    assert any("systemctl --user enable hyprpolkitagent" in cmd for cmd in cmd_strs), (
        "enable should be executed"
    )

    # Check start was called
    assert any("systemctl --user start hyprpolkitagent" in cmd for cmd in cmd_strs), (
        "start should be executed"
    )

    # Check success log
    assert any(
        "enabled and started" in log and "hyprpolkitagent" in log for log in logs
    )


def test_service_skipped_when_conflicting_process_detected(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """TS-2: Verify service is skipped when a conflicting polkit agent is running."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=True,
        service_exists=True,
        conflict_detected=True,  # Simulate conflict
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify enable/start were NOT called
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]
    assert not any(
        "systemctl --user enable hyprpolkitagent" in cmd for cmd in cmd_strs
    ), "enable should NOT be executed when conflict detected"
    assert not any(
        "systemctl --user start hyprpolkitagent" in cmd for cmd in cmd_strs
    ), "start should NOT be executed when conflict detected"

    # Verify log message about conflict
    assert any(
        "Conflicting process" in log and "hyprpolkitagent" in log for log in logs
    ), "Should log message about conflicting process"


def test_systemd_operations_skipped_when_systemctl_missing(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """TS-3: Verify graceful degradation when systemctl is not available."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=False,  # systemctl not available
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify no systemctl commands were executed
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]
    assert not any("systemctl" in cmd for cmd in cmd_strs), (
        "No systemctl commands should be executed when systemctl is missing"
    )

    # Verify graceful skip message
    assert any(
        "systemctl not found" in log and "skipping" in log.lower() for log in logs
    ), "Should log message about systemctl not found"


def test_service_not_started_when_unit_file_missing(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """TS-4: Verify service is skipped when unit file is not found."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=True,
        service_exists=False,  # Service not found in list-unit-files
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify enable/start were NOT called
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]
    assert not any(
        "systemctl --user enable hyprpolkitagent" in cmd for cmd in cmd_strs
    ), "enable should NOT be executed when service not found"
    assert not any(
        "systemctl --user start hyprpolkitagent" in cmd for cmd in cmd_strs
    ), "start should NOT be executed when service not found"

    # Verify log message about service not found
    assert any("not found" in log and "hyprpolkitagent" in log for log in logs), (
        "Should log message about service not found"
    )


def test_dry_run_logs_systemd_operations_without_execution(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """TS-5: Verify dry-run mode logs operations without executing them."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=True,
        service_exists=True,
        conflict_detected=False,
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
        dry_run=True,
    )

    # Verify systemd directory WAS copied to sandbox in dry-run
    # In dry-run mode, target_config_root is redirected to sandbox
    # so the copy operation executes to sandbox, not to real ~/.config
    # Note: Directory copy happens to sandbox - only external commands are skipped

    # Verify the systemd configs were actually copied (to sandbox)
    assert any("[OK]" in log and "Copied systemd configs" in log for log in logs), (
        "Should log successful copy to sandbox in dry-run"
    )
    assert any("[DRY-RUN]" in log and "daemon-reload" in log for log in logs), (
        "Should log dry-run daemon-reload"
    )

    # External commands (systemctl enable/start) are skipped in dry-run
    # This is correct behavior per the codebase pattern


# ============================================================================
# Error Handling Tests
# ============================================================================


def test_copy_failure_logs_warning_and_continues(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """EC-3: Verify installation continues when systemd copy fails."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder()
    _stub_system(monkeypatch, recorder)

    # Mock shutil.copytree to raise exception only for systemd in _setup_systemd_services
    import shutil

    original_copytree = shutil.copytree

    def mock_copytree(src, dst, *args, **kwargs):
        # Only fail if copying systemd to .config/systemd (not staging copy)
        if "systemd" in str(src) and ".config/systemd" in str(dst):
            raise PermissionError("Permission denied")
        return original_copytree(src, dst, *args, **kwargs)

    monkeypatch.setattr("shutil.copytree", mock_copytree)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify warning was logged
    assert any("Failed to copy systemd" in log or "WARN" in log for log in logs), (
        "Should log warning about copy failure"
    )

    # Verify no systemctl commands were executed (early return after copy failure)
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]
    assert not any("systemctl --user daemon-reload" in cmd for cmd in cmd_strs), (
        "daemon-reload should NOT be executed after copy failure"
    )


def test_daemon_reload_failure_logs_warning_and_continues(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """EC-1: Verify installation continues when daemon-reload fails."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=True,
        service_exists=True,
        conflict_detected=False,
        daemon_reload_fails=True,  # Simulate daemon-reload failure
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify warning was logged about daemon-reload failure
    assert any(
        "daemon-reload failed" in log or ("WARN" in log and "daemon" in log)
        for log in logs
    ), "Should log warning about daemon-reload failure"

    # Verify installation still attempted enable/start (continues despite failure)
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]
    assert any("systemctl --user enable hyprpolkitagent" in cmd for cmd in cmd_strs), (
        "enable should still be attempted after daemon-reload failure"
    )


def test_missing_pgrep_skips_conflict_check_and_enables_service(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    prompt_replace_yes,
    prompt_confirm_yes,
) -> None:
    """EC-8: Verify service is enabled when pgrep is not available."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root, include_systemd=True)

    recorder = SystemdCmdRecorder(
        systemctl_exists=True,
        pgrep_exists=False,  # pgrep not available
        service_exists=True,
    )
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda **_kw: fake_home.copy_logs)

    logs: list[str] = []
    _run_install(
        orch,
        fake_home,
        logs=logs,
        prompt_replace_yes=prompt_replace_yes,
        prompt_confirm_yes=prompt_confirm_yes,
    )

    # Verify pgrep was not called
    cmd_strs = [" ".join(call.argv) for call in recorder.calls]
    assert not any("pgrep" in cmd for cmd in cmd_strs), (
        "pgrep should NOT be called when not available"
    )

    # Verify log about pgrep not found
    assert any("pgrep not found" in log for log in logs), (
        "Should log message about pgrep not found"
    )

    # Verify service was still enabled (no conflict check performed)
    assert any("systemctl --user enable hyprpolkitagent" in cmd for cmd in cmd_strs), (
        "enable should still be executed when pgrep is missing"
    )
