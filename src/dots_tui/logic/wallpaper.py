# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from dots_tui.logic.models import InstallConfig, LogFn
from dots_tui.logic.path_safety import assert_safe_path
import dots_tui.utils as utils


async def detect_pictures_dir(
    log: LogFn,
    *,
    home_override: Path | None = None,
) -> Path:
    """Detect the XDG Pictures directory.

    Queries xdg-user-dir, falls back to $XDG_PICTURES_DIR, then ~/Pictures.

    Args:
        log: Logging callback.
        home_override: If set, immediately returns home_override / "Pictures".

    Returns:
        Path to the Pictures directory.
    """
    if home_override is not None:
        return home_override / "Pictures"
    if utils.which("xdg-user-dir"):
        res = await utils.run_cmd(["xdg-user-dir", "PICTURES"], log=log)
        if res.returncode == 0:
            raw = (res.output or "").strip().splitlines()[-1].strip()
            if raw:
                p = Path(raw).expanduser()
                if p.is_absolute():
                    return p

    return Path(os.environ.get("XDG_PICTURES_DIR", str(Path.home() / "Pictures")))


async def install_wallpapers(
    cfg: InstallConfig,
    staging_wallpapers: Path,
    log: LogFn,
    *,
    home_override: Path | None = None,
) -> None:
    """Install bundled wallpapers and optionally download Wallpaper-Bank.

    Copies staging wallpapers to <Pictures>/wallpapers/. If cfg.download_wallpapers
    is True and run_mode is not "express", also git-clones Wallpaper-Bank.

    Args:
        cfg: Install configuration.
        staging_wallpapers: Path to staging wallpapers directory.
        log: Logging callback.
        home_override: If set, uses this as the home directory root.
    """
    pictures_dir = await detect_pictures_dir(log, home_override=home_override)
    target = pictures_dir / "wallpapers"
    assert_safe_path(target)
    target.mkdir(parents=True, exist_ok=True)

    if staging_wallpapers.is_dir():
        for item in staging_wallpapers.iterdir():
            dst = target / item.name
            if item.is_dir():
                if dst.exists():
                    assert_safe_path(dst)
                    shutil.rmtree(dst)
                shutil.copytree(item, dst, symlinks=True)
            else:
                shutil.copy2(item, dst)
        log("[OK] Wallpapers copied.")

    if cfg.run_mode == "express":
        if cfg.download_wallpapers:
            log("[NOTE] Express mode: skipping additional wallpapers download.")
        return

    if cfg.download_wallpapers:
        log(
            "[NOTE] Disclaimer: additional wallpapers are AI generated and may contain artifacts."
        )
        log("[NOTE] Download size is ~1GB.")
        if not utils.which("git"):
            log("[WARN] git not found; cannot download Wallpaper-Bank")
            return

        with tempfile.TemporaryDirectory(prefix="hyprdots-walls-") as td:
            tmp = Path(td)
            res = await utils.run_cmd(
                [
                    "git",
                    "clone",
                    "https://github.com/LinuxBeginnings/Wallpaper-Bank.git",
                ],
                cwd=tmp,
                log=log,
            )
            if res.returncode != 0:
                log("[ERROR] Wallpaper-Bank clone failed")
                return

            bank = tmp / "Wallpaper-Bank" / "wallpapers"
            if bank.is_dir():
                for item in bank.iterdir():
                    dst = target / item.name
                    if item.is_dir():
                        if dst.exists():
                            assert_safe_path(dst)
                            shutil.rmtree(dst)
                        shutil.copytree(item, dst, symlinks=True)
                    else:
                        shutil.copy2(item, dst)
                log("[OK] Additional wallpapers copied.")
