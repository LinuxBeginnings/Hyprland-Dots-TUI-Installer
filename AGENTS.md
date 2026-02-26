# AGENTS.md
This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Common commands
### Setup
- Install/sync deps: `uv sync --locked --dev`

### Run (development)
- Start the TUI: `uv run python -m dots_tui`
- Entry-point script (same as above): `uv run dots-tui`
- Verbose logs to Textual DevTools: `uv run python -m dots_tui --verbose`
  - In a second terminal: `uv run textual console`

### Tests
- All tests: `uv run pytest`
- Single test file: `uv run pytest tests/test_ui_screens.py`
- Single test by name: `uv run pytest -k test_name`

### Lint / format / typecheck
- Lint: `uv run ruff check .`
- Format: `uv run ruff format .`
- Typecheck: `uv run basedpyright`

### Build standalone binary
- `uv run pyinstaller build.spec`
  - Output binary: `dist/dots-tui`

## High-level architecture
- **Entry point & app bootstrap**: `src/dots_tui/__main__.py` parses CLI flags and starts the app; `src/dots_tui/app.py` creates the Textual `InstallerApp`, kicks off async environment probing, and routes to the initial screen (menu/config/progress).
- **UI layer (Textual screens)**: `src/dots_tui/screens/` contains the TUI screens:
  - `menu.py` (mode selection), `config.py` (install configuration form), `progress.py` (execution + log viewer), plus confirm/input dialogs.
- **Core install/update engine**: `src/dots_tui/logic/orchestrator.py` is the main workflow runner. It stages files, applies environment-specific tweaks, copies configs (phase 1/2 + waybar merge), handles optional components, restores from backups on upgrade, and performs post-copy finalization (symlinks, wallpaper, SDDM tweaks).
- **System/environment detection**:
  - `logic/env_probe.py` provides **async** probes used during UI startup (non-blocking).
  - `logic/system.py` provides **sync** detection used during installation.
- **File operations & safety**:
  - `logic/copy_ops.py`, `logic/backup.py`, `logic/restore.py` implement copy/backup/restore flows.
  - `logic/path_safety.py` enforces safe delete/copy boundaries (under `$HOME`).
- **Dry-run planning**: `logic/plan.py` collects intended operations for `--dry-run` without mutating the filesystem.
- **Utilities**: `utils.py` wraps async subprocess execution and sanitizes output for the Textual log.

## Notes from repository docs
- README describes supported OS targets, run modes, CLI flags, and how to view verbose logs via `textual console`.
- `CODE_GUIDE.md` is labeled “AI Generated” and “must be deleted after testing”; treat it as potentially stale if you reference it.
