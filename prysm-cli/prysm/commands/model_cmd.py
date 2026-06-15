"""The /model slash command — manage models (list, add, remove, info)."""

from rich.console import Console
from rich.table import Table

from prysm.commands.base import Command
from prysm.models.registry import ModelEntry, ModelRegistry

console = Console()


class ModelCommand(Command):
    """Manage models — list, add, remove, show info."""

    def __init__(self, repl=None):
        self._repl = repl
        self._registry = ModelRegistry()

    @property
    def name(self) -> str:
        return "/model"

    @property
    def description(self) -> str:
        return "Manage models (list, add, remove, info)"

    def execute(self, args: list[str], repl=None) -> None:
        """Execute the /model command with subcommands."""
        if not args:
            self._list_models()
            return

        subcommand = args[0].lower()

        if subcommand == "list":
            self._list_models()
        elif subcommand == "add":
            self._add_model(args[1:])
        elif subcommand == "remove":
            self._remove_model(args[1:])
        elif subcommand == "info":
            self._show_model_info(args[1:])
        elif subcommand in ("--help", "-h"):
            self._show_usage()
        else:
            console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
            self._show_usage()

    def _show_usage(self) -> None:
        """Show usage info."""
        console.print("[bold cyan]/model[/bold cyan] — Manage models")
        console.print()
        console.print("  [bold]Subcommands:[/bold]")
        console.print("    [cyan]list[/cyan]                           List all registered models")
        console.print("    [cyan]add[/cyan] <id> --name NAME ...       Register a new model")
        console.print("    [cyan]remove[/cyan] <model-id>              Remove a model")
        console.print("    [cyan]info[/cyan] <model-id>                Show model details")
        console.print()
        console.print("  [dim]Examples:[/dim]")
        console.print("    [green]/model list[/green]")
        console.print("    [green]/model add gpt-4o --name GPT-4o --provider openai[/green]")
        console.print("    [green]/model info gpt-4o[/green]")

    def _list_models(self) -> None:
        """List all registered models."""
        models = self._registry.list_all()

        if not models:
            console.print("[yellow]No models registered.[/yellow]")
            console.print("[dim]Use [green]/model add <id> --name NAME --provider PROVIDER[/green] to add one.[/dim]")
            return

        table = Table(title="Registered Models", border_style="cyan")
        table.add_column("ID", style="bold cyan")
        table.add_column("Name", style="white")
        table.add_column("Provider", style="white")
        table.add_column("Runtime", style="dim")
        table.add_column("Context", style="dim")
        table.add_column("Default", style="white")

        for m in models:
            is_default = "[green]✓[/green]" if m.default else ""
            table.add_row(
                m.id,
                m.name,
                m.provider,
                m.runtime or "auto",
                str(m.context_length),
                is_default,
            )

        console.print(table)
        console.print()
        console.print(f"[dim]Total: {len(models)} model(s)[/dim]")

    def _add_model(self, args: list[str]) -> None:
        """Add a model to the registry."""
        if not args:
            console.print("[red]Usage: /model add <id> --name NAME --provider PROVIDER [--runtime RUNTIME] [--context-length N][/red]")
            return

        model_id = args[0].lower()

        # Parse optional flags
        name = None
        provider = None
        runtime = None
        context_length = 4096
        api_base = None

        i = 1
        while i < len(args):
            if args[i] == "--name" and i + 1 < len(args):
                name = args[i + 1]
                i += 2
            elif args[i] == "--provider" and i + 1 < len(args):
                provider = args[i + 1].lower()
                i += 2
            elif args[i] == "--runtime" and i + 1 < len(args):
                runtime = args[i + 1].lower()
                i += 2
            elif args[i] == "--context-length" and i + 1 < len(args):
                try:
                    context_length = int(args[i + 1])
                except ValueError:
                    console.print(f"[red]Invalid context-length: {args[i + 1]}[/red]")
                    return
                i += 2
            elif args[i] == "--api-base" and i + 1 < len(args):
                api_base = args[i + 1]
                i += 2
            else:
                console.print(f"[red]Unknown flag: {args[i]}[/red]")
                return

        if not name:
            name = model_id
        if not provider:
            provider = "local"

        # Create the model entry
        entry = ModelEntry(
            id=model_id,
            name=name,
            provider=provider,
            runtime=runtime,
            context_length=context_length,
            api_base=api_base,
        )

        # If this is the first model, set as default
        if self._registry.count() == 0:
            entry.default = True

        self._registry.add(entry)
        console.print(f"[green]✓[/green] Model [bold]{model_id}[/bold] added ({provider}, {name}).")

        if entry.default:
            console.print("  [dim]Set as default (first model).[/dim]")

    def _remove_model(self, args: list[str]) -> None:
        """Remove a model from the registry."""
        if not args:
            console.print("[red]Usage: /model remove <model-id>[/red]")
            return

        model_id = args[0].lower()
        model = self._registry.get(model_id)

        if not model:
            console.print(f"[red]Model not found: {model_id}[/red]")
            return

        was_default = model.default
        self._registry.remove(model_id)
        console.print(f"[green]✓[/green] Model [bold]{model_id}[/bold] removed.")

        # If the default was removed, set the next available as default
        if was_default:
            remaining = self._registry.list_all()
            if remaining:
                self._registry.set_default(remaining[0].id)
                console.print(f"  [dim]Default changed to: {remaining[0].id}[/dim]")

    def _show_model_info(self, args: list[str]) -> None:
        """Show detailed info about a model."""
        if not args:
            console.print("[red]Usage: /model info <model-id>[/red]")
            return

        model_id = args[0].lower()
        model = self._registry.get(model_id)

        if not model:
            console.print(f"[red]Model not found: {model_id}[/red]")
            return

        table = Table(title=f"Model: {model.id}", border_style="cyan")
        table.add_column("Property", style="bold")
        table.add_column("Value")

        table.add_row("ID", model.id)
        table.add_row("Name", model.name)
        table.add_row("Provider", model.provider)
        table.add_row("Runtime", model.runtime or "auto")
        table.add_row("Context Length", str(model.context_length))
        table.add_row("Capabilities", ", ".join(model.capabilities))
        table.add_row("Default", "[green]✓[/green]" if model.default else "")
        table.add_row("Loaded", "[green]loaded[/green]" if model.loaded else "[dim]unloaded[/dim]")
        if model.path:
            table.add_row("Path", model.path)
        if model.api_base:
            table.add_row("API Base", model.api_base)
        if model.model_name:
            table.add_row("Model Name", model.model_name)
        if model.hf_repo:
            table.add_row("HF Repo", model.hf_repo)
        if model.runtime_params:
            table.add_row("Runtime Params", str(model.runtime_params))
        if model.description:
            table.add_row("Description", model.description)

        console.print(table)
