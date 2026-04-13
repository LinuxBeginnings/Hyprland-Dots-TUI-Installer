# AGENTS.md - Agentic Coding Guide

This file provides guidance to AI agents (Claude, GitHub Copilot, etc.) working in the Hyprland-Dots TUI Installer repository.

## Quick Reference

### Setup & Dependencies
```bash
uv sync --locked --dev    # Install/sync all dependencies
```

### Common Development Commands
```bash
# Run the TUI
uv run python -m dots_tui              # Start the application
uv run dots-tui                         # Entry-point script (same as above)
uv run python -m dots_tui --verbose    # With verbose logging

# View logs in separate terminal
uv run textual console

# Testing
uv run pytest                              # Run all tests
uv run pytest tests/test_ui_screens.py     # Single test file
uv run pytest -k test_menu_screen_renders  # Single test by name/pattern
uv run pytest tests/ -v                    # Verbose test output

# Code quality
uv run ruff check .      # Lint check
uv run ruff format .     # Auto-format code
uv run basedpyright      # Type checking

# Build standalone binary
uv run pyinstaller build.spec  # Output: dist/dots-tui
```

## Architecture Overview

### Core Structure
- **Entry point**: `src/dots_tui/__main__.py` - CLI argument parsing
- **App bootstrap**: `src/dots_tui/app.py` - Textual App creation and screen routing
- **UI Layer**: `src/dots_tui/screens/` - TUI screens (menu, config, progress, dialogs)
- **Install Engine**: `src/dots_tui/logic/orchestrator.py` - Main workflow orchestrator
- **System Detection**: `src/dots_tui/logic/env_probe.py` (async), `system.py` (sync)
- **File Operations**: `copy_ops.py`, `backup.py`, `restore.py`, `path_safety.py`
- **Utilities**: `utils.py` - Async subprocess execution and output sanitization

### Key Modules
- **orchestrator.py** - Stages files, applies tweaks, copies configs, handles components, restores backups
- **models.py** - Type definitions (InstallConfig, EnvironmentInfo, etc.)
- **env_probe.py** - Async environment detection (runs during startup, non-blocking)
- **system.py** - Sync system detection used during installation
- **path_safety.py** - Enforces safe operations (delete/copy under `$HOME`)
- **plan.py** - Dry-run planning without filesystem mutations

## Code Style Guidelines

### Imports
- Use `from __future__ import annotations` at top of every module
- Standard library imports first, then third-party, then local imports
- Organize within groups: stdlib → third-party → dots_tui internal
- Use absolute imports (e.g., `from dots_tui.logic.models import ...`)

```python
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Literal

from textual.app import App

from dots_tui.logic.models import InstallConfig
```

### Formatting & Naming
- **Line length**: Configure via ruff; max ~100-120 chars
- **Naming conventions**:
  - Classes: `PascalCase` (e.g., `InstallerApp`, `ConfigScreen`)
  - Functions/methods: `snake_case` (e.g., `probe_environment`, `copy_config_dir`)
  - Constants: `UPPER_SNAKE_CASE` (e.g., `MIN_EXPRESS_VERSION`)
  - Private members: leading underscore (e.g., `_probe_task`, `_dry_run`)
- **Spacing**: 2 blank lines between top-level definitions, 1 within classes

### Type Annotations
- **Required everywhere** - use comprehensive type hints
- Use `from __future__ import annotations` for forward references
- Leverage `typing` module: `Literal`, `Union` (via `|`), `Optional` (via `| None`)
- Type async functions as `async def func(...) -> ReturnType:`
- Use `TypeVar` for generics, `Protocol` for duck typing
- Return `None` explicitly for functions without return values

```python
async def probe_environment() -> ProbeResult:
    """Probe system for installation compatibility."""
    ...

def copy_phase1_dir(
    *,
    name: str,
    staging_config_root: Path,
    target_config_root: Path,
    log,
) -> Path | None:
    """Copy phase 1 directory with logging. Returns backup path or None."""
    ...
```

### Docstrings
- Use **Google-style docstrings** (summary, Args, Returns, Raises)
- First line is brief summary; expand in body if needed
- Document all exceptions raised
- Include Args/Returns/Raises only if applicable

```python
def _copytree(src: Path, dst: Path) -> None:
    """Copy a directory tree, replacing destination if it exists.

    Raises:
        RuntimeError: If permission is denied during removal or copy.
    """
    ...

async def run_cmd(
    argv: list[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    log: LogFn | None = None,
    input_text: str | None = None,
) -> CmdResult:
    """Execute a command asynchronously.

    Args:
        argv: Command and arguments to execute.
        cwd: Working directory for subprocess.
        env: Environment variables for subprocess.
        log: Logging callback function.
        input_text: Optional input text to pipe to subprocess.

    Returns:
        CmdResult with returncode, stdout, stderr.

    Raises:
        RuntimeError: If command execution fails.
    """
    ...
```

