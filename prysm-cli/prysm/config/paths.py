"""Cross-platform configuration path discovery."""

from pathlib import Path
from platformdirs import PlatformDirs

_DIRS = PlatformDirs("prysm", "prysm-cli")


def get_config_dir() -> Path:
    """Get the user-level configuration directory.

    Returns:
        Path: ~/.config/prysm/ on Linux,
              ~/Library/Application Support/prysm/ on macOS,
              %APPDATA%/prysm/ on Windows.
    """
    return Path(_DIRS.user_config_dir)


def get_data_dir() -> Path:
    """Get the user-level data directory (for state.db)."""
    return Path(_DIRS.user_data_dir)


def get_cache_dir() -> Path:
    """Get the user-level cache directory."""
    return Path(_DIRS.user_cache_dir)


def get_default_config_path() -> Path:
    """Get the default config file path."""
    return get_config_dir() / "prysm.json"


def get_models_path() -> Path:
    """Get the models registry file path."""
    return get_config_dir() / "models.json"


def get_providers_path() -> Path:
    """Get the providers config file path."""
    return get_config_dir() / "providers.json"


def get_state_db_path() -> Path:
    """Get the SQLite state database path."""
    return get_data_dir() / "state.db"


def ensure_dirs() -> None:
    """Ensure all config/data/cache directories exist."""
    get_config_dir().mkdir(parents=True, exist_ok=True)
    get_data_dir().mkdir(parents=True, exist_ok=True)
    get_cache_dir().mkdir(parents=True, exist_ok=True)
