# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from dots_tui.logic.dedupe import cleanup_duplicate_userconfigs
from dots_tui.logic.models import LogFn
from dots_tui.logic.system import get_installed_dotfiles_version
import dots_tui.utils as utils

# ============================================================================
# Constants
# ============================================================================
DOTFILES_REPO_URL = "https://github.com/LinuxBeginnings/Hyprland-Dots"
DOTFILES_REPO_DIRNAME = "Hyprland-Dots"


async def ensure_repo_root_for_install(
    *,
    repo_root: Path,
    log: LogFn,
    set_step: Callable[[str, int | None], None],
    dry_run: bool,
) -> Path:
    """Ensure Hyprland-Dots source is available, cloning if needed.

    Args:
        repo_root: Current candidate repo root path.
        log: Logging callback.
        set_step: Progress step callback.
        dry_run: If True, skip auto-clone (raise instead).

    Returns:
        The resolved repo root path to use (may differ from input if
        cloned or found in home directory).

    Raises:
        RuntimeError: If sources are missing and cannot be auto-fetched.
    """
    if (repo_root / "config").is_dir() and (repo_root / "scripts").is_dir():
        return repo_root

    home_repo = Path.home() / DOTFILES_REPO_DIRNAME
    if (home_repo / "config").is_dir() and (home_repo / "scripts").is_dir():
        log(f"[NOTE] Using dotfiles repo at {home_repo}")
        return home_repo

    if dry_run:
        raise RuntimeError(
            "Hyprland-Dots sources are not available for dry-run. "
            "Use 'Download Repo' first or clone Hyprland-Dots to ~/Hyprland-Dots."
        )

    if not utils.which("git"):
        raise RuntimeError(
            "Hyprland-Dots sources are missing and git is unavailable. "
            "Use 'Download Repo' first or clone Hyprland-Dots to ~/Hyprland-Dots."
        )

    if home_repo.exists() and not home_repo.is_dir():
        raise RuntimeError(
            f"Cannot bootstrap Hyprland-Dots: non-directory path exists at {home_repo}"
        )

    set_step("Bootstrapping Hyprland-Dots source...", 8)
    log(f"[INFO] Hyprland-Dots source not found. Attempting to clone into {home_repo}")

    if not home_repo.exists():
        clean_env = os.environ.copy()
        clean_env.pop("LD_LIBRARY_PATH", None)
        clone = await utils.run_cmd(
            ["git", "clone", "--depth", "1", DOTFILES_REPO_URL, str(home_repo)],
            log=log,
            env=clean_env,
        )
        if clone.returncode != 0:
            raise RuntimeError(
                "Failed to fetch Hyprland-Dots source automatically. "
                "Use 'Download Repo' from the menu and retry install."
            )

    if not (home_repo / "config").is_dir() or not (home_repo / "scripts").is_dir():
        raise RuntimeError(
            f"Hyprland-Dots source is incomplete at {home_repo}; expected config/ and scripts/."
        )

    log(f"[OK] Hyprland-Dots source ready at {home_repo}")
    return home_repo