### Error Handling
- **Catch specific exceptions**, not bare `except:` or `except Exception:`
- Chain exceptions with `from e` for context
- Provide meaningful error messages with context
- Log or propagate; don't silently ignore

```python
try:
    shutil.rmtree(dst)
except PermissionError as e:
    raise RuntimeError(
        f"Permission denied removing existing directory {dst}: {e}"
    ) from e

try:
    shutil.copy2(p, dst)
except OSError:
    pass  # Acceptable for non-critical operations (e.g., rofi restore)
```

### Async/Await Patterns
- Use `async def` for I/O-bound operations (subprocess, file I/O)
- Avoid blocking calls in async functions
- Use `asyncio.create_task()` for background tasks
- Use `asyncio.Lock()` for shared state coordination

```python
self._probe_task = asyncio.create_task(probe_environment())
async with self._probe_lock:
    # coordinate access to shared state
    ...
```

### File Headers
Every Python file must start with:
```python
#!/usr/bin/env python3  # For executable scripts
# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================
from __future__ import annotations
```

### Code Patterns to Follow
- Use `Path` from `pathlib` for filesystem operations
- Use `*` in function signatures to force keyword arguments: `def func(*, required_kwarg):`
- Prefer `dict | None` over `Optional[dict]`
- Use type guards: `if isinstance(obj, MyType):`
- Validate paths with `path_safety.assert_safe_path()` before mutations

### Dry-Run Sandbox
The `--dry-run` flag creates a **temporary directory sandbox** (not the real home):
- Sandboxed home created via `tempfile.TemporaryDirectory(prefix="hyprdots-sandbox-")`
- `set_home_override()` redirects path safety checks to sandbox home
- All operations execute against sandbox `.config/` and `.local/share/`
- Sandbox automatically cleaned up after execution (no real system changes)
- Use `config.dry_run` to conditionally skip operations (sudo auth, xdg updates, etc.)
- Path safety validation uses the override home via `assert_safe_path()`

## Testing

### Test Organization
- Tests are in `tests/` directory
- Test files: `test_*.py`
- Fixtures in `conftest.py`
- Helpers in `helpers.py`
- Use `pytest` with `pytest-asyncio` for async tests

### Writing Tests
```python
# Use fixtures
@pytest.fixture
def app() -> InstallerApp:
    return InstallerApp(dry_run=True)

# Test async functions
async def test_probe_environment() -> None:
    result = await probe_environment()
    assert result is not None

# Use Textual's testing framework
async def test_menu_screen_renders(app: InstallerApp) -> None:
    async with app.run_test() as _:
        assert isinstance(app.screen, MenuScreen)
```

### Running Tests
```bash
uv run pytest                              # All tests
uv run pytest tests/test_ui_screens.py     # Specific file
uv run pytest -k test_menu_screen          # By name pattern
uv run pytest -v                           # Verbose
uv run pytest tests/ --tb=short            # Short traceback
```

## Quality Assurance

### Pre-commit Checks (Required before pushing)
```bash
# Format code
uv run ruff format .

# Lint
uv run ruff check . --fix

# Type check
uv run basedpyright

# Run tests
uv run pytest
```

### CI/CD (GitHub Actions)
- Linting, type checking, and tests run automatically on push
- Failures block merges

## Notes for AI Agents

1. **Code Generation**: Follow all style guidelines above. Use comprehensive type hints.
2. **Error Messages**: Include context and suggest fixes when possible.
3. **Testing**: Write tests for new functionality; run full test suite before finishing.
4. **Documentation**: Update docstrings and inline comments for complex logic.
5. **Git**: Create meaningful commits with clear messages.
6. **Dry-run**: Always respect `--dry-run` flag; use `logic/plan.py` for planning.
7. **Path Safety**: ALWAYS use `path_safety.assert_safe_path()` before filesystem mutations.
8. **Async Awareness**: Distinguish async vs sync operations; use proper patterns.

## References

- **Python Version**: 3.11+
- **Type Checking**: basedpyright (basic mode)
- **Formatting**: ruff (code formatter + linter)
- **Testing**: pytest + pytest-asyncio
- **UI Framework**: Textual (TUI framework)
- **Build Tool**: uv (Python package manager)
- **Binary Build**: PyInstaller (build.spec)

## Repository Metadata
- **License**: GNU GPLv3
- **Repository**: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
- **Status**: Active development (v0.2.1)
