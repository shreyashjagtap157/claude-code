"""Base command interface and registry."""

from abc import ABC, abstractmethod
from typing import Any


class Command(ABC):
    """Base class for all slash commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """The command name (e.g., 'help', 'exit')."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Short description shown in /help."""
        ...

    @property
    def usage(self) -> str:
        """Usage string, defaults to /<name>."""
        return f"/{self.name}"

    @abstractmethod
    def execute(self, args: list[str], repl: Any) -> None:
        """Execute the command with given arguments."""
        ...


class CommandRegistry:
    """Registry for all slash commands."""

    def __init__(self):
        self._commands: dict[str, Command] = {}

    def register(self, command: Command) -> None:
        """Register a command."""
        self._commands[command.name] = command

    def register_alias(self, alias_name: str, command: Command) -> None:
        """Register an alias pointing to an existing command."""
        self._commands[alias_name] = command

    def unregister(self, name: str) -> None:
        """Unregister a command."""
        self._commands.pop(name, None)

    def execute(self, name: str, args: list[str], repl: Any = None) -> None:
        """Execute a command by name."""
        cmd = self._commands.get(name)
        if cmd:
            cmd.execute(args, repl)

    def get(self, name: str) -> Command | None:
        """Get a command by name."""
        return self._commands.get(name)

    def __contains__(self, name: str) -> bool:
        return name in self._commands

    def __iter__(self):
        return iter(self._commands.values())

    def __len__(self) -> int:
        return len(self._commands)
