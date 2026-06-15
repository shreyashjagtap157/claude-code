"""The /runtime slash command — detect and display system hardware information."""

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from prysm.commands.base import Command
from prysm.system import SystemDetector, SystemInfo

console = Console()


class RuntimeCommand(Command):
    """Detect and display system hardware information."""

    def __init__(self, repl=None, system_info=None):
        self._repl = repl
        self._detected_system = system_info

    @property
    def name(self) -> str:
        return "/runtime"

    @property
    def description(self) -> str:
        return "Detect and display system hardware information"

    @property
    def detected_system(self) -> SystemInfo:
        """Run system detection if not already done, return cached result."""
        if self._detected_system is None:
            detector = SystemDetector()
            self._detected_system = detector.detect()
        return self._detected_system

    def execute(self, args: list[str], repl=None) -> None:
        """Execute the /runtime command with subcommands."""
        if not args:
            self._show_detect()
            return

        subcommand = args[0].lower()

        if subcommand == "detect":
            self._show_detect()
        elif subcommand == "info":
            self._show_info(args[1:] if len(args) > 1 else [])
        elif subcommand == "summary":
            self._show_summary()
        elif subcommand in ("--help", "-h"):
            self._show_usage()
        else:
            console.print(f"[red]Unknown subcommand: {subcommand}[/red]")
            self._show_usage()

    def _show_usage(self) -> None:
        """Show usage info."""
        console.print("[bold cyan]/runtime[/bold cyan] — Detect and display system hardware")
        console.print()
        console.print("  [bold]Subcommands:[/bold]")
        console.print("    [cyan]detect[/cyan]                  Run system detection (default)")
        console.print("    [cyan]summary[/cyan]                 Show one-line system summary")
        console.print("    [cyan]info[/cyan]                    Show detailed system info")
        console.print()
        console.print("  [dim]Examples:[/dim]")
        console.print("    [green]/runtime[/green]")
        console.print("    [green]/runtime detect[/green]")
        console.print("    [green]/runtime summary[/green]")

    def _show_detect(self) -> None:
        """Run system detection and display results."""
        console.print("[bold cyan]Detecting system hardware...[/bold cyan]")
        system = self.detected_system

        # OS & Architecture
        console.print()
        console.print("[bold]OS & Architecture[/bold]")
        os_table = Table(show_header=False, border_style="dim")
        os_table.add_column("Key", style="bold")
        os_table.add_column("Value")
        os_table.add_row("Operating System", f"{system.os_name.title()} {system.os_version}")
        os_table.add_row("Architecture", system.architecture)
        if system.is_wsl:
            os_table.add_row("Environment", "[yellow]WSL[/yellow]")
        if system.is_docker:
            os_table.add_row("Environment", "[yellow]Docker[/yellow]")
        if system.is_remote:
            os_table.add_row("Session", "[yellow]Remote (SSH)[/yellow]")
        console.print(os_table)

        # CPU
        console.print()
        console.print("[bold]CPU[/bold]")
        cpu_table = Table(show_header=False, border_style="dim")
        cpu_table.add_column("Key", style="bold")
        cpu_table.add_column("Value")
        cpu_table.add_row("Model", system.cpu_brand or "Unknown")
        cpu_table.add_row("Cores", f"{system.cpu_cores}C / {system.cpu_threads}T")
        if system.cpu_features:
            feat = ", ".join(f for f in system.cpu_features[:10])
            if len(system.cpu_features) > 10:
                feat += "..."
            cpu_table.add_row("Features", feat)
        console.print(cpu_table)

        # RAM
        console.print()
        console.print("[bold]Memory[/bold]")
        ram_table = Table(show_header=False, border_style="dim")
        ram_table.add_column("Key", style="bold")
        ram_table.add_column("Value")
        ram_table.add_row("Total", f"{system.ram_total_gb:.1f} GB")
        ram_table.add_row("Available", f"{system.ram_available_gb:.1f} GB")
        console.print(ram_table)

        # GPU
        console.print()
        console.print("[bold]GPU[/bold]")
        gpu_table = Table(show_header=False, border_style="dim")
        gpu_table.add_column("Key", style="bold")
        gpu_table.add_column("Value")
        if system.has_gpu:
            gpu_table.add_row("Detected", "[green]Yes[/green]")
            gpu_table.add_row("Vendor", system.gpu.vendor or "Unknown")
            gpu_table.add_row("Model", system.gpu.name or "Unknown")
            if system.gpu.vram_gb:
                gpu_table.add_row("VRAM", f"{system.gpu.vram_gb:.0f} GB")
            if system.gpu.driver:
                gpu_table.add_row("Driver", system.gpu.driver)
            if system.gpu.cuda_version:
                gpu_table.add_row("CUDA", system.gpu.cuda_version)
            backends = []
            if system.gpu.metal_supported:
                backends.append("Metal")
            if system.gpu.rocm_supported:
                backends.append("ROCm")
            if system.gpu.vulkan_supported:
                backends.append("Vulkan")
            if backends:
                gpu_table.add_row("Backends", ", ".join(backends))
        else:
            gpu_table.add_row("Detected", "[yellow]No GPU detected[/yellow]")
            gpu_table.add_row("Runtime", "CPU mode (Ollama or llama.cpp)")
        console.print(gpu_table)

        console.print()
        console.print("[dim]Tip: Use [green]/runtime summary[/green] for a one-line overview.[/dim]")

    def _show_summary(self) -> None:
        """Show a one-line system summary."""
        system = self.detected_system
        console.print(f"[bold cyan]System:[/bold cyan] {system.summary}")

    def _show_info(self, args: list[str]) -> None:
        """Show detailed info on a specific subsystem."""
        if args:
            subsystem = args[0].lower()
            if subsystem == "gpu":
                console.print(f"[bold]GPU:[/bold] {self.detected_system.gpu.summary}")
            elif subsystem == "cpu":
                system = self.detected_system
                console.print(f"[bold]CPU:[/bold] {system.cpu_brand} ({system.cpu_cores}C/{system.cpu_threads}T)")
            elif subsystem == "ram":
                system = self.detected_system
                console.print(f"[bold]RAM:[/bold] {system.ram_total_gb:.1f} GB total, {system.ram_available_gb:.1f} GB available")
            else:
                console.print(f"[yellow]Unknown subsystem: {subsystem}[/yellow]")
                console.print("[dim]Available: gpu, cpu, ram[/dim]")
        else:
            console.print(self.detected_system.summary)
