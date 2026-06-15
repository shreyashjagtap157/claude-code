"""Tests for the CLI entry point."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from prysm.cli import main
from prysm.version import VERSION


class TestCLI:
    """Tests for the CLI entry point."""

    def test_version_flag(self):
        """The --version flag should print version and exit."""
        test_args = ["prysm", "--version"]
        with patch.object(sys, "argv", test_args):
            with pytest.raises(SystemExit) as exc_info:
                main()
            assert exc_info.value.code == 0

    def test_help_text_available(self):
        """The CLI should have help text."""
        from click.testing import CliRunner
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0
        assert "Prysm" in result.output
        assert "model" in result.output
        assert "runtime" in result.output
