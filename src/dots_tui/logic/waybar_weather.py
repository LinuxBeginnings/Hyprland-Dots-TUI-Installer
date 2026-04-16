# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import gzip
import re
import shutil
import tempfile
from pathlib import Path
from typing import Awaitable, Callable

from dots_tui.logic.models import LogFn
from dots_tui.logic.path_safety import assert_safe_path
import dots_tui.utils as utils

# ============================================================================
# Constants
# ============================================================================
WAYBAR_WEATHER_DIRNAME = "waybar-weather"


async def handle_waybar_weather_binary(
    *,
    repo_root: Path,
    log: LogFn,
    is_nixos: bool,
    distro_id: str | None,
    run_sudo_cmd: Callable[..., Awaitable[bool]],
    dry_run: bool,
) -> None:
    """Install waybar-weather binary via AUR or bundled asset.

    Skips in dry_run. Does not raise on install failure — logs WARN and continues.

    Args:
        repo_root: Path to the dotfiles repository root (for bundled asset).
        log: Logging function for user-visible messages.
        is_nixos: Whether the system is NixOS.
        distro_id: Linux distribution ID (e.g., "arch").
        run_sudo_cmd: Callable to run a command with sudo.
        dry_run: If True, skip all install operations.
    """
    if dry_run:
        log("[DRY-RUN] Skipped: waybar-weather binary install")
        return

    if utils.which("waybar-weather"):
        log("[OK] waybar-weather binary detected.")
        return

    if is_nixos:
        log("[WARN] waybar-weather binary is missing.")
        log(
            "[NOTE] Install the current NixOS-Hyprland version to install "
            "waybar-weather applet for Waybar"
        )
        return

    log("[INFO] waybar-weather binary not found; attempting best-effort install")
    try:
        installed = await _attempt_waybar_weather_install(
            repo_root=repo_root,
            distro_id=distro_id,
            log=log,
            run_sudo_cmd=run_sudo_cmd,
        )
    except Exception as exc:
        log(f"[WARN] waybar-weather install failed ({exc}); continuing")
        return

    if installed:
        log("[OK] waybar-weather install step completed")
    else:
        log("[WARN] waybar-weather install was not completed; continuing")


def handle_waybar_weather_config(
    *,
    run_mode: str,
    staging_config_root: Path,
    target_config_root: Path,
    log: LogFn,
) -> bool:
    """Copy waybar-weather config directory to target.

    On fresh install (install mode), always copies. On upgrade/express, skips if
    target already exists.

    Args:
        run_mode: One of "install", "upgrade", "express".
        staging_config_root: Path to the staged config tree.
        target_config_root: Target ~/.config directory.
        log: Logging function.

    Returns:
        True iff config was copied.
    """
    src = staging_config_root / WAYBAR_WEATHER_DIRNAME
    dst = target_config_root / WAYBAR_WEATHER_DIRNAME

    if run_mode == "install":
        if not src.is_dir():
            log(f"[WARN] - waybar-weather config not found at {src}")
            return False

        log("[INFO] - Copying waybar-weather config (fresh copy)")
        _copy_waybar_weather_dir(src=src, dst=dst, replace=True)
        return True

    if run_mode in {"upgrade", "express"}:
        if dst.exists():
            log("[INFO] - waybar-weather config exists; skipping copy")
            return False

        if not src.is_dir():
            log(f"[WARN] - waybar-weather config not found at {src}")
            return False

        log("[INFO] - Copying waybar-weather config")
        _copy_waybar_weather_dir(src=src, dst=dst, replace=False)
        return True

    return False


def handle_waybar_weather_units(
    *,
    run_mode: str,
    weather_units: str,
    weather_config_copied: bool,
    target_config_root: Path,
    log: LogFn,
) -> None:
    """Patch config.toml to use imperial units if requested.

    Args:
        run_mode: One of "install", "upgrade", "express".
        weather_units: "F" for imperial, anything else skips.
        weather_config_copied: Whether the config was just copied (must be True).
        target_config_root: Target ~/.config directory.
        log: Logging function.
    """
    eligible = run_mode != "express" and weather_config_copied

    if not eligible:
        return

    weather_cfg = target_config_root / WAYBAR_WEATHER_DIRNAME / "config.toml"
    if weather_units == "F":
        _apply_waybar_weather_imperial(weather_cfg, log)


async def _attempt_waybar_weather_install(
    *,
    repo_root: Path,
    distro_id: str | None,
    log: LogFn,
    run_sudo_cmd: Callable[..., Awaitable[bool]],
) -> bool:
    """Try AUR install first, then bundled asset fallback.

    Args:
        repo_root: Path to the dotfiles repository root.
        distro_id: Linux distribution ID.
        log: Logging function.
        run_sudo_cmd: Callable to run a command with sudo.

    Returns:
        True if the binary was successfully installed.
    """
    if distro_id == "arch" and utils.which("yay"):
        res = await utils.run_cmd(
            ["yay", "-S", "--noconfirm", "waybar-weather"], log=log
        )
        if res.returncode == 0:
            return True
        log("[WARN] AUR install failed; falling back to bundled asset")

    asset_path = repo_root / "assets" / "waybar-weather.gz"
    if not asset_path.is_file():
        return False

    with tempfile.NamedTemporaryFile(prefix="waybar-weather-", delete=False) as tmp:
        tmp_path = Path(tmp.name)

    try:
        with gzip.open(asset_path, "rb") as src, tmp_path.open("wb") as dst:
            shutil.copyfileobj(src, dst)
        tmp_path.chmod(0o755)

        ok = await run_sudo_cmd(
            ["install", "-m", "0755", str(tmp_path), "/usr/bin/waybar-weather"],
            description="install waybar-weather binary",
        )
        return ok
    finally:
        tmp_path.unlink(missing_ok=True)


def _copy_waybar_weather_dir(*, src: Path, dst: Path, replace: bool) -> None:
    """Copy src directory to dst, optionally replacing existing target.

    Args:
        src: Source directory.
        dst: Destination directory.
        replace: If True, remove existing dst before copying.
    """
    assert_safe_path(dst)
    if replace and (dst.exists() or dst.is_symlink()):
        if dst.is_symlink() or dst.is_file():
            dst.unlink(missing_ok=True)
        else:
            shutil.rmtree(dst)

    if not dst.exists():
        dst.mkdir(parents=True, exist_ok=True)

    shutil.copytree(src, dst, dirs_exist_ok=True, symlinks=True)


def _apply_waybar_weather_imperial(weather_cfg: Path, log: LogFn) -> None:
    """Patch config.toml to set units = "imperial".

    Args:
        weather_cfg: Path to the waybar-weather config.toml.
        log: Logging function.
    """
    if not weather_cfg.is_file():
        log(f"[WARN] - waybar-weather config not found at {weather_cfg}")
        return

    lines = weather_cfg.read_text(encoding="utf-8", errors="replace").splitlines(True)
    out: list[str] = []
    replaced = False
    units_pat = re.compile(r"^\s*(?:#\s*)?units\s*=")

    for line in lines:
        if units_pat.match(line):
            if not replaced:
                out.append('units = "imperial"\n')
                replaced = True
            continue
        out.append(line)

    if not replaced:
        if out and not out[-1].endswith("\n"):
            out[-1] = out[-1] + "\n"
        out.append('units = "imperial"\n')

    weather_cfg.write_text("".join(out), encoding="utf-8")
    log("[OK] - Set waybar-weather units to imperial")
