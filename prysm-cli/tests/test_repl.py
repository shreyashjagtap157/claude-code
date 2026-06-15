"""Tests for the REPL shell — PrysmREPL class."""

from unittest.mock import MagicMock, patch, PropertyMock
import pytest

from prysm.repl import PrysmREPL
from prysm.commands.base import CommandRegistry
from prysm.config.schema import PrysmConfig


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def minimal_config():
    """A minimal PrysmConfig for REPL tests."""
    return PrysmConfig()


@pytest.fixture
def mock_prompt_session():
    """Mock prompt_toolkit PromptSession to avoid TTY dependency."""
    with patch("prysm.repl.PromptSession") as mock:
        # Make the prompt() method return empty on first call to exit loop
        instance = mock.return_value
        instance.prompt.return_value = ""  # Will be overridden per test
        yield instance


# ─── Initialization Tests ────────────────────────────────────────────────────

class TestREPLInit:
    """Tests for PrysmREPL construction."""

    def test_creates_command_registry(self, minimal_config, mock_prompt_session):
        """The REPL should have a non-empty command registry."""
        repl = PrysmREPL(minimal_config)
        assert isinstance(repl.commands, CommandRegistry)
        assert len(repl.commands) > 0

    def test_registers_expected_commands(self, minimal_config, mock_prompt_session):
        """The REPL should register /help, /exit, /quit."""
        repl = PrysmREPL(minimal_config)
        assert "/help" in repl.commands
        assert "/exit" in repl.commands
        assert "/quit" in repl.commands

    def test_running_flag_true_on_init(self, minimal_config, mock_prompt_session):
        """The running flag should start as True."""
        repl = PrysmREPL(minimal_config)
        assert repl.running is True

    def test_stores_config(self, minimal_config, mock_prompt_session):
        """The REPL should store the config."""
        repl = PrysmREPL(minimal_config)
        assert repl.config is minimal_config

    def test_verbose_flag_defaults_false(self, minimal_config, mock_prompt_session):
        """Verbose should default to False."""
        repl = PrysmREPL(minimal_config)
        assert repl.verbose is False

    def test_verbose_flag_true(self, minimal_config, mock_prompt_session):
        """Verbose flag should be settable."""
        repl = PrysmREPL(minimal_config, verbose=True)
        assert repl.verbose is True

    def test_creates_ui_renderer(self, minimal_config, mock_prompt_session):
        """The REPL should have a UI renderer."""
        repl = PrysmREPL(minimal_config)
        from prysm.ui.renderer import UIRenderer
        assert isinstance(repl.ui, UIRenderer)


# ─── Banner Tests ────────────────────────────────────────────────────────────

