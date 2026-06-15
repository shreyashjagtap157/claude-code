"""Configuration loading and merging."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

from prysm.config.schema import PrysmConfig
from prysm.config.paths import get_default_config_path, ensure_dirs

logger = logging.getLogger(__name__)


DEFAULT_CONFIG = {
    "model": "",
    "runtime": "auto",
    "ui": {
        "theme": "auto",
        "streaming": True,
        "show_thinking": True,
        "status_bar": True,
    },
    "agent": {
        "max_turns": 25,
        "context_window": 8192,
        "auto_summarize": True,
    },
    "permissions": {
        "ask": ["Bash"],
        "deny": [],
        "allow": [],
        "bash_allowlist": [],
    },
    "sandbox": {
        "enabled": False,
        "auto_allow_bash_if_sandboxed": False,
        "allowed_domains": [],
        "read_only_paths": [],
        "max_bash_timeout": 30,
        "max_bash_memory_mb": 512,
    },
}


def load_config(config_path: Optional[Path] = None) -> PrysmConfig:
    """Load configuration with priority: defaults → user file → env vars.

    Args:
        config_path: Optional explicit path to config file.

    Returns:
        Merged PrysmConfig instance.
    """
    ensure_dirs()

    # 1. Start with defaults
    config_data = dict(DEFAULT_CONFIG)

    # 2. Merge user config file
    if config_path is None:
        config_path = get_default_config_path()

    if config_path.exists():
        try:
            with open(config_path, "r") as f:
                user_config = json.load(f)
            _deep_merge(config_data, user_config)
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid config file at {config_path}: {e}. Using defaults.")
        except OSError as e:
            logger.warning(f"Cannot read config file at {config_path}: {e}. Using defaults.")

    # 3. Environment variable overrides
    _apply_env_overrides(config_data)

    return PrysmConfig(**config_data)


def _deep_merge(base: dict, override: dict) -> None:
    """Recursively merge override dict into base dict."""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _apply_env_overrides(config_data: dict) -> None:
    """Apply PRYSM_* environment variable overrides."""
    if model := os.environ.get("PRYSM_MODEL"):
        config_data["model"] = model
    if runtime := os.environ.get("PRYSM_RUNTIME"):
        config_data["runtime"] = runtime


def save_config(config: PrysmConfig, config_path: Optional[Path] = None) -> None:
    """Save configuration to file."""
    if config_path is None:
        config_path = get_default_config_path()

    ensure_dirs()
    with open(config_path, "w") as f:
        json.dump(config.model_dump(), f, indent=2)
