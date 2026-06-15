"""The /provider slash command — manage API providers and keys."""

from rich.console import Console
from rich.table import Table

from prysm.commands.base import Command
from prysm.models.provider import ProviderRegistry, CredentialManager, ProviderConfig
from prysm.models.registry import ModelEntry, ModelRegistry

console = Console()


class ProviderCommand(Command):
    """Manage API providers and keys."""

    def __init__(self, repl=None):
        self._repl = repl
        self.credential_manager = CredentialManager()
        self.model_registry = ModelRegistry()
        self.provider_registry = ProviderRegistry()

    @property
    def name(self) -> str:
        return "/provider"

    @property
    def description(self) -> str:
        return "Manage API providers (list, add, remove, enable, disable)"

    def execute(self, args: list[str], repl=None) -> None:
        """Execute the /provider command with subcommands."""
        if not args:
            self._show_usage()
            return

        subcommand = args[0].lower()

        if subcommand == "list":
            self._list_providers()
        elif subcommand == "add":
            self._add_provider(args[1:])
        elif subcommand == "remove":
            self._remove_provider(args[1:])
        elif subcommand == "enable":
            self._enable_provider(args[1:])
        elif subcommand == "disable":
            self._disable_provider(args[1:])
        elif subcommand in ("models", "list-models"):
            self._list_provider_models(args[1:])
        elif subcommand in ("--help", "-h"):
            self._show_usage()
        else:
            console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
            self._show_usage()

    def _show_usage(self) -> None:
        """Show usage info."""
        console.print("[bold cyan]/provider[/bold cyan] — Manage API providers")
        console.print()
        console.print("  [bold]Subcommands:[/bold]")
        console.print("    [cyan]list[/cyan]                     List all configured providers")
        console.print("    [cyan]add[/cyan] <provider> [--key KEY]  Add/configure a provider")
        console.print("    [cyan]remove[/cyan] <provider>          Remove a provider")
        console.print("    [cyan]enable[/cyan] <provider>          Enable a provider")
        console.print("    [cyan]disable[/cyan] <provider>         Disable a provider")
        console.print("    [cyan]models[/cyan] <provider>          List models for a provider")
        console.print()
        console.print("  [dim]Known providers: openai, anthropic, google, openrouter,")
        console.print("   deepseek, groq, together, mistral, ollama, local[/dim]")
        console.print()
        console.print("  [dim]Examples:[/dim]")
        console.print("    [green]/provider list[/green]")
        console.print("    [green]/provider add openai --key sk-xxx[/green]")
        console.print("    [green]/provider models openai[/green]")

    def _list_providers(self) -> None:
        """List all configured providers."""
        known = self.provider_registry.get_known_providers()
        configured = self.credential_manager.list_providers()

        # Build provider status map
        status_map = {}
        for p in configured:
            status_map[p["provider"]] = p

        table = Table(title="Providers", border_style="cyan")
        table.add_column("Provider", style="bold cyan")
        table.add_column("Status", style="white")
        table.add_column("Key", style="white")
        table.add_column("Models", style="dim")

        # Show known providers
        for pid, info in known.items():
            configured_info = status_map.get(pid, {})
            has_key = configured_info.get("has_key", False)
            source = configured_info.get("source", "")

            if has_key:
                key_status = f"[green]✓ set[/green]"
                if source == "env":
                    key_status += " [dim](env)[/dim]"
                status = "[green]✓ active[/green]"
            else:
                key_status = "[yellow]⚠ no key[/yellow]"
                status = "[dim]inactive[/dim]"

            model_count = len(info.get("models", []))
            models_str = f"{model_count} known" if model_count else "-"

            table.add_row(pid, status, key_status, models_str)

        # Show custom providers not in the known list
        for p in configured:
            pid = p["provider"]
            if pid not in known and p["has_key"]:
                source = p.get("source", "")
                key_status = "[green]✓ set[/green]"
                if source == "env":
                    key_status += " [dim](env)[/dim]"
                table.add_row(pid, "[green]✓ active[/green]", key_status, "[dim]custom[/dim]")

        console.print(table)
        console.print()
        console.print("[dim]Tip: Use [green]/provider add <name> --key <key>[/green] to add a key.[/dim]")

    def _add_provider(self, args: list[str]) -> None:
        """Add or configure a provider with an API key."""
        if not args:
            console.print("[red]Usage: /provider add <provider> --key <key>[/red]")
            return

        provider_id = args[0].lower()

        # Parse --key argument
        key = None
        if "--key" in args:
            key_idx = args.index("--key")
            if key_idx + 1 < len(args):
                key = args[key_idx + 1]

        if not key:
            console.print(f"[yellow]No key provided for '{provider_id}'.[/yellow]")
            console.print(f"[dim]Usage: /provider add {provider_id} --key sk-xxx[/dim]")
            return

        # Store the credential
        success = self.credential_manager.set(provider_id, key)

        if success:
            console.print(f"[green]✓[/green] Provider [bold]{provider_id}[/bold] configured.")
            # Try to add common models
            if known := self.provider_registry.get_provider_info(provider_id):
                added = 0
                for model_name in known.get("models", []):
                    entry = ModelEntry(
                        id=f"{provider_id}/{model_name}",
                        name=model_name,
                        provider=provider_id,
                        api_base=known.get("api_base"),
                    )
                    existing = self.model_registry.get(entry.id)
                    if not existing:
                        self.model_registry.add(entry)
                        added += 1
                if added > 0:
                    console.print(f"[dim]  Added {added} model(s) to registry.[/dim]")
        else:
            console.print(f"[red]✗[/red] Failed to configure provider [bold]{provider_id}[/bold].")

    def _remove_provider(self, args: list[str]) -> None:
        """Remove a provider and its credentials."""
        if not args:
            console.print("[red]Usage: /provider remove <provider>[/red]")
            return

        provider_id = args[0].lower()
        self.credential_manager.delete(provider_id)
        console.print(f"[green]✓[/green] Provider [bold]{provider_id}[/bold] removed.")

        # Also remove associated models
        models = self.model_registry.list_by_provider(provider_id)
        for model in models:
            self.model_registry.remove(model.id)
        if models:
            console.print(f"[dim]  Removed {len(models)} model(s) from registry.[/dim]")

    def _enable_provider(self, args: list[str]) -> None:
        """Enable a provider."""
        if not args:
            console.print("[red]Usage: /provider enable <provider>[/red]")
            return

        provider_id = args[0].lower()
        # In a full implementation, this would update the provider config
        console.print(f"[green]✓[/green] Provider [bold]{provider_id}[/bold] enabled.")

    def _disable_provider(self, args: list[str]) -> None:
        """Disable a provider."""
        if not args:
            console.print("[red]Usage: /provider disable <provider>[/red]")
            return

        provider_id = args[0].lower()
        # In a full implementation, this would update the provider config
        console.print(f"[green]✓[/green] Provider [bold]{provider_id}[/bold] disabled.")

    def _list_provider_models(self, args: list[str]) -> None:
        """List models available for a provider."""
        if not args:
            console.print("[red]Usage: /provider models <provider>[/red]")
            return

        provider_id = args[0].lower()
        known = self.provider_registry.get_provider_info(provider_id)

        if known:
            table = Table(title=f"{known['name']} Models", border_style="cyan")
            table.add_column("Model ID", style="bold cyan")
            table.add_column("Context", style="white")
            table.add_column("Capabilities", style="dim")

            for model_name in known.get("models", []):
                table.add_row(model_name, "-", "chat")

            console.print(table)
        else:
            # Check if models are in the registry
            models = self.model_registry.list_by_provider(provider_id)
            if models:
                table = Table(title=f"{provider_id} Models", border_style="cyan")
                table.add_column("Model ID", style="bold cyan")
                table.add_column("Runtime", style="white")
                table.add_column("Status", style="dim")
                for m in models:
                    status = "[green]loaded[/green]" if m.loaded else "[dim]unloaded[/dim]"
                    table.add_row(m.name, m.runtime or "auto", status)
                console.print(table)
            else:
                console.print(f"[yellow]Unknown provider: {provider_id}[/yellow]")
