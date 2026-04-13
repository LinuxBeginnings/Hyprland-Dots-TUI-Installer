# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import re
import shutil
from pathlib import Path

from dots_tui.logic.copy_ops import copy_config_dir
from dots_tui.logic.models import InstallConfig, LogFn, PromptConfirmFn
from dots_tui.logic.path_safety import assert_safe_path
import dots_tui.utils as utils


def install_optional_app_configs(
    cfg: InstallConfig,
    *,
    staging_config_root: Path,
    target_config_root: Path,
    log: LogFn,
    prompt_confirm: PromptConfirmFn | None,
) -> None:
    """Install optional application configs (AGS and Quickshell).

    Handles overwrite prompts, legacy cleanup, and startup script patching.

    Args:
        cfg: Install configuration (enable_ags, enable_quickshell flags).
        staging_config_root: Path to the staged config tree.
        target_config_root: Target ~/.config directory.
        log: Logging callback.
        prompt_confirm: Callable for overwrite confirmation prompts, or None.
    """

    def _copytree(src: Path, dst: Path) -> None:
        assert_safe_path(dst)
        if dst.exists() and not dst.is_symlink():
            shutil.rmtree(dst)
        elif dst.is_symlink():
            dst.unlink(missing_ok=True)
        shutil.copytree(src, dst, symlinks=True)

    # AGS config copy/overwrite.
    if cfg.enable_ags and utils.which("ags"):
        src = staging_config_root / "ags"
        dst = target_config_root / "ags"
        if not src.is_dir():
            log("[ERROR] Missing source config/ags; skipping.")
        elif not dst.exists():
            _copytree(src, dst)
            log("[OK] - Installed ags config")
        else:
            msg = "Do you want to overwrite your existing ags config?"
            ok = False
            if prompt_confirm is not None:
                ok = prompt_confirm(msg, "Overwrite", "Skip", False)
            if ok:
                backup = copy_config_dir(
                    name="ags",
                    staging_config_root=staging_config_root,
                    target_config_root=target_config_root,
                )
                if backup is None:
                    if not dst.is_dir():
                        raise RuntimeError("Failed to install ags config")
                log("[OK] - Overwrote ags config")
            else:
                log("[NOTE] - Skipped overwriting ags config")

    # Quickshell config copy/overwrite + overview fixups.
    if cfg.enable_quickshell and utils.which("qs"):
        src = staging_config_root / "quickshell"
        dst = target_config_root / "quickshell"
        if not src.is_dir():
            log("[ERROR] Missing source config/quickshell; skipping.")
            return

        if dst.exists() and (dst / "shell.qml").exists():
            (dst / "shell.qml").unlink(missing_ok=True)
            log("[NOTE] Removed legacy quickshell shell.qml")

        if not dst.exists():
            _copytree(src, dst)
            (dst / "shell.qml").unlink(missing_ok=True)
            log("[OK] - Installed quickshell config")
        else:
            msg = "Do you want to overwrite your existing quickshell config?"
            ok = False
            if prompt_confirm is not None:
                ok = prompt_confirm(msg, "Overwrite", "Skip", True)
            if ok:
                # Backup existing then replace.
                backup = copy_config_dir(
                    name="quickshell",
                    staging_config_root=staging_config_root,
                    target_config_root=target_config_root,
                )
                _ = backup
                (dst / "shell.qml").unlink(missing_ok=True)
                if not dst.is_dir():
                    raise RuntimeError("Failed to install quickshell config")
                log("[OK] - Overwrote quickshell config")
            else:
                log("[NOTE] - Skipped overwriting quickshell config")

        # Ensure overview exists.
        overview_dst = dst / "overview"
        overview_src = src / "overview"
        if not overview_dst.exists() and overview_src.is_dir():
            try:
                _copytree(overview_src, overview_dst)
                log("[OK] - Installed quickshell overview")
            except Exception:
                pass

        # Rewrite legacy qs startup lines.
        startup = target_config_root / "hypr" / "configs" / "Startup_Apps.conf"
        if startup.is_file():
            txt = startup.read_text(encoding="utf-8", errors="replace").splitlines(True)
            out: list[str] = []
            changed = False
            for line in txt:
                if re.match(r"^\s*exec-once\s*=\s*qs(?:\s*&)?\s*$", line.strip()):
                    out.append("exec-once = qs -c overview  # Quickshell Overview\n")
                    changed = True
                else:
                    out.append(line)
            if changed:
                startup.write_text("".join(out), encoding="utf-8")
                log("[OK] - Updated Startup_Apps for Quickshell Overview")
