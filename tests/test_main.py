"""Tests for the __main__.py CLI entry point."""

from dots_tui.__main__ import parse_args


def test_parse_args_dry_run():
    args = parse_args(["--dry-run"])
    assert args.dry_run is True


def test_parse_args_defaults():
    args = parse_args([])
    assert args.dry_run is False
    assert args.verbose is False
    assert args.upgrade is False
    assert args.express_upgrade is False
    assert args.update is False


def test_parse_args_verbose():
    args = parse_args(["--verbose"])
    assert args.verbose is True


def test_parse_args_verbose_short():
    args = parse_args(["-v"])
    assert args.verbose is True


def test_parse_args_upgrade():
    args = parse_args(["--upgrade"])
    assert args.upgrade is True


def test_parse_args_express_upgrade():
    args = parse_args(["--express-upgrade"])
    assert args.express_upgrade is True


def test_parse_args_update():
    args = parse_args(["--update"])
    assert args.update is True


def test_parse_args_dry_run_and_verbose():
    args = parse_args(["--dry-run", "--verbose"])
    assert args.dry_run is True
    assert args.verbose is True


def test_parse_args_mutually_exclusive_modes(capsys):
    """--upgrade, --express-upgrade, and --update are mutually exclusive."""
    import pytest

    with pytest.raises(SystemExit) as exc_info:
        parse_args(["--upgrade", "--update"])
    assert exc_info.value.code != 0
