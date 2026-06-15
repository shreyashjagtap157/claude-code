"""Shared test fixtures for PRYSM tests."""

import json
import pytest
import tempfile
from pathlib import Path

from prysm.config.loader import PrysmConfig
from prysm.config.paths import get_config_dir


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test isolation."""
    with tempfile.TemporaryDirectory() as tmp:
        yield Path(tmp)


@pytest.fixture
def default_config():
    """Return a default PrysmConfig instance."""
    return PrysmConfig()


@pytest.fixture
def config_file(temp_dir):
    """Create a temporary config file."""
    config_path = temp_dir / "prysm.json"
    config_data = {
        "model": "test-model",
        "runtime": "ollama",
        "ui": {"theme": "dark"},
    }
    with open(config_path, "w") as f:
        json.dump(config_data, f)
    return config_path


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Set mock environment variables."""
    monkeypatch.setenv("PRYSM_MODEL", "env-model")
    monkeypatch.setenv("PRYSM_RUNTIME", "llama-cpp")
    return monkeypatch
