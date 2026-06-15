"""Tests for the slash command system — CommandRegistry, HelpCommand, ExitCommand."""

from unittest.mock import MagicMock, patch
import pytest
import sys

from prysm.commands.base import Command, CommandRegistry
from prysm.commands.help_cmd import HelpCommand
from prysm.commands.exit_cmd import ExitCommand


# ─── Mock Command Fixtures ───────────────────────────────────────────────────

class _EchoCommand(Command):
    """A test command that records its invocations."""

    def __init__(self):
        self.called_with: list[tuple[list[str], object]] = []

    @property
    def name(self) -> str:
        return "/echo"

    @property
    def description(self) -> str:
        return "Echo back arguments"

    def execute(self, args: list[str], repl=None) -> None:
        self.called_with.append((args, repl))


class _GreetCommand(Command):
    @property
    def name(self) -> str:
        return "/greet"

    @property
    def description(self) -> str:
        return "Greet the user"

    def execute(self, args: list[str], repl=None) -> None:
        pass


# ─── CommandRegistry Tests ───────────────────────────────────────────────────

class TestCommandRegistry:
    """Tests for the CommandRegistry class."""

    def test_register_and_get(self):
        """Registering a command should make it retrievable."""
        registry = CommandRegistry()
        cmd = _EchoCommand()
        registry.register(cmd)
        assert registry.get("/echo") is cmd

    def test_register_alias(self):
        """An alias should point to the same command object."""
        registry = CommandRegistry()
        exit_cmd = ExitCommand()
        registry.register(exit_cmd)
        registry.register_alias("/quit", exit_cmd)

        assert registry.get("/exit") is exit_cmd
        assert registry.get("/quit") is exit_cmd
        # Both keys point to the exact same object
        assert registry.get("/exit") is registry.get("/quit")

    def test_unregister(self):
        """Unregistering should remove the command."""
        registry = CommandRegistry()
        registry.register(_EchoCommand())
        registry.unregister("/echo")
        assert registry.get("/echo") is None

    def test_unregister_nonexistent(self):
        """Unregistering a non-existent command should not raise."""
        registry = CommandRegistry()
        registry.unregister("/nonexistent")  # Should not raise

    def test_execute_calls_command(self):
        """Execute should call the command's execute method."""
        registry = CommandRegistry()
        cmd = _EchoCommand()
        registry.register(cmd)
        registry.execute("/echo", ["hello", "world"], repl="test_repl")
        assert cmd.called_with == [(["hello", "world"], "test_repl")]

    def test_execute_unknown_command(self):
        """Execute on an unknown command should do nothing (no error)."""
        registry = CommandRegistry()
        # Should not raise
        registry.execute("/nonexistent", [])

    def test_contains(self):
        """The 'in' operator should work."""
        registry = CommandRegistry()
        cmd = _EchoCommand()
        registry.register(cmd)
        assert "/echo" in registry
        assert "/nonexistent" not in registry

    def test_iteration(self):
        """Iterating should yield all registered commands."""
        registry = CommandRegistry()
        cmd1 = _EchoCommand()
        cmd2 = _GreetCommand()
        registry.register(cmd1)
        registry.register(cmd2)

        names = {c.name for c in registry}
        assert names == {"/echo", "/greet"}

    def test_len(self):
        """Len should return the count of registered commands."""
        registry = CommandRegistry()
        assert len(registry) == 0
        registry.register(_EchoCommand())
        assert len(registry) == 1
        registry.register(_GreetCommand())
        assert len(registry) == 2

    def test_register_twice_overwrites(self):
        """Registering the same name twice should overwrite."""
        registry = CommandRegistry()
        cmd1 = _EchoCommand()
        cmd2 = _EchoCommand()
        registry.register(cmd1)
        registry.register(cmd2)
        assert registry.get("/echo") is cmd2
        assert len(registry) == 1


# ─── HelpCommand Tests ───────────────────────────────────────────────────────

