"""Rich-based terminal UI renderer."""

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.text import Text

console = Console()


class UIRenderer:
    """Handles terminal output rendering with Rich."""

    def info(self, message: str) -> None:
        """Display an info message."""
        console.print(f"[blue]ℹ[/blue] {message}")

    def success(self, message: str) -> None:
        """Display a success message."""
        console.print(f"[green]✓[/green] {message}")

    def warning(self, message: str) -> None:
        """Display a warning message."""
        console.print(f"[yellow]⚠[/yellow] {message}")

    def error(self, message: str) -> None:
        """Display an error message."""
        console.print(f"[red]✗[/red] {message}")

    def panel(self, title: str, content: str, border_style: str = "cyan") -> None:
        """Display a panel with title."""
        panel = Panel(
            Text.from_markup(content),
            title=title,
            border_style=border_style,
        )
        console.print(panel)

    def table(self, title: str, columns: list[str], rows: list[list[str]]) -> None:
        """Display a table."""
        table = Table(title=title, border_style="cyan")
        for col in columns:
            table.add_column(col, style="bold cyan" if col == columns[0] else "white")
        for row in rows:
            table.add_row(*row)
        console.print(table)

    def markdown(self, content: str) -> None:
        """Display markdown content."""
        md = Markdown(content)
        console.print(md)

    def stream(self, text: str) -> None:
        """Stream text to the console (used for token-by-token output)."""
        console.print(text, end="")
