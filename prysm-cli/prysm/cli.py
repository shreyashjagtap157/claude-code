"""Main CLI entry point for Prysm."""

import logging
import sys
import click
from pathlib import Path

from prysm.version import VERSION
from prysm.config.paths import get_config_dir
from prysm.config.loader import load_config
from prysm.repl import PrysmREPL

logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")


@click.command()
@click.option("--config", "-c", default=None, help="Path to config file")
@click.option("--model", "-m", default=None, help="Model to use (e.g., ollama/llama3)")
@click.option("--runtime", "-r", default=None, help="Runtime override (auto-detected by default)")
@click.option("--plugin-dir", default=None, help="Plugin directory")
@click.option("--verbose", "-v", is_flag=True, help="Verbose logging")
@click.option("--version", is_flag=True, help="Show version")
def main(config, model, runtime, plugin_dir, verbose, version):
    """Prysm — AI coding agent for any model, any runtime.

    Your models. Your runtime. Your code.
    """
    if version:
        click.echo(f"prysm {VERSION} — Your models. Your runtime. Your code.")
        sys.exit(0)

    # Resolve config
    config_path = Path(config) if config else None

    # Load configuration
    cfg = load_config(config_path)

    # Apply CLI overrides
    if model:
        cfg.model = model
    if runtime:
        cfg.runtime = runtime

    # Start REPL
    repl = PrysmREPL(config=cfg, verbose=verbose)
    try:
        repl.run()
    except KeyboardInterrupt:
        click.echo("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        if verbose:
            import traceback
            click.echo(f"Fatal error: {e}", err=True)
            traceback.print_exc()
        else:
            click.echo(f"Fatal error: {e}. Run with --verbose for details.", err=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
