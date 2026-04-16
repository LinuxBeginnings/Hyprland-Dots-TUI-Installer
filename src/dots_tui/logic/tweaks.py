# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path

# ============================================================================
# Path Constants - Hyprland config file paths (relative to staging_config)
# ============================================================================
HYPR_CONFIGS_DIR = Path("hypr/configs")
HYPR_ENV_VARS = HYPR_CONFIGS_DIR / "ENVariables.conf"
HYPR_SYSTEM_SETTINGS = HYPR_CONFIGS_DIR / "SystemSettings.conf"
HYPR_STARTUP_APPS = HYPR_CONFIGS_DIR / "Startup_Apps.conf"
HYPR_STARTUP_DISABLE = HYPR_CONFIGS_DIR / "Startup_Apps.disable"
HYPR_MONITORS = Path("hypr/monitors.conf")


def apply_nvidia_tweaks(staging_config: Path) -> None:
    """Uncomment Nvidia env vars and disable hardware cursors in staging config.

    Operates only on files under staging_config — never touches live ~/.config.

    Args:
        staging_config: Path to the staged config tree.
    """
    env_file = staging_config / HYPR_ENV_VARS
    sys_file = staging_config / HYPR_SYSTEM_SETTINGS

    if env_file.is_file():
        text = env_file.read_text(encoding="utf-8", errors="replace").splitlines(True)
        rules = [
            "env = LIBVA_DRIVER_NAME,nvidia",
            "env = __GLX_VENDOR_LIBRARY_NAME,nvidia",
            "env = NVD_BACKEND,direct",
            "env = GSK_RENDERER,ngl",
        ]
        out: list[str] = []
        for line in text:
            stripped = line.lstrip("#")
            if any(r in stripped for r in rules):
                out.append(stripped)
            else:
                out.append(line)
        env_file.write_text("".join(out), encoding="utf-8")

    if sys_file.is_file():
        txt = sys_file.read_text(encoding="utf-8", errors="replace")
        txt = txt.replace("no_hardware_cursors = 2", "no_hardware_cursors = 1")
        sys_file.write_text(txt, encoding="utf-8")


def apply_vm_tweaks(staging_config: Path) -> None:
    """Enable software renderer env var, disable hardware cursors, uncomment VM monitor line.

    Operates only on files under staging_config — never touches live ~/.config.

    Args:
        staging_config: Path to the staged config tree.
    """
    env_file = staging_config / HYPR_ENV_VARS
    sys_file = staging_config / HYPR_SYSTEM_SETTINGS
    mon_file = staging_config / HYPR_MONITORS

    if sys_file.is_file():
        txt = sys_file.read_text(encoding="utf-8", errors="replace")
        txt = txt.replace("no_hardware_cursors = 2", "no_hardware_cursors = 1")
        sys_file.write_text(txt, encoding="utf-8")

    if env_file.is_file():
        txt = env_file.read_text(encoding="utf-8", errors="replace")
        txt = txt.replace(
            "#env = WLR_RENDERER_ALLOW_SOFTWARE,1",
            "env = WLR_RENDERER_ALLOW_SOFTWARE,1",
        )
        env_file.write_text(txt, encoding="utf-8")

    if mon_file.is_file():
        txt = mon_file.read_text(encoding="utf-8", errors="replace")
        txt = txt.replace(
            "#monitor = Virtual-1, 1920x1080@60,auto,1",
            "monitor = Virtual-1, 1920x1080@60,auto,1",
        )
        mon_file.write_text(txt, encoding="utf-8")


def apply_nixos_tweaks(staging_config: Path) -> None:
    """Append NixOS polkit exec-once line and disable default polkit startup.

    Operates only on files under staging_config — never touches live ~/.config.

    Args:
        staging_config: Path to the staged config tree.
    """
    overlay = staging_config / HYPR_STARTUP_APPS
    disable = staging_config / HYPR_STARTUP_DISABLE
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.touch(exist_ok=True)
    disable.touch(exist_ok=True)

    line = "exec-once = $scriptsDir/Polkit-NixOS.sh\n"
    if line not in overlay.read_text(encoding="utf-8", errors="replace"):
        with overlay.open("a", encoding="utf-8") as fh:
            fh.write(line)

    dline = "$scriptsDir/Polkit.sh\n"
    if dline not in disable.read_text(encoding="utf-8", errors="replace"):
        with disable.open("a", encoding="utf-8") as fh:
            fh.write(dline)


def apply_hyprcursor_tweaks(staging_config: Path) -> None:
    """Uncomment HYPRCURSOR_THEME and HYPRCURSOR_SIZE env vars in staging config.

    Operates only on files under staging_config — never touches live ~/.config.

    Args:
        staging_config: Path to the staged config tree.
    """
    env_file = staging_config / HYPR_ENV_VARS
    if not env_file.is_file():
        return
    txt = env_file.read_text(encoding="utf-8", errors="replace")
    txt = txt.replace(
        "#env = HYPRCURSOR_THEME,Bibata-Modern-Ice",
        "env = HYPRCURSOR_THEME,Bibata-Modern-Ice",
    )
    txt = txt.replace("#env = HYPRCURSOR_SIZE,24", "env = HYPRCURSOR_SIZE,24")
    env_file.write_text(txt, encoding="utf-8")
