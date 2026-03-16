from __future__ import annotations

import asyncio
import re
import tomllib

import pytest

from dots_tui.logic.models import InstallConfig, RunMode
from dots_tui.logic.orchestrator import InstallerOrchestrator

from tests.helpers import CmdRecorder, read_text, write_text


def _seed_repo(repo_root) -> None:
    (repo_root / "config").mkdir(parents=True)
    (repo_root / "scripts").mkdir(parents=True)
    write_text(
        repo_root / "config" / "waybar-weather" / "config.toml",
        '# units = "metric"\nunits = "metric"\nunits = "kelvin"\n',
    )


def _base_config(run_mode: RunMode, weather_units: str = "C") -> InstallConfig:
    return InstallConfig(
        run_mode=run_mode,
        resolution="gte_1440p",
        keyboard_layout="us",
        clock_24h=True,
        weather_units=weather_units,  # type: ignore[arg-type]
        default_editor=None,
        download_wallpapers=False,
        apply_sddm_wallpaper=False,
        dry_run=False,
        enable_asus=False,
        enable_blueman=False,
        enable_ags=False,
        enable_quickshell=False,
    )


def _stub_system(
    monkeypatch: pytest.MonkeyPatch,
    recorder: CmdRecorder,
    *,
    installed_version: str | None = None,
) -> None:
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
        lambda _root: installed_version,
    )


def test_install_mode_refreshes_weather_config(
    fake_home, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)
    write_text(
        fake_home.config / "waybar-weather" / "config.toml", 'units = "legacy"\n'
    )

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder, installed_version="999.0.0")
    monkeypatch.setattr("dots_tui.logic.orchestrator.version_gte", lambda _a, _b: True)
    monkeypatch.setattr("dots_tui.logic.orchestrator.version_gte", lambda _a, _b: True)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        orch,
        "_handle_waybar_weather_binary",
        lambda **_kwargs: asyncio.sleep(0),
    )

    asyncio.run(
        orch.run_install(
            _base_config("install"),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "weather-install.log",
            set_step=lambda _m, _p: None,
        )
    )

    text = read_text(fake_home.config / "waybar-weather" / "config.toml")
    assert 'units = "legacy"' not in text
    assert 'units = "metric"' in text


def test_upgrade_mode_preserves_existing_weather_config(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)
    write_text(
        fake_home.config / "waybar-weather" / "config.toml", 'units = "legacy"\n'
    )

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder, installed_version="999.0.0")

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        orch,
        "_handle_waybar_weather_binary",
        lambda **_kwargs: asyncio.sleep(0),
    )

    asyncio.run(
        orch.run_install(
            _base_config("upgrade"),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "weather-upgrade.log",
            set_step=lambda _m, _p: None,
        )
    )

    text = read_text(fake_home.config / "waybar-weather" / "config.toml")
    assert 'units = "legacy"' in text


def test_express_mode_copies_missing_weather_config_without_prompt(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder, installed_version="999.0.0")

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        orch,
        "_handle_waybar_weather_binary",
        lambda **_kwargs: asyncio.sleep(0),
    )

    def fail_prompt(_label: str) -> str | None:
        raise AssertionError("units prompt must not be shown in express mode")

    asyncio.run(
        orch.run_install(
            _base_config("express"),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "weather-express.log",
            set_step=lambda _m, _p: None,
            prompt_input=fail_prompt,
        )
    )

    assert (fake_home.config / "waybar-weather" / "config.toml").is_file()


def test_non_express_existing_weather_config_does_not_prompt_units(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)
    write_text(
        fake_home.config / "waybar-weather" / "config.toml", 'units = "legacy"\n'
    )

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder, installed_version="999.0.0")

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        orch,
        "_handle_waybar_weather_binary",
        lambda **_kwargs: asyncio.sleep(0),
    )

    def fail_prompt(_label: str) -> str | None:
        raise AssertionError(
            "units prompt must not be shown when weather config was not copied"
        )

    asyncio.run(
        orch.run_install(
            _base_config("upgrade"),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "weather-upgrade-no-prompt.log",
            set_step=lambda _m, _p: None,
            prompt_input=fail_prompt,
        )
    )

    cfg = read_text(fake_home.config / "waybar-weather" / "config.toml")
    assert cfg == 'units = "legacy"\n'


