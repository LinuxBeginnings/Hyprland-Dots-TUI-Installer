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
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Callable

from dots_tui.logic.copy_ops import (
    copy_config_dir,
    copy_phase1_dir,
    copy_waybar_with_merge,
    install_file,
    restore_rofi_from_backup,
)
from dots_tui.logic.backup import backup_dir, cleanup_backups
from dots_tui.logic.models import (
    EnvironmentInfo,
    InstallConfig,
    InstallerPaths,
    InstallerState,
    LogFn,
    PromptConfirmFn,
    PromptInputFn,
    PromptPasswordFn,
    PromptReplaceFn,
)
from dots_tui.logic.restore import (
    restore_hypr_assets,
    restore_hypr_files,
    restore_user_configs,
    restore_user_scripts,
)
from dots_tui.logic.system import (
    detect_distro,
    detect_chassis,
    detect_nixos,
    detect_nvidia,
    detect_vm,
    get_installed_dotfiles_version,
    MIN_EXPRESS_VERSION,
    version_gte,
)
import dots_tui.utils as utils

from dots_tui.logic.path_safety import assert_safe_path, set_home_override
import dots_tui.logic.tweaks as tweaks
import dots_tui.logic.systemd_services as systemd_services
import dots_tui.logic.waybar_weather as waybar_weather_mod
import dots_tui.logic.wallpaper as wallpaper_mod
import dots_tui.logic.optional_apps as optional_apps_mod
import dots_tui.logic.user_config as user_config_mod
import dots_tui.logic.repo_ops as repo_ops_mod


def is_root() -> bool:
    return utils.is_root()


def which(cmd: str) -> str | None:
    return utils.which(cmd)


async def run_cmd(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    log: LogFn | None = None,
    input_text: str | None = None,
) -> utils.CmdResult:
    if input_text is None:
        return await utils.run_cmd(
            argv,
            cwd=cwd,
            env=env,
            log=log,
        )

    return await utils.run_cmd(
        argv,
        cwd=cwd,
        env=env,
        log=log,
        input_text=input_text,
    )


# ============================================================================
# Path Constants - Orchestrator-local config file paths
# ============================================================================

# Phase 1 config directories (prompt for replacement)
PHASE1_CONFIGS = ["fastfetch", "kitty", "rofi", "swaync"]

# Phase 2 config directories (no prompt, backup + replace)
PHASE2_CONFIGS = [
    "btop",
    "cava",
    "hypr",
    "Kvantum",
    "qt5ct",
    "qt6ct",
    "swappy",
    "wallust",
    "wlogout",
]


