# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path


def _normalize(p: Path) -> Path:
    # Avoid strict resolve() since targets may not exist yet.
    try:
        return p.expanduser().resolve(strict=False)
    except Exception:
        return p


def assert_safe_path(path: Path, *, home: Path | None = None) -> None:
    """Fail fast if a destructive operation targets an unsafe path.

    The installer frequently deletes/replaces directories. We restrict those
    operations to paths under the user's home directory to avoid catastrophic
    deletion when XDG_* env vars are misconfigured.
    """

    if not path.is_absolute():
        raise RuntimeError(f"Refusing to operate on non-absolute path: {path}")

    p = _normalize(path)

    if str(p) == "/":
        raise RuntimeError("Refusing to operate on '/'")

    h = _normalize(home or Path.home())
    try:
        p.relative_to(h)
    except Exception as e:
        raise RuntimeError(f"Refusing to operate outside $HOME: {p}") from e
