"""REPL shell for Prysm using prompt_toolkit."""

import sys
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.styles import Style
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from prysm.version import VERSION
from prysm.commands.base import CommandRegistry
from prysm.commands.help_cmd import HelpCommand
from prysm.commands.exit_cmd import ExitCommand
from prysm.ui.renderer import UIRenderer
from prysm.config.paths import get_config_dir

console = Console()


class PrysmREPL:
    """Interactive REPL for Prysm."""

    def __init__(self, config, verbose=False):
        self.config = config
        self.verbose = verbose
        self.running = True

        # Command registry
        self.commands = CommandRegistry()
        exit_cmd = ExitCommand(self)
        self.commands.register(HelpCommand(self))
        self.commands.register(exit_cmd)
        self.commands.register_alias("/quit", exit_cmd)

        # UI renderer
        self.ui = UIRenderer()

        # Config paths
        self.config_dir = get_config_dir()

        # Prompt session
        history_path = self.config_dir / ".prysm_history" if self.config_dir else None
        if history_path:
            history_path.parent.mkdir(parents=True, exist_ok=True)

        self.session = PromptSession(
            history=FileHistory(str(history_path)) if history_path else None,
            auto_suggest=AutoSuggestFromHistory(),
            style=Style.from_dict({
                "prompt": "ansicyan bold",
            }),
        )

    def run(self):
        """Start the REPL loop."""
        self._show_banner()

        while self.running:
            try:
                user_input = self.session.prompt(
                    "❯ ",
                    vi_mode=True,
                )
            except (KeyboardInterrupt, EOFError):
                self.running = False
                console.print("\n[yellow]Goodbye![/yellow]")
                break

            if not user_input.strip():
                continue

            # Handle slash commands
            if user_input.strip().startswith("/"):
                self._handle_command(user_input.strip())
            else:
                self._handle_message(user_input.strip())

    def _show_banner(self):
        """Show the startup banner."""
        banner = Panel(
            Text.from_markup(
                "[bold cyan]───  P R Y S M  ───[/bold cyan]\n"
                "[italic]Your models. Your runtime. Your code.[/italic]\n\n"
                f"[dim]v{VERSION}[/dim]\n\n"
                "[yellow]No model loaded.[/yellow] Use [bold]/model list[/bold] to see available\n"
                "models, or [bold]/runtime[/bold] to check recommended runtime.\n\n"
                "Type [bold]/help[/bold] for available commands."
            ),
            title="Welcome",
            border_style="cyan",
        )
        console.print(banner)

    def _handle_command(self, cmd_line: str):
        """Handle a slash command."""
        parts = cmd_line.split()
        cmd_name = parts[0].lower()

        if cmd_name in self.commands:
            self.commands.execute(cmd_name, parts[1:])
        else:
            console.print(f"[red]Unknown command: {cmd_name}[/red]")
            console.print("Type [bold]/help[/bold] for available commands.")

    def _handle_message(self, message: str):
        """Handle a free-form message (no agent loop in Phase 0)."""
        console.print("[dim]Agent loop not yet implemented. [/dim]")
        console.print("[dim]This is Phase 0 — stay tuned for Phases 1-5![/dim]")

    def stop(self):
        """Stop the REPL."""
        self.running = False
