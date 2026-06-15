"""The /exit (and /quit) slash command."""

import sys
from rich.console import Console
from prysm.commands.base import Command

console = Console()


class ExitCommand(Command):
    """Exit the REPL."""

    def __init__(self, repl=None):
        self._repl = repl

    @property
    def name(self) -> str:
        return "/exit"

    @property
    def description(self) -> str:
        return "Exit Prysm"

    def execute(self, args: list[str], repl=None) -> None:
        """Exit the REPL gracefully."""
        active_repl = repl or self._repl
        if active_repl:
            active_repl.stop()
        else:
            console.print("[yellow]Goodbye![/yellow]")
            sys.exit(0)
