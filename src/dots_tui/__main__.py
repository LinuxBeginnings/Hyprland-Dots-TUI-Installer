#!/usr/bin/env python3
# ============================================================================
#  KoolDots TUI Installer (2026)
#  Project URL: https://github.com/LinuxBeginnings/Hyprland-Dots-TUI-Installer
#  License: GNU GPLv3
#  SPDX-License-Identifier: GPL-3.0-or-later
# ============================================================================

from __future__ import annotations

import argparse
import os

from rich_argparse import RichHelpFormatter


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse CLI arguments. Accepts an optional argv list for testing."""
    parser = argparse.ArgumentParser(
        prog="dots_tui",
        description="[bold blue]Hyprland-Dots[/bold blue] [magenta]TUI Installer[/magenta]",
        formatter_class=RichHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run in dry-run mode (no filesystem changes)",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose/debug logging output",
    )

    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--upgrade",
        action="store_true",
        help="Start in upgrade mode (skip main menu)",
    )
    mode.add_argument(
        "--express-upgrade",
        action="store_true",
        help="Start in express upgrade mode (skip main menu)",
    )
    mode.add_argument(
        "--update",
        action="store_true",
        help="Start in repo update mode (skip main menu)",
    )

    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    from dots_tui.app import run

    args = parse_args(argv)

    start = None
    if args.upgrade:
        start = "upgrade"
    elif args.express_upgrade:
        start = "express"
    elif args.update:
        start = "update"
    if args.verbose:
        os.environ["TEXTUAL"] = "devtools"

    run(dry_run=args.dry_run, start=start, verbose=args.verbose)


if __name__ == "__main__":
    main()
