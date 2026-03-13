# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path

import pytest

from dots_tui.logic.path_safety import assert_safe_path


class TestPathSafety:
    def test_rejects_non_absolute(self, tmp_path: Path) -> None:
        """assert_safe_path must refuse relative paths."""
        with pytest.raises(RuntimeError, match="non-absolute"):
            assert_safe_path(Path("relative/path"), home=tmp_path)

    def test_rejects_root(self, tmp_path: Path) -> None:
        """assert_safe_path must refuse the filesystem root '/'."""
        with pytest.raises(RuntimeError, match="'/'"):
            assert_safe_path(Path("/"), home=tmp_path)

    def test_rejects_outside_home(self, tmp_path: Path) -> None:
        """assert_safe_path must refuse paths outside $HOME."""
        with pytest.raises(RuntimeError, match=r"outside \$HOME"):
            assert_safe_path(Path("/etc/passwd"), home=tmp_path)

    def test_accepts_path_inside_home(self, tmp_path: Path) -> None:
        """assert_safe_path must not raise for a path nested under home."""
        # Should not raise — no assertion needed, the absence of an exception is the test.
        assert_safe_path(tmp_path / ".config" / "hypr", home=tmp_path)

    def test_accepts_home_itself(self, tmp_path: Path) -> None:
        """assert_safe_path must accept home itself (e.g. when wiping a stale dir)."""
        assert_safe_path(tmp_path, home=tmp_path)
