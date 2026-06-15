"""Status bar component for the REPL prompt area."""

from rich.console import Console
from rich.text import Text

console = Console()


class StatusBar:
    """Bottom status bar showing model, runtime, token info."""

    def __init__(self):
        self.model = "No model"
        self.runtime = "auto"
        self.tokens = 0
        self.cost = 0.0

    def update_model(self, model: str) -> None:
        """Update the active model name."""
        self.model = model

    def update_runtime(self, runtime: str) -> None:
        """Update the active runtime."""
        self.runtime = runtime

    def update_tokens(self, tokens: int, cost: float = 0.0) -> None:
        """Update token count and cost."""
        self.tokens = tokens
        self.cost = cost

    def render(self) -> str:
        """Render the status bar as a string."""
        parts = [
            f"[bold cyan]Model:[/bold cyan] {self.model}",
            f"[bold cyan]Runtime:[/bold cyan] {self.runtime}",
        ]
        if self.tokens > 0:
            parts.append(f"[dim]{self.tokens} tokens[/dim]")
        if self.cost > 0:
            parts.append(f"[dim]${self.cost:.4f}[/dim]")

        return " | ".join(parts)
