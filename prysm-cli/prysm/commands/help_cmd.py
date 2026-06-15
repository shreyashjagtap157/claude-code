"""The /help slash command."""

from rich.console import Console
from rich.table import Table

from prysm.commands.base import Command

console = Console()


class HelpCommand(Command):
    """Show available commands."""

    def __init__(self, repl=None):
        self._repl = repl

    @property
    def name(self) -> str:
        return "/help"

    @property
    def description(self) -> str:
        return "Show available commands"

    def execute(self, args: list[str], repl=None) -> None:
        """Display all registered commands."""
        repl = repl or self._repl
        if not repl:
            console.print("[red]No REPL context available[/red]")
            return

        table = Table(title="Available Commands", border_style="cyan")
        table.add_column("Command", style="bold cyan", no_wrap=True)
        table.add_column("Description", style="white")

        for cmd in sorted(repl.commands, key=lambda c: c.name):
            table.add_row(cmd.name, cmd.description)

        console.print(table)
        console.print("\n[dim]Use /<command> --help for more info on a specific command.[/dim]")
