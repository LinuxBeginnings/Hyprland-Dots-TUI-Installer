# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

import re
from pathlib import Path

from dots_tui.logic.models import InstallConfig, LogFn
from dots_tui.logic.system import replace_kb_layout
import dots_tui.utils as utils

# ============================================================================
# HYPR path constants (used only by apply_user_choices)
# ============================================================================
_HYPR_USERCONFIGS_DIR = Path("hypr/UserConfigs")
_HYPR_SYSTEM_SETTINGS = Path("hypr/configs") / "SystemSettings.conf"
_HYPR_USER_DEFAULTS = _HYPR_USERCONFIGS_DIR / "01-UserDefaults.conf"


def apply_user_choices(
    cfg: InstallConfig,
    staging_config: Path,
    log: LogFn,
) -> None:
    """Apply user-selected preferences to the staged config tree.

    Writes keyboard layout, editor, resolution, clock format, and startup
    entries to staging files. Operates ONLY within staging_config.

    Args:
        cfg: Install configuration with user preferences.
        staging_config: Path to the staged config tree.
        log: Logging callback.
    """
    sys_settings = staging_config / _HYPR_SYSTEM_SETTINGS
    if sys_settings.is_file():
        replace_kb_layout(sys_settings, cfg.keyboard_layout)
        log(f"[NOTE] kb_layout {cfg.keyboard_layout} configured in settings.")

    if cfg.default_editor:
        defaults = staging_config / _HYPR_USER_DEFAULTS
        if defaults.is_file():
            lines = defaults.read_text(encoding="utf-8", errors="replace").splitlines(
                True
            )
            defaults_out: list[str] = []
            replaced = False
            for line in lines:
                if re.match(r"^\s*#?\s*env\s*=\s*EDITOR,", line):
                    defaults_out.append(
                        f"env = EDITOR,{cfg.default_editor} #default editor\n"
                    )
                    replaced = True
                else:
                    defaults_out.append(line)
            if not replaced:
                defaults_out.insert(
                    0, f"env = EDITOR,{cfg.default_editor} #default editor\n"
                )
            defaults.write_text("".join(defaults_out), encoding="utf-8")
            log(f"[OK] Default editor set to {cfg.default_editor}.")
        else:
            log(
                "[WARN] Default editor template not found; skipping editor configuration"
            )

    if cfg.resolution == "lt_1440p":
        kitty_conf = staging_config / "kitty" / "kitty.conf"
        if kitty_conf.is_file():
            txt = kitty_conf.read_text(encoding="utf-8", errors="replace")
            txt = txt.replace("font_size 16.0", "font_size 14.0")
            kitty_conf.write_text(txt, encoding="utf-8")

        rofi_fonts = staging_config / "rofi" / "0-shared-fonts.rasi"
        if rofi_fonts.is_file():
            txt = rofi_fonts.read_text(encoding="utf-8", errors="replace")
            txt = txt.replace(
                'font: "JetBrainsMono Nerd Font SemiBold 13";',
                'font: "JetBrainsMono Nerd Font SemiBold 11";',
            )
            txt = txt.replace(
                'font: "JetBrainsMono Nerd Font SemiBold 15";',
                'font: "JetBrainsMono Nerd Font SemiBold 13";',
            )
            rofi_fonts.write_text(txt, encoding="utf-8")

        hypr_dir = staging_config / "hypr"
        hyprlock = hypr_dir / "hyprlock.conf"
        hyprlock_2k = hypr_dir / "hyprlock-2k.conf"
        hyprlock_1080 = hypr_dir / "hyprlock-1080p.conf"
        if hyprlock.exists():
            hyprlock.rename(hyprlock_2k)
        if hyprlock_1080.exists():
            hyprlock_1080.rename(hyprlock)

    if not cfg.clock_24h:
        modules = staging_config / "waybar" / "Modules"
        if modules.is_file():
            lines = modules.read_text(encoding="utf-8", errors="replace").splitlines(
                True
            )

            def uncomment(line: str) -> str:
                return re.sub(r"^(\s*)//\s*", r"\1", line)

            def comment(line: str) -> str:
                if re.match(r"^\s*//", line):
                    return line
                return re.sub(r"^(\s*)", r"\1//", line)

            enable_12h = [
                "{:%I:%M %p}",
                "{:%I:%M %p - %d/%b}",
                "{:%B | %a %d, %Y | %I:%M %p}",
                "{:%A, %I:%M %P}",
            ]
            disable_24h = [
                "{:%H:%M:%S}",
                "{:%H:%M}",
                "{:%H:%M - %d/%b}",
                "{:%B | %a %d, %Y | %H:%M}",
                "{:%a %d | %H:%M}",
            ]

            modules_out: list[str] = []
            for line in lines:
                if any(pat in line for pat in enable_12h):
                    modules_out.append(uncomment(line))
                elif any(pat in line for pat in disable_24h):
                    modules_out.append(comment(line))
                else:
                    modules_out.append(line)

            modules.write_text("".join(modules_out), encoding="utf-8")

        hypr_dir = staging_config / "hypr"
        hyprlock_file = hypr_dir / "hyprlock.conf"
        if not hyprlock_file.is_file() and (hypr_dir / "hyprlock-1080p.conf").is_file():
            hyprlock_file = hypr_dir / "hyprlock-1080p.conf"
        if hyprlock_file.is_file():
            txt = hyprlock_file.read_text(encoding="utf-8", errors="replace")
            lines = txt.splitlines(True)

            def ensure_commented(line: str) -> str:
                stripped = line.lstrip()
                indent = line[: len(line) - len(stripped)]
                if stripped.startswith("#"):
                    return line
                return indent + "# " + stripped

            def ensure_uncommented(line: str) -> str:
                stripped = line.lstrip()
                indent = line[: len(line) - len(stripped)]
                if not stripped.startswith("#"):
                    return line
                stripped = re.sub(r"^#+\s*", "", stripped)
                return indent + stripped

            out: list[str] = []
            for line in lines:
                raw = line.lstrip()
                candidate = re.sub(r"^#+\s*", "", raw)
                if "text = cmd[update:1000]" in candidate and 'date +"%H' in candidate:
                    out.append(ensure_commented(line))
                elif (
                    "text = cmd[update:1000]" in candidate
                    and 'date +"%I' in candidate
                    and "%p" in candidate
                ):
                    out.append(ensure_uncommented(line))
                elif (
                    "text = cmd[update:1000]" in candidate
                    and 'date +"%S' in candidate
                    and "%p" not in candidate
                ):
                    out.append(ensure_commented(line))
                elif (
                    "text = cmd[update:1000]" in candidate
                    and 'date +"%S %p' in candidate
                ):
                    out.append(ensure_uncommented(line))
                else:
                    out.append(line)

            txt = "".join(out)
            hyprlock_file.write_text(txt, encoding="utf-8")

    overlay = staging_config / "hypr" / "configs" / "Startup_Apps.conf"
    overlay.parent.mkdir(parents=True, exist_ok=True)
    overlay.touch(exist_ok=True)
    existing = overlay.read_text(encoding="utf-8", errors="replace")

    def add(line: str) -> None:
        nonlocal existing
        if line not in existing:
            with overlay.open("a", encoding="utf-8") as fh:
                fh.write(line)
            existing += line

    if cfg.enable_asus and utils.which("asusctl"):
        add("exec-once = rog-control-center\n")

    if cfg.enable_blueman and utils.which("blueman-applet"):
        add("exec-once = blueman-applet\n")

    if cfg.enable_ags and utils.which("ags"):
        add("exec-once = ags\n")
        # Also uncomment ags lines in Refresh scripts
        for script in ["RefreshNoWaybar.sh", "Refresh.sh"]:
            script_path = staging_config / "hypr" / "scripts" / script
            if script_path.exists():
                txt = script_path.read_text(encoding="utf-8", errors="replace")
                txt = re.sub(r"#ags -q && ags &", "ags -q && ags &", txt)
                script_path.write_text(txt, encoding="utf-8")

    if cfg.enable_quickshell and utils.which("qs"):
        add("exec-once = qs\n")
        # Also uncomment quickshell lines in Refresh scripts
        for script in ["RefreshNoWaybar.sh", "Refresh.sh"]:
            script_path = staging_config / "hypr" / "scripts" / script
            if script_path.exists():
                txt = script_path.read_text(encoding="utf-8", errors="replace")
                txt = re.sub(r"#pkill qs && qs &", "pkill qs && qs &", txt)
                script_path.write_text(txt, encoding="utf-8")

    add("exec-once = $scriptsDir/KeybindsLayoutInit.sh\n")
