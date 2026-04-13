# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

from dots_tui.logic.models import LogFn
import dots_tui.utils as utils

# ============================================================================
# Constants
# ============================================================================

SYSTEMD_SERVICES: list[str] = ["hyprpolkitagent"]
SYSTEMD_CONFLICT_PATTERNS: dict[str, list[str]] = {
    "hyprpolkitagent": [
        "xfce-polkit",
        "polkit-gnome-authentication-agent-1",
        "polkit-kde-authentication-agent-1",
        "hyprpolkitagent",
    ]
}


async def setup_systemd_services(
    *,
    staging_root: Path,
    target_config_root: Path,
    log: LogFn,
    dry_run: bool,
) -> None:
    """Copy systemd user service overrides and enable/start services.

    Implements feature parity with copy.sh lines 643-662:
    - Copies config/systemd/ directory tree to ~/.config/systemd/
    - Reloads systemd user daemon
    - Enables and starts services listed in SYSTEMD_SERVICES (if no conflicts)

    Args:
        staging_root: Path to staged dotfiles (repo_root or sandbox staging area)
        target_config_root: Target ~/.config directory (real or sandbox)
        log: Logging function for user-visible messages
        dry_run: If True, log operations without executing systemctl commands

    Returns:
        None (all errors are logged and gracefully handled)

    Side Effects:
        - Creates/modifies files under target_config_root/systemd/
        - Calls systemctl --user daemon-reload (unless systemctl missing or dry_run)
        - Calls systemctl --user enable/start <service> (conditionally)

    Error Handling:
        - Missing systemctl: logs NOTE, skips all systemd operations
        - Service unit file missing: logs NOTE, skips enable/start for that service
        - Conflicting process: logs NOTE, skips enable/start for that service
        - systemctl command failure: logs WARN, continues (non-fatal)
    """
    # STEP 1: Copy systemd directory tree
    systemd_src = staging_root / "config/systemd"
    systemd_dest = target_config_root / "systemd"

    if not systemd_src.exists():
        log("[NOTE] No systemd directory in dotfiles; skipping service setup")
        return

    log("[INFO] Copying systemd service configurations...")
    try:
        systemd_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(systemd_src, systemd_dest, dirs_exist_ok=True)
        log(f"[OK] Copied systemd configs to {systemd_dest}")
    except Exception as e:
        log(f"[WARN] Failed to copy systemd configs: {e}")
        return  # Cannot proceed without service files

    # STEP 2: Check systemctl availability
    if not utils.which("systemctl"):
        log("[NOTE] systemctl not found; skipping systemd service installation")
        return

    # STEP 3: Daemon reload
    log("[INFO] Reloading systemd user daemon...")
    reload_ok = await _systemctl_daemon_reload(log=log, dry_run=dry_run)
    if not reload_ok:
        log("[WARN] systemctl daemon-reload failed; services may not be recognized")
        # Continue anyway (service files are copied; user can reload manually)

    # STEP 4: Process each service
    for service_name in SYSTEMD_SERVICES:
        log(f"[INFO] Processing service: {service_name}")

        # 4a. Check if service unit file exists
        exists = await _check_service_exists(service_name, log=log, dry_run=dry_run)
        if not exists:
            log(
                f"[NOTE] Service unit file '{service_name}.service' not found; skipping"
            )
            continue

        # 4b. Check for conflicting processes
        conflict_patterns = SYSTEMD_CONFLICT_PATTERNS.get(service_name, [])
        if conflict_patterns:
            has_conflict = await _check_process_conflict(
                conflict_patterns, log=log, dry_run=dry_run
            )
            if has_conflict:
                log(
                    f"[NOTE] Conflicting process already running for {service_name}; skipping enable/start"
                )
                continue

        # 4c. Enable and start service
        log(f"[INFO] Enabling and starting {service_name}...")
        enable_ok, start_ok = await _systemctl_enable_start(
            service_name, log=log, dry_run=dry_run
        )

        if enable_ok and start_ok:
            log(f"[OK] Service {service_name} enabled and started")
        elif enable_ok:
            log(f"[WARN] Service {service_name} enabled but failed to start")
        else:
            log(f"[WARN] Failed to enable service {service_name}")


async def _systemctl_daemon_reload(
    *,
    log: LogFn,
    dry_run: bool,
) -> bool:
    """Reload systemd user daemon to pick up new/modified service files."""
    if dry_run:
        log("[DRY-RUN] Would run: systemctl --user daemon-reload")
        return True

    result = await utils.run_cmd(
        ["systemctl", "--user", "daemon-reload"],
        log=log,
    )
    return result.returncode == 0


async def _check_service_exists(
    service_name: str,
    *,
    log: LogFn,
    dry_run: bool,
) -> bool:
    """Check if a systemd user service unit file is available."""
    if dry_run:
        log(f"[DRY-RUN] Would check if {service_name}.service exists")
        return False

    result = await utils.run_cmd(
        ["systemctl", "--user", "list-unit-files"],
        log=None,
    )

    if result.returncode != 0:
        return False

    # Match pattern: ^hyprpolkitagent\.service\s+
    pattern = re.compile(rf"^{re.escape(service_name)}\.service\s+", re.MULTILINE)
    return bool(pattern.search(result.output))


async def _check_process_conflict(
    patterns: list[str],
    *,
    log: LogFn,
    dry_run: bool,
) -> bool:
    """Check if any conflicting processes are running."""
    if dry_run:
        log(f"[DRY-RUN] Would check for conflicting processes: {patterns}")
        return False

    if not utils.which("pgrep"):
        log("[NOTE] pgrep not found; skipping conflict check")
        return False

    uid = os.getuid()
    # Build alternation pattern: xfce-polkit|polkit-gnome-...|hyprpolkitagent
    combined_pattern = "|".join(patterns)

    result = await utils.run_cmd(
        ["pgrep", "-u", str(uid), "-f", combined_pattern],
        log=None,
    )

    # pgrep returns 0 if match found, 1 if no match, >1 if error
    if result.returncode == 0:
        log(f"[NOTE] Found running process matching: {patterns}")
        return True

    return False


async def _systemctl_enable_start(
    service_name: str,
    *,
    log: LogFn,
    dry_run: bool,
) -> tuple[bool, bool]:
    """Enable and start a systemd user service."""
    if dry_run:
        log(f"[DRY-RUN] Would run: systemctl --user enable {service_name}")
        log(f"[DRY-RUN] Would run: systemctl --user start {service_name}")
        return (True, True)

    # Enable
    enable_result = await utils.run_cmd(
        ["systemctl", "--user", "enable", service_name],
        log=log,
    )
    enable_ok = enable_result.returncode == 0

    # Start (run regardless of enable result)
    start_result = await utils.run_cmd(
        ["systemctl", "--user", "start", service_name],
        log=log,
    )
    start_ok = start_result.returncode == 0

    return (enable_ok, start_ok)
