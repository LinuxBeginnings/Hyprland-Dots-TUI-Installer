## Hyprland Dotfiles TUI Installer

## 0.2.0 - 3/13/2026

- Added standalone operation by searching `~/Hyprland-Dots` when running outside the repository.
- Added a shallow repository download action in the installer menu.
- Added a GitHub Actions release workflow for version tags.
- Improved path safety by validating absolute paths before normalization.
- Fixed callback protocols and related tests for strict type checking compatibility.
- Expanded test coverage for CLI parsing, UI screens, restore/path safety, and backup discovery.
- Updated setup documentation and release binary instructions in `README.md`.

## 3/12/2026
### Summary
- Add GitHub Actions release workflow for version tags
- Add comprehensive UI screen tests (ConfigScreen, ConfirmScreen, ProgressScreen)
- Fix path safety validation to enforce absolute paths before normalization
- Add project headers across all .py and .sh files
- Various bug fixes and test reliability improvements
### Commits
- ci: Add GitHub Actions release workflow for version tags
- test: Add UI screen tests and standardise asyncio mode
- test: Progress screen tests
- test: Add ConfigScreen and ConfirmScreen interaction tests
- test: Improve backup discovery test reliability
- fix(safety): Validate absolute paths before normalization
- test(cli): Add argument parser coverage
- test: Add unit coverage for restore critical paths
- chore: .gitignore
- Various additional fixes, test improvements, and project housekeeping

## 2/26/2026

- Added project headers in all .py and .sh files

```text
# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================

```
