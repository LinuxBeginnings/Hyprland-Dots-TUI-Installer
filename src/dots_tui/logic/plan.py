# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PlannedOp:
    kind: str
    detail: str
    src: Path | None = None
    dst: Path | None = None


class PlanCollector:
    """Collect intended operations for dry-run/plan mode."""

    def __init__(self) -> None:
        self.ops: list[PlannedOp] = []

    def add(
        self,
        *,
        kind: str,
        detail: str,
        src: Path | None = None,
        dst: Path | None = None,
    ) -> None:
        self.ops.append(PlannedOp(kind=kind, detail=detail, src=src, dst=dst))
