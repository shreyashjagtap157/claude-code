"""Tests for configuration loading, merging, and saving."""

import json
from pathlib import Path

import pytest

from prysm.config.loader import load_config, save_config, _deep_merge
from prysm.config.schema import PrysmConfig


class TestConfigLoading:
    """Tests for loading configuration."""

    def test_load_default_config(self):
        """Loading with no config file should return defaults."""
        config = load_config()
        assert isinstance(config, PrysmConfig)
        assert config.runtime == "auto"
        assert config.model == ""

    def test_load_from_file(self, config_file):
        """Loading from a config file should read values."""
        config = load_config(config_file)
        assert config.model == "test-model"
        assert config.runtime == "ollama"

    def test_env_var_overrides(self, mock_env_vars):
        """Environment variables should override file values."""
        config = load_config()
        assert config.model == "env-model"
        assert config.runtime == "llama-cpp"

    def test_config_file_overrides_defaults(self, config_file):
        """Config file values should override defaults."""
        config = load_config(config_file)
        assert config.ui.theme == "dark"

    def test_invalid_config_file_uses_defaults(self, temp_dir):
        """An invalid/corrupted config file should fall back to defaults."""
        bad_path = temp_dir / "bad.json"
        bad_path.write_text("{invalid json")
        config = load_config(bad_path)
        assert isinstance(config, PrysmConfig)
        assert config.runtime == "auto"


class TestConfigSave:
    """Tests for saving configuration."""

    def test_save_and_reload(self, temp_dir):
        """Saving config and reloading should preserve values."""
        config_path = temp_dir / "prysm.json"
        config = PrysmConfig(model="saved-model", runtime="ollama")
        save_config(config, config_path)

        reloaded = load_config(config_path)
        assert reloaded.model == "saved-model"
        assert reloaded.runtime == "ollama"


class TestDeepMerge:
    """Tests for the deep merge utility."""

    def test_simple_override(self):
        """Simple key override."""
        base = {"a": 1, "b": 2}
        override = {"b": 3}
        _deep_merge(base, override)
        assert base == {"a": 1, "b": 3}

    def test_nested_merge(self):
        """Nested dictionary merge."""
        base = {"a": {"x": 1, "y": 2}, "b": 3}
        override = {"a": {"y": 99}}
        _deep_merge(base, override)
        assert base == {"a": {"x": 1, "y": 99}, "b": 3}

    def test_new_key_added(self):
        """New keys from override should be added."""
        base = {"a": 1}
        override = {"b": 2}
        _deep_merge(base, override)
        assert base == {"a": 1, "b": 2}

    def test_empty_override(self):
        """Empty override should not modify base."""
        base = {"a": 1, "b": {"c": 2}}
        _deep_merge(base, {})
        assert base == {"a": 1, "b": {"c": 2}}
