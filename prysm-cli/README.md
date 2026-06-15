# PRYSM 🔮

**Your models. Your runtime. Your code.**

Prysm is a terminal-first AI coding agent that runs **any model** — local GGUF files, Ollama, or cloud APIs from 75+ providers. One CLI, one plugin ecosystem, zero vendor lock-in.

## Features

- **Any Model**: Local GGUF, Ollama, OpenAI, Anthropic, OpenRouter, and any OpenAI-compatible endpoint
- **Hardware-Aware Runtimes**: Auto-detects CPU, CUDA, Metal, ROCm, Vulkan — picks the best backend
- **Slash Commands**: `/model`, `/runtime`, `/provider`, `/session`, `/help`
- **Plugin System**: Backward compatible with Claude Code plugins
- **Cross-Platform**: Windows, macOS, Linux
- **Open Source**: MIT license

## Quick Start

```bash
# Install
pip install prysm-cli

# Or with local model support
pip install prysm-cli[cpu]
pip install prysm-cli[cuda]   # NVIDIA GPU
pip install prysm-cli[metal]  # Apple Silicon

# Start
prysm
```

## Status

🚧 **Phase 0 — Early Development** 🚧

This project is in early development. The REPL shell, configuration system, and command infrastructure are being built.

### Current Phase: 0 (Project Scaffolding)
- [x] Project structure and build system
- [x] CLI entry point with argument parsing
- [x] REPL shell (prompt_toolkit)
- [x] Configuration system (Pydantic models, JSON loading, env overrides)
- [x] Slash command infrastructure (/help, /exit)
- [x] Terminal UI components (renderer, status bar, themes)
- [x] SQLite state database (sessions, messages, usage)
- [ ] System detection layer (planned Phase 1)
- [ ] Model registry (planned Phase 2)

## Development

```bash
# Clone and install in development mode
git clone https://github.com/shreyashjagtap157/claude-code.git
cd prysm-cli
pip install -e ".[development]"

# Run tests
pytest

# Type check
mypy prysm/

# Lint
ruff check prysm/
```

## License

MIT