class TestREPLBanner:
    """Tests for the startup banner."""

    def test_banner_contains_prysm(self, minimal_config, mock_prompt_session):
        """The banner should mention PRYSM."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._show_banner()
            # Panel was printed
            assert mock_print.called
            # Extract the panel text
            panel = mock_print.call_args[0][0]
            panel_str = panel.renderable
            assert "P R Y S M" in str(panel_str)

    def test_banner_contains_version(self, minimal_config, mock_prompt_session):
        """The banner should show the version."""
        from prysm.version import VERSION
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._show_banner()
            panel = mock_print.call_args[0][0]
            panel_str = panel.renderable
            assert VERSION in str(panel_str)

    def test_banner_contains_tagline(self, minimal_config, mock_prompt_session):
        """The banner should contain the tagline."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._show_banner()
            panel = mock_print.call_args[0][0]
            panel_str = panel.renderable
            assert "Your models" in str(panel_str)
            assert "Your runtime" in str(panel_str)
            assert "Your code" in str(panel_str)

    def test_banner_contains_help_hint(self, minimal_config, mock_prompt_session):
        """The banner should tell the user to type /help."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._show_banner()
            panel = mock_print.call_args[0][0]
            panel_str = panel.renderable
            assert "/help" in str(panel_str)


# ─── Command Handling Tests ──────────────────────────────────────────────────

class TestREPLCommandHandling:
    """Tests for _handle_command."""

    def test_known_command_dispatches(self, minimal_config, mock_prompt_session):
        """A known command should dispatch to the command's execute method."""
        repl = PrysmREPL(minimal_config)
        with patch.object(repl.commands, "execute") as mock_execute:
            repl._handle_command("/help")
            mock_execute.assert_called_once_with("/help", [])

    def test_known_command_with_args(self, minimal_config, mock_prompt_session):
        """A known command with arguments should pass them through."""
        repl = PrysmREPL(minimal_config)
        with patch.object(repl.commands, "execute") as mock_execute:
            # Use /help with args since /echo doesn't exist in the default REPL
            repl._handle_command("/help some extra args")
            mock_execute.assert_called_once_with("/help", ["some", "extra", "args"])

    def test_unknown_command_shows_error(self, minimal_config, mock_prompt_session):
        """An unknown command should show an error message."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._handle_command("/nonexistent")
            # Should print two messages: unknown command + suggestion
            assert mock_print.call_count >= 2
            first_arg = mock_print.call_args_list[0][0][0]
            assert "Unknown command" in str(first_arg)

    def test_unknown_command_shows_help_hint(self, minimal_config, mock_prompt_session):
        """An unknown command should suggest /help."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._handle_command("/nonexistent")
            second_arg = mock_print.call_args_list[1][0][0]
            assert "/help" in str(second_arg)

    def test_empty_string_after_slash(self, minimal_config, mock_prompt_session):
        """A bare '/' should not crash."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._handle_command("/")
            assert mock_print.call_count >= 1
            first_arg = mock_print.call_args_list[0][0][0]
            assert "Unknown command" in str(first_arg)


# ─── Message Handling Tests ─────────────────────────────────────────────────

class TestREPLMessageHandling:
    """Tests for _handle_message (non-slash input)."""

    def test_free_form_message_shows_info(self, minimal_config, mock_prompt_session):
        """A free-form message should show 'not implemented' info."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._handle_message("Hello")
            assert mock_print.call_count >= 1
            first_arg = mock_print.call_args_list[0][0][0]
            assert "Agent loop" in str(first_arg) or "Phase 0" in str(first_arg)

    def test_free_form_message_phase_mention(self, minimal_config, mock_prompt_session):
        """A free-form message should mention this is Phase 0."""
        repl = PrysmREPL(minimal_config)
        with patch("prysm.repl.console.print") as mock_print:
            repl._handle_message("Hello")
            messages = [str(c[0][0]) for c in mock_print.call_args_list]
            combined = " ".join(messages)
            assert "Phase 0" in combined or "not yet" in combined


# ─── Stop Behavior Tests ─────────────────────────────────────────────────────

class TestREPLStop:
    """Tests for the stop() method."""

    def test_stop_sets_running_false(self, minimal_config, mock_prompt_session):
        """stop() should set running to False."""
        repl = PrysmREPL(minimal_config)
        assert repl.running is True
        repl.stop()
        assert repl.running is False

    def test_stop_is_idempotent(self, minimal_config, mock_prompt_session):
        """Calling stop() multiple times should not raise."""
        repl = PrysmREPL(minimal_config)
        repl.stop()
        repl.stop()  # Should not raise
        assert repl.running is False


# ─── Integration: Exit Command Stops REPL ────────────────────────────────────

class TestREPLExitIntegration:
    """Tests that the /exit command correctly stops the REPL."""

    def test_exit_command_stops_via_repl(self, minimal_config, mock_prompt_session):
        """Executing /exit from a repl should call repl.stop()."""
        repl = PrysmREPL(minimal_config)
        with patch.object(repl, "stop") as mock_stop:
            repl._handle_command("/exit")
            mock_stop.assert_called_once()

    def test_quit_alias_stops_via_repl(self, minimal_config, mock_prompt_session):
        """Executing /quit should also call repl.stop()."""
        repl = PrysmREPL(minimal_config)
        with patch.object(repl, "stop") as mock_stop:
            repl._handle_command("/quit")
            mock_stop.assert_called_once()
