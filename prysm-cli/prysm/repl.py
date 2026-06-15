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
from prysm.commands.provider_cmd import ProviderCommand
from prysm.commands.runtime_cmd import RuntimeCommand
from prysm.commands.model_cmd import ModelCommand
from prysm.ui.renderer import UIRenderer
from prysm.config.paths import get_config_dir
from prysm.models.registry import ModelRegistry

console = Console()


class PrysmREPL:
    """Interactive REPL for Prysm."""

    def __init__(self, config, system_info=None, verbose=False):
        self.config = config
        self.system_info = system_info
        self.verbose = verbose
        self.running = True

        # Command registry
        self.commands = CommandRegistry()
        exit_cmd = ExitCommand(self)
        self.commands.register(HelpCommand(self))
        self.commands.register(exit_cmd)
        self.commands.register_alias("/quit", exit_cmd)
        self.commands.register(ProviderCommand(self))
        self.commands.register(RuntimeCommand(self, system_info=self.system_info))
        self.commands.register(ModelCommand(self))

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
        # Build banner text
        banner_lines = [
            f"[bold cyan]───  P R Y S M  ───[/bold cyan]",
            f"[italic]Your models. Your runtime. Your code.[/italic]",
            "",
            f"[dim]v{VERSION}[/dim]",
        ]

        # Add system info if available
        if self.system_info:
            banner_lines.append("")
            gpu_str = self.system_info.gpu.summary if self.system_info.has_gpu else "[dim]No GPU[/dim]"
            banner_lines.append(f"[dim]System: {self.system_info.os_name.title()} | {self.system_info.cpu_brand or 'CPU'} ({self.system_info.cpu_cores}C/{self.system_info.cpu_threads}T) | RAM {self.system_info.ram_total_gb:.0f} GB | {gpu_str}[/dim]")

        # Check if there's a default model
        model_registry = ModelRegistry()
        default_model = model_registry.get_default()

        banner_lines.append("")
        if default_model:
            banner_lines.append(f"[green]Default model: {default_model.name}[/green] ([dim]{default_model.provider}[/dim])")
        else:
            banner_lines.append("[yellow]No model loaded.[/yellow] Use [bold]/model list[/bold] to see available")
            banner_lines.append("models, or [bold]/runtime detect[/bold] to check hardware.")

        banner_lines.append("")
        banner_lines.append("Type [bold]/help[/bold] for available commands.")

        banner = Panel(
            Text.from_markup("\n".join(banner_lines)),
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