async def update_repo(
    *,
    repo_root: Path,
    log: LogFn,
    log_file: Path,
    set_step: Callable[[str, int | None], None],
) -> None:
    """Update the Hyprland-Dots repository via git pull.

    Args:
        repo_root: Path to the Hyprland-Dots repository root.
        log: Logging callback.
        log_file: Path to the log file for this operation.
        set_step: Progress step callback.

    Raises:
        RuntimeError: If repo_root is not a valid Hyprland-Dots directory,
            git is unavailable, or git pull fails.
    """
    if not (repo_root / "config").is_dir():
        raise RuntimeError(f"Expected repo root with config/: {repo_root}")

    expected_names = {"Hyprland-Dots", "hyprland-dots"}
    if repo_root.name not in expected_names:
        raise RuntimeError(
            "This helper must be run from Hyprland-Dots or hyprland-dots directory. "
            f"Current: {repo_root}"
        )
    set_step("Starting repository update...", 5)
    log("[INFO] Starting repository update...")

    set_step("Checking git repo...", 10)
    if not utils.which("git"):
        raise RuntimeError("git not found")

    head_before_res = await utils.run_cmd(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        log=log,
    )
    head_before = (
        head_before_res.output.strip() if head_before_res.returncode == 0 else "unknown"
    )

    set_step("Checking working tree...", 15)
    log("[INFO] Checking working tree...")
    diff1 = await utils.run_cmd(["git", "diff", "--quiet"], cwd=repo_root, log=log)
    diff2 = await utils.run_cmd(
        ["git", "diff", "--cached", "--quiet"], cwd=repo_root, log=log
    )

    stash_msg = "No local changes; no stash created."
    if diff1.returncode == 0 and diff2.returncode == 0:
        log(f"[NOTE] {stash_msg}")
    else:
        set_step("Stashing local changes...", 25)
        log("[INFO] Stashing local changes (tracked + untracked)...")
        stash_res = await utils.run_cmd(
            ["git", "stash", "push", "-u"], cwd=repo_root, log=log
        )
        if stash_res.returncode != 0:
            raise RuntimeError("git stash failed")
        first = (stash_res.output.splitlines() or [""])[0]
        stash_msg = f"Created stash: {first}" if first else "Created stash."
        log(f"[OK] {stash_msg}")

    set_step("Pulling latest changes...", 60)
    log("[INFO] Pulling latest changes...")
    res = await utils.run_cmd(["git", "pull", "--ff-only"], cwd=repo_root, log=log)
    pull_status = res.returncode
    if pull_status == 0:
        log("[OK] Repository updated successfully.")
    else:
        log(f"[ERROR] git pull failed (exit {pull_status}).")

    head_after_res = await utils.run_cmd(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=repo_root,
        log=log,
    )
    head_after = (
        head_after_res.output.strip() if head_after_res.returncode == 0 else "unknown"
    )

    log("----------------------------------------")
    log("Summary:")
    log(f"  Repo        : {repo_root}")
    log(f"  Log file    : {log_file}")
    log(f"  HEAD before : {head_before}")
    log(f"  HEAD after  : {head_after}")
    log(f"  Stash       : {stash_msg}")
    log(f"  Pull status : {'success' if pull_status == 0 else 'failure'}")
    log("----------------------------------------")

    if pull_status != 0:
        raise RuntimeError(f"git pull failed (exit {pull_status})")

    installed_version = get_installed_dotfiles_version()
    if installed_version:
        log(
            f"[INFO] Checking for duplicate UserConfigs entries after repo update (detected v{installed_version})..."
        )
        cleanup_duplicate_userconfigs(installed_version, log)
    else:
        log(
            "[NOTE] Skipping UserConfigs duplicate cleanup; installed version could not be detected."
        )

    set_step("Update complete.", 100)


async def download_repo(
    *,
    log: LogFn,
    log_file: Path,
    set_step: Callable[[str, int | None], None],
) -> None:
    """Clone the Hyprland-Dots repository to ~/Hyprland-Dots.

    Args:
        log: Logging callback.
        log_file: Path to the log file for this operation.
        set_step: Progress step callback.

    Raises:
        RuntimeError: If git is unavailable, destination exists, or clone fails.
    """
    set_step("Starting repository download...", 5)
    log("[INFO] Starting repository download...")

    set_step("Checking git availability...", 15)
    if not utils.which("git"):
        raise RuntimeError("git not found")

    target = Path.home() / DOTFILES_REPO_DIRNAME

    set_step("Checking destination...", 25)
    if target.exists():
        raise RuntimeError(
            f"Destination already exists: {target}. "
            "Use Update Repo or remove the directory first."
        )

    set_step("Cloning Hyprland-Dots...", 55)
    clean_env = os.environ.copy()
    clean_env.pop("LD_LIBRARY_PATH", None)
    clone_res = await utils.run_cmd(
        ["git", "clone", "--depth", "1", DOTFILES_REPO_URL, str(target)],
        log=log,
        env=clean_env,
    )
    if clone_res.returncode != 0:
        raise RuntimeError(f"git clone failed (exit {clone_res.returncode})")

    set_step("Verifying clone...", 85)
    head_res = await utils.run_cmd(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=target,
        log=log,
    )
    head = head_res.output.strip() if head_res.returncode == 0 else "unknown"

    log("----------------------------------------")
    log("Summary:")
    log(f"  Repo URL   : {DOTFILES_REPO_URL}")
    log(f"  Target dir : {target}")
    log(f"  Log file   : {log_file}")
    log(f"  HEAD       : {head}")
    log("----------------------------------------")

    set_step("Download complete.", 100)