def test_nixos_missing_binary_warns_and_does_not_attempt_install(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    orch = InstallerOrchestrator()
    logs: list[str] = []
    attempted = {"value": False}

    monkeypatch.setattr("dots_tui.logic.orchestrator.which", lambda _cmd: None)

    async def fail_attempt(**_kwargs) -> bool:
        attempted["value"] = True
        return False

    monkeypatch.setattr(orch, "_attempt_waybar_weather_install", fail_attempt)

    asyncio.run(
        orch._handle_waybar_weather_binary(
            log=logs.append,
            is_nixos=True,
            distro_id="nixos",
            prompt_password=None,
            plan=None,
        )
    )

    assert attempted["value"] is False
    assert any("missing" in line for line in logs)


def test_non_nixos_install_failure_is_non_fatal_and_continues(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)

    async def fail_attempt(**_kwargs) -> bool:
        raise RuntimeError("boom")

    monkeypatch.setattr(orch, "_attempt_waybar_weather_install", fail_attempt)

    logs: list[str] = []
    asyncio.run(
        orch.run_install(
            _base_config("install"),
            log=logs.append,
            log_file=fake_home.copy_logs / "weather-fail.log",
            set_step=lambda _m, _p: None,
        )
    )

    assert any("install failed" in line for line in logs)
    assert (fake_home.config / "waybar-weather" / "config.toml").is_file()


@pytest.mark.parametrize(
    ("weather_units", "expect_imperial"),
    [("F", True), ("C", False)],
)
def test_units_from_config_gating_and_outcomes(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
    weather_units: str,
    expect_imperial: bool,
) -> None:
    """Weather units are read from InstallConfig instead of prompting."""
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        orch,
        "_handle_waybar_weather_binary",
        lambda **_kwargs: asyncio.sleep(0),
    )

    # No prompt function should be called
    def fail_prompt(_label: str) -> str | None:
        raise AssertionError("weather units must be read from config, not prompted")

    asyncio.run(
        orch.run_install(
            _base_config("install", weather_units=weather_units),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "weather-config.log",
            set_step=lambda _m, _p: None,
            prompt_input=fail_prompt,
        )
    )

    cfg = read_text(fake_home.config / "waybar-weather" / "config.toml")
    if expect_imperial:
        active_units = re.findall(r'^\s*units\s*=\s*"([^"]+)"', cfg, flags=re.MULTILINE)
        assert active_units == ["imperial"], (
            f"Expected ['imperial'], got {active_units}"
        )
        parsed = tomllib.loads(cfg)
        assert parsed["units"] == "imperial"
    else:
        assert 'units = "imperial"' not in cfg


def test_fahrenheit_adds_units_when_key_is_absent(
    fake_home,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo_root = fake_home.home / "repo"
    _seed_repo(repo_root)
    write_text(
        repo_root / "config" / "waybar-weather" / "config.toml", 'api_key = "x"\n'
    )

    recorder = CmdRecorder()
    _stub_system(monkeypatch, recorder)

    orch = InstallerOrchestrator()
    orch.repo_root = repo_root
    monkeypatch.setattr(orch, "_copy_logs_dir", lambda: fake_home.copy_logs)
    monkeypatch.setattr(
        orch,
        "_handle_waybar_weather_binary",
        lambda **_kwargs: asyncio.sleep(0),
    )

    asyncio.run(
        orch.run_install(
            _base_config("install", weather_units="F"),
            log=lambda _l: None,
            log_file=fake_home.copy_logs / "weather-units-absent.log",
            set_step=lambda _m, _p: None,
        )
    )

    cfg = read_text(fake_home.config / "waybar-weather" / "config.toml")
    active_units = re.findall(r'^\s*units\s*=\s*"([^"]+)"', cfg, flags=re.MULTILINE)
    assert active_units == ["imperial"], f"Expected ['imperial'], got {active_units}"