class InstallerOrchestrator:
    def __init__(self) -> None:
        self.repo_root = self._detect_repo_root()
        self.last_state: InstallerState | None = None
        self._sudo_warned = False

    def _detect_repo_root(self) -> Path:
        start = Path.cwd().resolve()
        for candidate in (start, *start.parents):
            if (candidate / "config").is_dir() and (candidate / "scripts").is_dir():
                return candidate

        # Support running from the TUI wrapper repository root where
        # Hyprland-Dots is vendored as a child directory.
        for child_name in ("Hyprland-Dots", "hyprland-dots"):
            child = start / child_name
            if (child / "config").is_dir() and (child / "scripts").is_dir():
                return child

        home = Path.home()
        for candidate in (home / "Hyprland-Dots", home / "hyprland-dots"):
            if (candidate / "config").is_dir() and (candidate / "scripts").is_dir():
                return candidate

        return start

    def _assert_repo_root(self) -> None:
        if not (self.repo_root / "config").is_dir():
            raise RuntimeError(f"Expected repo root with config/: {self.repo_root}")

    async def update_repo(
        self,
        *,
        log: LogFn,
        log_file: Path,
        set_step: Callable[[str, int | None], None],
    ) -> None:
        """Delegate to repo_ops_mod.update_repo."""
        await repo_ops_mod.update_repo(
            repo_root=self.repo_root,
            log=log,
            log_file=log_file,
            set_step=set_step,
        )

    async def download_repo(
        self,
        *,
        log: LogFn,
        log_file: Path,
        set_step: Callable[[str, int | None], None],
    ) -> None:
        """Delegate to repo_ops_mod.download_repo."""
        await repo_ops_mod.download_repo(
            log=log,
            log_file=log_file,
            set_step=set_step,
        )

    def _copy_logs_dir(self, *, sandbox_root: Path | None = None) -> Path:
        if sandbox_root is not None:
            d = sandbox_root / "Copy-Logs"
        else:
            d = self.repo_root / "Copy-Logs"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _log_file_path(self, prefix: str, *, sandbox_root: Path | None = None) -> Path:
        ts = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        if prefix == "update":
            return (
                self._copy_logs_dir(sandbox_root=sandbox_root) / f"update-{ts}_git.log"
            )
        if prefix == "download":
            return (
                self._copy_logs_dir(sandbox_root=sandbox_root)
                / f"download-{ts}_git.log"
            )
        return (
            self._copy_logs_dir(sandbox_root=sandbox_root)
            / f"install-{ts}_dotfiles.log"
        )

    def create_log_sink(
        self, *, prefix: str, ui_log: LogFn, sandbox_root: Path | None = None
    ) -> tuple[LogFn, Path]:
        """Return a log function that writes to UI + file.

        This is the core "tee -a" parity hook: any line written to the UI log
        should also be appended to the file log.
        """

        log_file = self._log_file_path(prefix, sandbox_root=sandbox_root)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.touch(exist_ok=True)

        def tee(message: str) -> None:
            ui_log(message)
            with log_file.open("a", encoding="utf-8") as lf:
                lf.write(message + "\n")

        return tee, log_file

    async def _run_sudo_cmd(
        self,
        argv: list[str],
        *,
        log: LogFn,
        prompt_password: PromptPasswordFn | None = None,
        description: str = "",
    ) -> bool:
        # 1. Try non-interactive sudo first
        full_cmd = ["sudo", "-n"] + argv
        result = await run_cmd(full_cmd, log=log)
        if result.returncode == 0:
            return True

        # Check if failure is due to missing password
        is_auth_fail = (
            "password is required" in result.output.lower() or result.returncode == 1
        )
        if not is_auth_fail:
            # Genuine failure not related to auth
            return False

        # 2. Try to get password if prompt function is provided
        if prompt_password is not None:
            # Only log warning once
            if not self._sudo_warned:
                log("[NOTE] Sudo authentication required for this step.")

            while True:
                pw = prompt_password("Enter sudo password to proceed (or Esc to skip):")
                if not pw:
                    break

                # 3. Authenticate session with sudo -v -S
                auth_cmd = ["sudo", "-v", "-S"]
                auth_res = await run_cmd(auth_cmd, input_text=pw + "\n", log=log)

                if auth_res.returncode == 0:
                    # Retry original command
                    retry_res = await run_cmd(full_cmd, log=log)
                    return retry_res.returncode == 0
                else:
                    log("[WARN] Authentication failed. Please try again.")

        # 4. Fallback: warn if not already warned
        if not self._sudo_warned:
            log(
                "[NOTE] Some system changes require passwordless sudo or a password."
                " Skipping this step."
            )
            self._sudo_warned = True

        if description:
            log(f"[NOTE] Skipped (auth failed): {description}")
        return False

    async def _pre_authenticate_sudo(
        self,
        *,
        log: LogFn,
        prompt_password: PromptPasswordFn | None = None,
    ) -> bool:
        """Pre-authenticate sudo to cache credentials before any prompts.

        Returns True if sudo is authenticated (or passwordless), False otherwise.
        """
        # Try non-interactive sudo first
        result = await run_cmd(["sudo", "-n", "true"], log=log)
        if result.returncode == 0:
            return True

        # Check if failure is due to missing password
        is_auth_fail = (
            "password is required" in result.output.lower() or result.returncode == 1
        )
        if not is_auth_fail:
            return False

        if prompt_password is None:
            log("[NOTE] Sudo authentication required for system changes.")
            return False

        log("[NOTE] Sudo authentication required. Please enter your password.")

        while True:
            pw = prompt_password("Enter sudo password (or Esc to skip):")
            if not pw:
                log("[NOTE] Sudo authentication skipped.")
                return False

            auth_res = await run_cmd(
                ["sudo", "-v", "-S"],
                input_text=pw + "\n",
                log=log,
            )

            if auth_res.returncode == 0:
                log("[OK] Sudo authentication successful.")
                return True
            else:
                log("[WARN] Authentication failed. Please try again.")

    async def run_install(
        self,
        config: InstallConfig,
        *,
        log: LogFn,
        log_file: Path,
        set_step: Callable[[str, int | None], None],
        prompt_replace: PromptReplaceFn | None = None,
        prompt_confirm: PromptConfirmFn | None = None,
        prompt_password: PromptPasswordFn | None = None,
        prompt_input: PromptInputFn | None = None,
    ) -> None:
        if is_root():
            raise RuntimeError(
                "This script should NOT be executed as root!! Exiting......."
            )

        self.repo_root = await repo_ops_mod.ensure_repo_root_for_install(
            repo_root=self.repo_root,
            log=log,
            set_step=set_step,
            dry_run=config.dry_run,
        )

        set_step("Preparing...", 5)

        # Read installed version from REAL config BEFORE sandbox redirect.
        real_home = Path.home()
        target_config_root = Path(
            os.environ.get("XDG_CONFIG_HOME", str(real_home / ".config"))
        )

        distro_id, distro_like = detect_distro()
        chassis = detect_chassis()
        installed_version = get_installed_dotfiles_version(target_config_root)
        installed_version_at_start = installed_version

        # Sandbox lifecycle for dry-run.
        sandbox: tempfile.TemporaryDirectory[str] | None = None
        sandbox_home: Path | None = None
        if config.dry_run:
            sandbox = tempfile.TemporaryDirectory(prefix="hyprdots-sandbox-")
            sandbox_home = Path(sandbox.name)
            target_config_root = sandbox_home / ".config"
            set_home_override(sandbox_home)
            log(f"[DRY-RUN] Sandbox: {sandbox_home}")

        # Pre-authenticate sudo before any prompts (SDDM operations need it)
        if not config.dry_run:
            await self._pre_authenticate_sudo(
                log=log,
                prompt_password=prompt_password,
            )
        else:
            log("[DRY-RUN] Skipped: sudo pre-auth")

        if not config.dry_run:
            res = await run_cmd(["xdg-user-dirs-update"], log=log)
            if res.returncode != 0:
                log(
                    f"[WARN] xdg-user-dirs-update failed (exit {res.returncode}); continuing"
                )
        else:
            log("[DRY-RUN] Skipped: xdg-user-dirs-update")

        try:
            with tempfile.TemporaryDirectory(prefix="hyprdots-stage-") as td:
                staging_root = Path(td)
                staging_config = staging_root / "config"
                staging_wallpapers = staging_root / "wallpapers"

                set_step("Staging files...", 10)
                shutil.copytree(
                    self.repo_root / "config", staging_config, symlinks=True
                )
                if (self.repo_root / "wallpapers").is_dir():
                    shutil.copytree(
                        self.repo_root / "wallpapers",
                        staging_wallpapers,
                        symlinks=True,
                    )

                set_step("Applying system tweaks...", 20)
                is_nvidia = detect_nvidia()
                is_vm = detect_vm()
                is_nixos = detect_nixos()
                if is_nvidia:
                    log("[INFO] Nvidia GPU detected; applying config tweaks")
                    tweaks.apply_nvidia_tweaks(staging_config)
                if is_vm:
                    log("[INFO] VM detected; applying config tweaks")
                    tweaks.apply_vm_tweaks(staging_config)
                if is_nixos:
                    log("[INFO] NixOS detected; applying config tweaks")
                    tweaks.apply_nixos_tweaks(staging_config)

                if (real_home / ".icons/Bibata-Modern-Ice/hyprcursors").is_dir():
                    log(
                        "[INFO] Bibata-Hyprcursor directory detected. Activating Hyprcursor...."
                    )
                    tweaks.apply_hyprcursor_tweaks(staging_config)

                await waybar_weather_mod.handle_waybar_weather_binary(
                    repo_root=self.repo_root,
                    log=log,
                    is_nixos=is_nixos,
                    distro_id=distro_id,
                    run_sudo_cmd=lambda argv, **kw: self._run_sudo_cmd(
                        argv, log=log, prompt_password=prompt_password, **kw
                    ),
                    dry_run=config.dry_run,
                )

                self.last_state = InstallerState(
                    run_mode=config.run_mode,
                    selections=config,
                    env=EnvironmentInfo(
                        distro_id=distro_id,
                        distro_like=distro_like,
                        chassis=chassis,
                        is_nvidia=is_nvidia,
                        is_vm=is_vm,
                        is_nixos=is_nixos,
                        installed_dotfiles_version=installed_version,
                    ),
                    paths=InstallerPaths(
                        repo_root=self.repo_root,
                        copy_logs_dir=self._copy_logs_dir(sandbox_root=sandbox_home),
                        log_file=log_file,
                        target_config_root=target_config_root,
                        staging_root=staging_root,
                    ),
                )

                if config.run_mode == "express":
                    if installed_version is None or not version_gte(
                        installed_version, MIN_EXPRESS_VERSION
                    ):
                        log(
                            f"[WARN] Express mode requires installed dotfiles v{MIN_EXPRESS_VERSION} or newer. Falling back to standard upgrade."
                        )
                        config = InstallConfig(
                            run_mode="upgrade",
                            resolution=config.resolution,
                            keyboard_layout=config.keyboard_layout,
                            clock_24h=config.clock_24h,
                            default_editor=config.default_editor,
                            download_wallpapers=config.download_wallpapers,
                            enable_asus=config.enable_asus,
                            enable_blueman=config.enable_blueman,
                            enable_ags=config.enable_ags,
                            enable_quickshell=config.enable_quickshell,
                            dry_run=config.dry_run,
                            default_wallpaper=config.default_wallpaper,
                        )

                        assert self.last_state is not None
                        self.last_state = InstallerState(
                            run_mode=config.run_mode,
                            selections=config,
                            env=self.last_state.env,
                            paths=self.last_state.paths,
                        )

                # Initial run-mode logging parity.
                log(f"Selected workflow: {config.run_mode}")
                if config.run_mode in {"upgrade", "express"}:
                    log("Upgrade mode enabled.")
                if config.run_mode == "express":
                    log(
                        "Express mode enabled. Optional restore prompts will be skipped."
                    )

                set_step("Applying user configuration...", 30)
                user_config_mod.apply_user_choices(config, staging_config, log)

                set_step("Copying configs (phase 1)...", 45)
                for name in PHASE1_CONFIGS:
                    log(f"[INFO] Installing {name}")

                    dst = target_config_root / name
                    if dst.exists() and prompt_replace is not None:
                        if not prompt_replace(name, dst):
                            log(f"[NOTE] - Skipping {name}")
                            continue

                    backup = None
                    backup = copy_phase1_dir(
                        name=name,
                        staging_config_root=staging_config,
                        target_config_root=target_config_root,
                        log=log,
                    )
                    if name == "rofi" and backup is not None:
                        restore_rofi_from_backup(
                            backup_dir=backup,
                            rofi_dir=target_config_root / "rofi",
                            log=log,
                        )

                set_step("Copying configs (waybar)...", 55)
                log("[INFO] Installing waybar")

                waybar_dst = target_config_root / "waybar"
                if waybar_dst.exists() and prompt_replace is not None:
                    if not prompt_replace("waybar", waybar_dst):
                        log("[NOTE] - Skipping waybar config replacement.")
                    else:
                        copy_waybar_with_merge(
                            staging_config_root=staging_config,
                            target_config_root=target_config_root,
                            log=log,
                        )
                else:
                    copy_waybar_with_merge(
                        staging_config_root=staging_config,
                        target_config_root=target_config_root,
                        log=log,
                    )

                set_step("Copying configs (phase 2)...", 70)
                hypr_backup: Path | None = None
                for name in PHASE2_CONFIGS:
                    log(f"[INFO] Installing {name}")
                    backup = None
                    backup = copy_config_dir(
                        name=name,
                        staging_config_root=staging_config,
                        target_config_root=target_config_root,
                    )
                    if name == "hypr" and backup is not None:
                        hypr_backup = backup

                weather_config_copied = waybar_weather_mod.handle_waybar_weather_config(
                    run_mode=config.run_mode,
                    staging_config_root=staging_config,
                    target_config_root=target_config_root,
                    log=log,
                )

                waybar_weather_mod.handle_waybar_weather_units(
                    run_mode=config.run_mode,
                    weather_units=config.weather_units,
                    weather_config_copied=weather_config_copied,
                    target_config_root=target_config_root,
                    log=log,
                )

                set_step("Installing terminal configs...", 78)
                ghostty_src = staging_config / "ghostty" / "ghostty.config"
                if ghostty_src.is_file():
                    ghostty_dir = target_config_root / "ghostty"
                    if ghostty_dir.exists():
                        ghostty_backup = backup_dir(ghostty_dir)
                        if ghostty_backup:
                            log(f"[NOTE] - Backed up ghostty to {ghostty_backup}")
                    install_file(
                        src=ghostty_src,
                        dst=target_config_root / "ghostty" / "config",
                        mode=0o644,
                    )
                    log("[OK] - Installed ghostty config")
                    wallust_conf = target_config_root / "ghostty" / "wallust.conf"
                    if wallust_conf.is_file():
                        txt = wallust_conf.read_text(encoding="utf-8", errors="replace")
                        txt = re.sub(
                            r"^(\s*palette\s*=\s*)([0-9]{1,2}):",
                            r"\1\2=",
                            txt,
                            flags=re.MULTILINE,
                        )
                        wallust_conf.write_text(txt, encoding="utf-8")
                wez_src = staging_config / "wezterm" / "wezterm.lua"
                if wez_src.is_file():
                    install_file(
                        src=wez_src,
                        dst=target_config_root / "wezterm" / "wezterm.lua",
                        mode=0o644,
                    )

                # Optional post-copy app configs (AGS / Quickshell).
                set_step("Installing optional app configs...", 80)
                optional_apps_mod.install_optional_app_configs(
                    config,
                    staging_config_root=staging_config,
                    target_config_root=target_config_root,
                    log=log,
                    prompt_confirm=prompt_confirm,
                )

                if config.run_mode in {"upgrade", "express"}:
                    set_step("Restoring previous configs...", 82)
                    # If no backup was created this run, look for existing backups
                    # (including legacy copy.sh format backups)
                    if hypr_backup is None:
                        from dots_tui.logic.backup import find_most_recent_backup

                        hypr_dir = target_config_root / "hypr"
                        hypr_backup = find_most_recent_backup(hypr_dir)

                        if hypr_backup is not None:
                            log(
                                f"[NOTE] Found existing backup from previous installation: {hypr_backup.name}"
                            )
                        else:
                            log(
                                "[NOTE] No hypr backup found for this run; skipping restore."
                            )

                    if hypr_backup is not None:
                        hypr_dir = target_config_root / "hypr"
                        express = config.run_mode == "express"
                        restore_hypr_assets(
                            backup_hypr_dir=hypr_backup,
                            hypr_dir=hypr_dir,
                            express=express,
                            log=log,
                        )
                        restore_user_configs(
                            backup_hypr_dir=hypr_backup,
                            hypr_dir=hypr_dir,
                            express=express,
                            prompt_confirm=prompt_confirm,
                            log=log,
                            old_version=installed_version_at_start,
                        )
                        restore_user_scripts(
                            backup_hypr_dir=hypr_backup,
                            hypr_dir=hypr_dir,
                            express=express,
                            prompt_confirm=prompt_confirm,
                            log=log,
                        )
                        restore_hypr_files(
                            backup_hypr_dir=hypr_backup,
                            hypr_dir=hypr_dir,
                            express=express,
                            prompt_confirm=prompt_confirm,
                            log=log,
                        )

                set_step("Installing wallpapers...", 85)
                await wallpaper_mod.install_wallpapers(
                    config,
                    staging_wallpapers,
                    log,
                    home_override=sandbox_home,
                )

                set_step("Finalizing...", 92)
                await self._finalize_post_copy(
                    config,
                    target_config_root,
                    log,
                    prompt_confirm=prompt_confirm,
                    prompt_password=prompt_password,
                    sandbox_home=sandbox_home,
                    staging_root=staging_root,
                    dry_run=config.dry_run,
                )

        finally:
            if sandbox is not None:
                set_home_override(None)
                sandbox.cleanup()
                log("[DRY-RUN] Complete — no changes made to real system")
                log("[DRY-RUN] Sandbox cleaned up")

        set_step("Complete.", 100)

    def _enforce_symlink_target(
        self,
        *,
        link_path: Path,
        canonical_target: Path,
        label: str,
        log: LogFn,
    ) -> None:
        """Ensure link_path points to canonical_target with warn-only fallbacks.

        If canonical_target is missing, this method leaves link_path untouched and
        emits a warning. Recoverable filesystem errors are logged and do not raise.
        """

        if not canonical_target.exists():
            log(
                "[WARN] Skipping Waybar "
                f"{label} symlink enforcement for {link_path}: "
                f"canonical target missing at {canonical_target}"
            )
            return

        canonical_resolved = canonical_target.resolve()
        if link_path.is_symlink():
            try:
                if link_path.resolve(strict=True) == canonical_resolved:
                    return
            except FileNotFoundError:
                pass
            except OSError as exc:
                log(
                    "[WARN] Failed to inspect Waybar "
                    f"{label} symlink at {link_path}: {exc}"
                )

        try:
            if link_path.is_symlink() or link_path.is_file():
                link_path.unlink(missing_ok=True)
            elif link_path.exists():
                log(
                    "[WARN] Skipping Waybar "
                    f"{label} symlink enforcement for {link_path}: "
                    "destination is not a file or symlink"
                )
                return

            link_path.symlink_to(canonical_target)
        except OSError as exc:
            log(
                f"[WARN] Failed to enforce Waybar {label} symlink at {link_path}: {exc}"
            )

    async def _finalize_post_copy(
        self,
        cfg: InstallConfig,
        target_config_root: Path,
        log: LogFn,
        *,
        prompt_confirm: PromptConfirmFn | None,
        prompt_password: PromptPasswordFn | None = None,
        sandbox_home: Path | None = None,
        staging_root: Path | None = None,
        dry_run: bool = False,
    ) -> None:
        hypr_dir = target_config_root / "hypr"
        if hypr_dir.is_dir():
            scripts_dir = hypr_dir / "scripts"
            userscripts_dir = hypr_dir / "UserScripts"
            for p in [scripts_dir, userscripts_dir]:
                if p.is_dir():
                    for child in p.iterdir():
                        try:
                            mode = child.stat().st_mode
                            child.chmod(mode | 0o111)
                        except Exception:
                            pass

            init_boot = hypr_dir / "initial-boot.sh"
            if init_boot.is_file():
                try:
                    init_boot.chmod(init_boot.stat().st_mode | 0o111)
                except Exception:
                    pass

        # Setup systemd services
        if staging_root is not None:
            await systemd_services.setup_systemd_services(
                staging_root=staging_root,
                target_config_root=target_config_root,
                log=log,
                dry_run=dry_run,
            )

        # Rofi themes local-share symlink logic.
        rofi_dir = target_config_root / "rofi"
        rofi_themes = rofi_dir / "themes"
        if sandbox_home is not None:
            data_home = sandbox_home / ".local/share"
        else:
            data_home = Path(
                os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local/share"))
            )
        rofi_share = data_home / "rofi" / "themes"
        try:
            rofi_share.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        dummy = rofi_themes / "dummy.rasi"
        created_dummy = False
        if rofi_themes.is_dir() and rofi_share.is_dir():
            try:
                if not any(rofi_themes.iterdir()):
                    dummy.write_text("/* Dummy Rofi theme */\n", encoding="utf-8")
                    created_dummy = True
                for item in rofi_themes.iterdir():
                    dst = rofi_share / item.name
                    try:
                        if dst.exists() or dst.is_symlink():
                            dst.unlink(missing_ok=True)
                        dst.symlink_to(item)
                    except Exception:
                        pass
            finally:
                if created_dummy:
                    try:
                        dummy.unlink(missing_ok=True)
                    except Exception:
                        pass

        waybar_dir = target_config_root / "waybar"
        chassis = detect_chassis()
        if waybar_dir.is_dir():
            config_target = (
                waybar_dir
                / "configs"
                / ("TOP-Default" if chassis == "desktop" else "TOP-Default-Laptop")
            )
            style_target = waybar_dir / "style" / "Extra-Prismatic-Glow.css"
            self._enforce_symlink_target(
                link_path=waybar_dir / "config",
                canonical_target=config_target,
                label="config",
                log=log,
            )
            self._enforce_symlink_target(
                link_path=waybar_dir / "style.css",
                canonical_target=style_target,
                label="style.css",
                log=log,
            )

            # Remove inappropriate waybar configs (shell behavior).
            config_remove = " Laptop" if chassis == "desktop" else ""
            to_remove = [
                f"[TOP] Default{config_remove}",
                f"[BOT] Default{config_remove}",
                f"[TOP] Default{config_remove} (old v1)",
                f"[TOP] Default{config_remove} (old v2)",
                f"[TOP] Default{config_remove} (old v3)",
                f"[TOP] Default{config_remove} (old v4)",
            ]
            for name in to_remove:
                p = waybar_dir / "configs" / name
                try:
                    if p.is_dir() and not p.is_symlink():
                        assert_safe_path(p)
                        shutil.rmtree(p)
                    else:
                        p.unlink(missing_ok=True)
                except Exception:
                    pass

        # Initialize default desktop wallpaper if not already set
        wall_effects_dir = hypr_dir / "wallpaper_effects"
        wallpaper_current = wall_effects_dir / ".wallpaper_current"
        if not wallpaper_current.exists():
            default_filename = cfg.default_wallpaper
            pictures_dir = await wallpaper_mod.detect_pictures_dir(
                log, home_override=sandbox_home
            )
            default_img = pictures_dir / "wallpapers" / default_filename
            if not default_img.exists():
                default_img = self.repo_root / "wallpapers" / default_filename
            if default_img.exists():
                wall_effects_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(default_img, wallpaper_current)
                log("[OK] Default desktop wallpaper initialized.")
            else:
                log(
                    f"[WARN] Default wallpaper '{default_filename}' not found; skipping initialization"
                )

        # SDDM wallpaper
        if not cfg.dry_run:
            sddm_theme = Path("/usr/share/sddm/themes/simple_sddm_2")
            if sddm_theme.is_dir():
                if cfg.apply_sddm_wallpaper:
                    wallpaper_src = (
                        hypr_dir / "wallpaper_effects" / ".wallpaper_current"
                    )
                    dest = sddm_theme / "Backgrounds" / "default"
                    if wallpaper_src.exists():
                        success = await self._run_sudo_cmd(
                            ["cp", "-r", str(wallpaper_src), str(dest)],
                            log=log,
                            description="apply wallpaper as SDDM background",
                            prompt_password=prompt_password,
                        )
                        if success:
                            log(
                                "[NOTE] Current wallpaper applied as default SDDM background"
                            )
                    else:
                        log("[WARN] SDDM wallpaper source not found; skipping")
                else:
                    log("[NOTE] SDDM wallpaper disabled; skipping.")

            # SDDM clock format edits
            if not cfg.clock_24h and cfg.run_mode != "express":
                for theme_name in ["simple_sddm_2", "simple-sddm"]:
                    theme_conf = Path(f"/usr/share/sddm/themes/{theme_name}/theme.conf")
                    if not theme_conf.is_file():
                        continue
                    await self._run_sudo_cmd(
                        [
                            "sed",
                            "-i",
                            's|^## HourFormat="hh:mm AP"|HourFormat="hh:mm AP"|',
                            str(theme_conf),
                        ],
                        log=log,
                        description=f"update 12h clock format in {theme_name}",
                        prompt_password=prompt_password,
                    )
                    await self._run_sudo_cmd(
                        [
                            "sed",
                            "-i",
                            's|^HourFormat="HH:mm"|## HourFormat="HH:mm"|',
                            str(theme_conf),
                        ],
                        log=log,
                        description=f"disable 24h clock format in {theme_name}",
                        prompt_password=prompt_password,
                    )

                # sequoia_2
                theme_conf = Path("/usr/share/sddm/themes/sequoia_2/theme.conf")
                if theme_conf.is_file():
                    await self._run_sudo_cmd(
                        [
                            "sed",
                            "-i",
                            's|^clockFormat="HH:mm"|## clockFormat="HH:mm"|',
                            str(theme_conf),
                        ],
                        log=log,
                        description="disable 24h clock format in sequoia_2",
                        prompt_password=prompt_password,
                    )
                    # Ensure the 12h clock format line exists; avoid shell usage.
                    has_12h = await run_cmd(
                        [
                            "sudo",
                            "-n",
                            "grep",
                            "-q",
                            'clockFormat="hh:mm AP"',
                            str(theme_conf),
                        ],
                        log=log,
                    )
                    if has_12h.returncode != 0:
                        await self._run_sudo_cmd(
                            [
                                "sed",
                                "-i",
                                '/^## clockFormat="HH:mm"/a clockFormat="hh:mm AP"',
                                str(theme_conf),
                            ],
                            log=log,
                            description="add 12h clock format in sequoia_2",
                            prompt_password=prompt_password,
                        )
            elif not cfg.clock_24h:
                log("[NOTE] Express mode: skipping SDDM 12h clock edits.")
        else:
            log("[DRY-RUN] Skipped: SDDM sudo operations")

        # Backup cleanup (express auto, otherwise prompt).
        cleanup_backups(
            mode=("auto" if cfg.run_mode == "express" else "prompt"),
            log=log,
            prompt_confirm=prompt_confirm,
            config_root=target_config_root,
        )

        # Initialize wallust to avoid config error on hyprland.
        if not cfg.dry_run:
            wallpaper_src = hypr_dir / "wallpaper_effects" / ".wallpaper_current"
            if which("wallust") and wallpaper_src.exists():
                _ = await run_cmd(["wallust", "run", "-s", str(wallpaper_src)], log=log)
        else:
            log("[DRY-RUN] Skipped: wallust run")
