# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations

from pathlib import Path

import pytest

from dots_tui.logic.path_safety import assert_safe_path, set_home_override


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


class TestSetHomeOverride:
    """Tests for the module-level home override used by sandbox dry-run."""

    def test_override_allows_sandbox_paths(self, tmp_path: Path) -> None:
        """When home override is set, sandbox paths should pass validation."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        set_home_override(sandbox)
        try:
            # Should not raise — sandbox path is under the override home
            assert_safe_path(sandbox / ".config" / "hypr")
        finally:
            set_home_override(None)

    def test_override_rejects_non_sandbox_paths(self, tmp_path: Path) -> None:
        """When home override is set, paths outside sandbox should be rejected."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        set_home_override(sandbox)
        try:
            with pytest.raises(RuntimeError, match=r"outside \$HOME"):
                assert_safe_path(Path("/etc/passwd"))
        finally:
            set_home_override(None)

    def test_clearing_override_restores_default(self, tmp_path: Path) -> None:
        """Setting override to None restores Path.home() behavior."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        set_home_override(sandbox)
        set_home_override(None)
        # After clearing, assert_safe_path should use Path.home() or explicit home=
        # Path under tmp_path with explicit home should still work
        assert_safe_path(tmp_path / "some" / "dir", home=tmp_path)

    def test_explicit_home_param_overrides_module_override(
        self, tmp_path: Path
    ) -> None:
        """Explicit home= kwarg takes precedence over module-level override."""
        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        real_home = tmp_path / "real"
        real_home.mkdir()
        set_home_override(sandbox)
        try:
            # Explicit home= should take priority over module override
            assert_safe_path(real_home / ".config", home=real_home)
        finally:
            set_home_override(None)
