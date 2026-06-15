"""Color theme definitions for terminal UI."""

from dataclasses import dataclass


@dataclass
class Theme:
    """Color theme configuration."""

    name: str
    primary: str = "cyan"
    secondary: str = "blue"
    success: str = "green"
    warning: str = "yellow"
    error: str = "red"
    dim: str = "dim white"
    code: str = "bold white"
    link: str = "underline blue"


LIGHT_THEME = Theme(
    name="light",
    primary="cyan",
    secondary="blue",
    success="green",
    warning="yellow",
    error="red",
    dim="dim white",
    code="bold white",
    link="underline blue",
)

DARK_THEME = Theme(
    name="dark",
    primary="cyan",
    secondary="bright_blue",
    success="bright_green",
    warning="bright_yellow",
    error="bright_red",
    dim="bright_black",
    code="bold bright_white",
    link="underline bright_blue",
)

THEMES = {
    "light": LIGHT_THEME,
    "dark": DARK_THEME,
    "auto": DARK_THEME,  # Default to dark
}


def get_theme(name: str = "auto") -> Theme:
    """Get a theme by name."""
    return THEMES.get(name, DARK_THEME)