class TestHelpCommand:
    """Tests for the /help command."""

    def test_name_and_description(self):
        """HelpCommand should have correct identity."""
        cmd = HelpCommand()
        assert cmd.name == "/help"
        assert cmd.description == "Show available commands"

    def test_execute_no_repl_shows_error(self):
        """Without a repl context, /help should show an error."""
        cmd = HelpCommand()
        with patch("prysm.commands.help_cmd.console.print") as mock_print:
            cmd.execute([])
            mock_print.assert_called_once_with(
                "[red]No REPL context available[/red]"
            )

    def test_execute_with_repl_shows_table(self):
        """With a repl context, /help should build a table from registered commands."""
        # Create a mock repl with a registry containing test commands
        mock_repl = MagicMock()
        mock_registry = MagicMock()
        cmd1 = _EchoCommand()
        cmd2 = _GreetCommand()
        mock_registry.__iter__.return_value = iter([cmd1, cmd2])
        mock_repl.commands = mock_registry

        cmd = HelpCommand()
        with patch("prysm.commands.help_cmd.console.print") as mock_print:
            cmd.execute([], repl=mock_repl)
            # Should print a table and a hint line = 2 print calls
            assert mock_print.call_count == 2

    def test_execute_with_repl_added_to_help_text(self):
        """The help output should mention --help."""
        mock_repl = MagicMock()
        mock_registry = MagicMock()
        mock_registry.__iter__.return_value = iter([])
        mock_repl.commands = mock_registry

        cmd = HelpCommand()
        with patch("prysm.commands.help_cmd.console.print") as mock_print:
            cmd.execute([], repl=mock_repl)
            # Second call should contain the hint about --help
            second_call_arg = mock_print.call_args_list[1][0][0]
            assert "--help" in str(second_call_arg)


# ─── ExitCommand Tests ───────────────────────────────────────────────────────

class TestExitCommand:
    """Tests for the /exit command."""

    def test_name_and_description(self):
        """ExitCommand should have correct identity."""
        cmd = ExitCommand()
        assert cmd.name == "/exit"
        assert cmd.description == "Exit Prysm"

    def test_execute_with_repl_stops_it(self):
        """With a repl context, /exit should call repl.stop()."""
        mock_repl = MagicMock()
        mock_repl.running = True

        cmd = ExitCommand(mock_repl)
        cmd.execute([])

        assert mock_repl.stop.called
        # running should still be set (stop() is what changes it)
        assert mock_repl.running

    def test_execute_with_repl_passed_as_arg(self):
        """The repl argument should take priority over the stored one."""
        mock_repl1 = MagicMock()
        mock_repl2 = MagicMock()

        cmd = ExitCommand(mock_repl1)
        cmd.execute([], repl=mock_repl2)

        # It should stop mock_repl2, not mock_repl1
        mock_repl2.stop.assert_called_once()
        mock_repl1.stop.assert_not_called()

    def test_execute_without_repl_exits(self):
        """Without a repl context, /exit should call sys.exit(0)."""
        cmd = ExitCommand()
        with patch("prysm.commands.exit_cmd.console.print") as mock_print:
            with pytest.raises(SystemExit) as exc_info:
                cmd.execute([])
            assert exc_info.value.code == 0
            mock_print.assert_called_once_with("[yellow]Goodbye![/yellow]")

    def test_execute_without_repl_no_exit_if_repl_provided(self):
        """No sys.exit if repl is provided even when not stored during init."""
        mock_repl = MagicMock()
        cmd = ExitCommand()  # No repl stored
        cmd.execute([], repl=mock_repl)
        mock_repl.stop.assert_called_once()


# ─── Abstract Command Base Tests ─────────────────────────────────────────────

class TestCommandBase:
    """Tests for the abstract Command base class."""

    def test_usage_default(self):
        """The usage property should default to /<name>.

        Note: If the command name already starts with '/', usage will be
        '//name' since the base class prepends '/'. Commands should define
        their name starting with the actual name only, without '/', or
        override usage if needed.
        """
        cmd = _EchoCommand()
        assert cmd.usage == "/echo"
