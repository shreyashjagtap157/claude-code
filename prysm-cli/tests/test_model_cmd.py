"""Tests for the /model command — model lifecycle management."""

from unittest.mock import MagicMock, patch
import pytest

from prysm.commands.model_cmd import ModelCommand
from prysm.models.registry import ModelEntry, ModelRegistry


@pytest.fixture
def populated_registry(temp_dir):
    """Create a ModelRegistry populated with test models."""
    path = temp_dir / "models.json"
    registry = ModelRegistry(path=path)
    registry.add(ModelEntry(id="openai/gpt-4o", name="GPT-4o", provider="openai",
                             context_length=128000, capabilities=["chat", "tools", "vision"]))
    registry.add(ModelEntry(id="anthropic/claude", name="Claude Sonnet", provider="anthropic",
                             context_length=200000, runtime="anthropic"))
    registry.add(ModelEntry(id="local/codellama", name="CodeLlama", provider="local",
                             path="/models/codellama.gguf", runtime="llama-cpp",
                             runtime_params={"n_gpu_layers": -1}))
    return registry


class TestModelCommand:
    """Tests for the ModelCommand class."""

    def test_name_and_description(self):
        """Should have correct identity."""
        cmd = ModelCommand()
        assert cmd.name == "/model"
        assert cmd.description

    def test_list_empty(self):
        """Listing models when none registered should show a message."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry") as mock_registry:
            mock_registry.list_all.return_value = []
            with patch("prysm.commands.model_cmd.console.print") as mock_print:
                cmd._list_models()
            # Should print "No models registered"
            outputs = [str(c[0][0]) for c in mock_print.call_args_list]
            assert any("No models" in o for o in outputs)

    def test_list_populated(self, populated_registry):
        """Listing models should show them in a table."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry", populated_registry):
            with patch("prysm.commands.model_cmd.console.print") as mock_print:
                cmd._list_models()
            # Should print at least 2 times (table + total line)
            assert mock_print.call_count >= 2
            # Check that the table was rendered (first call is the Table)
            rendered = str(mock_print.call_args_list[0][0][0])
            assert "gpt-4o" in rendered or "Table" in str(type(mock_print.call_args_list[0][0][0]))

    def test_add_model_minimal(self):
        """Adding a model with minimal args should work."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry") as mock_registry:
            mock_registry.count.return_value = 0  # First model → default
            with patch("prysm.commands.model_cmd.ModelEntry") as mock_entry_cls:
                with patch("prysm.commands.model_cmd.console.print") as mock_print:
                    cmd._add_model(["my-model", "--name", "My Model", "--provider", "openai"])
                mock_entry_cls.assert_called_once()
                kwargs = mock_entry_cls.call_args[1]
                assert kwargs["id"] == "my-model"
                assert kwargs["name"] == "My Model"
                assert kwargs["provider"] == "openai"
                # First model should be default
                assert mock_registry.add.called

    def test_add_model_with_runtime(self):
        """Adding a model with runtime option should work."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry") as mock_registry:
            mock_registry.count.return_value = 1
            with patch("prysm.commands.model_cmd.ModelEntry") as mock_entry_cls:
                with patch("prysm.commands.model_cmd.console.print"):
                    cmd._add_model([
                        "local/llama", "--name", "Llama",
                        "--provider", "local", "--runtime", "llama-cpp",
                        "--context-length", "8192",
                    ])
                kwargs = mock_entry_cls.call_args[1]
                assert kwargs["runtime"] == "llama-cpp"
                assert kwargs["context_length"] == 8192

    def test_remove_model(self, populated_registry):
        """Removing a model should work."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry", populated_registry):
            with patch("prysm.commands.model_cmd.console.print"):
                cmd._remove_model(["openai/gpt-4o"])
            # Model should be removed
            assert populated_registry.get("openai/gpt-4o") is None

    def test_remove_nonexistent(self):
        """Removing a non-existent model should show error."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry") as mock_registry:
            mock_registry.get.return_value = None
            with patch("prysm.commands.model_cmd.console.print") as mock_print:
                cmd._remove_model(["nonexistent"])
            output = str(mock_print.call_args[0][0])
            assert "not found" in output.lower()

    def test_info_model(self, populated_registry):
        """Showing model info should display properties."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry", populated_registry):
            with patch("prysm.commands.model_cmd.console.print") as mock_print:
                cmd._show_model_info(["openai/gpt-4o"])
            # Should print a table
            assert mock_print.call_count >= 1
            table = mock_print.call_args_list[0][0][0]
            assert hasattr(table, "title")  # It's a Rich Table
            assert "gpt-4o" in table.title or "gpt-4o" in str(table)

    def test_info_nonexistent(self):
        """Info for non-existent model should show error."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry") as mock_registry:
            mock_registry.get.return_value = None
            with patch("prysm.commands.model_cmd.console.print") as mock_print:
                cmd._show_model_info(["nonexistent"])
            output = str(mock_print.call_args[0][0])
            assert "not found" in output.lower()

    def test_execute_list_subcommand(self, populated_registry):
        """Execute 'list' should call _list_models."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry", populated_registry):
            with patch.object(cmd, "_list_models") as mock_list:
                cmd.execute(["list"])
                mock_list.assert_called_once()

    def test_execute_no_args_calls_list(self, populated_registry):
        """Execute with no args should call _list_models."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry", populated_registry):
            with patch.object(cmd, "_list_models") as mock_list:
                cmd.execute([])
                mock_list.assert_called_once()

    def test_execute_remove_subcommand(self, populated_registry):
        """Execute 'remove' should call _remove_model."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry", populated_registry):
            with patch.object(cmd, "_remove_model") as mock_remove:
                cmd.execute(["remove", "test-id"])
                mock_remove.assert_called_once_with(["test-id"])

    def test_execute_unknown_subcommand(self):
        """Unknown subcommand should show usage."""
        cmd = ModelCommand()
        with patch.object(cmd, "_show_usage") as mock_usage:
            cmd.execute(["invalid"])
            mock_usage.assert_called_once()

    def test_first_model_auto_default(self):
        """The first model added should auto-become default."""
        cmd = ModelCommand()
        with patch.object(cmd, "_registry") as mock_registry:
            mock_registry.count.return_value = 0
            with patch("prysm.commands.model_cmd.ModelEntry"):
                with patch("prysm.commands.model_cmd.console.print"):
                    cmd._add_model(["test", "--name", "Test", "--provider", "local"])
            # Should have set default=True on the entry
            entry = mock_registry.add.call_args[0][0]
            assert entry.default is True
