# PRYSM 🔮

**Your models. Your runtime. Your code.**

Prysm is a terminal-first AI coding agent that runs **any model** — local GGUF files, Ollama, or cloud APIs from 75+ providers. One CLI, one plugin ecosystem, zero vendor lock-in.

## Features

- **Any Model**: Local GGUF, Ollama, OpenAI, Anthropic, OpenRouter, and any OpenAI-compatible endpoint
- **Hardware-Aware Runtimes**: Auto-detects CPU, CUDA, Metal, ROCm, Vulkan — picks the best backend
- **Slash Commands**: `/help`, `/model`, `/runtime`, `/provider`, `/exit`
- **Plugin System**: Backward compatible with Claude Code plugins (planned)
- **Cross-Platform**: Windows, macOS, Linux
- **Open Source**: MIT license

## Quick Start

```bash
# Install from source
cd prysm-cli
pip install -e ".[development]"

# Start the REPL
prysm
```

You'll be greeted with a welcome banner showing your system hardware and a prompt to get started.

## Slash Commands

| Command | Description |
|---|---|
| `/help` | Show all available commands |
| `/runtime [detect\|summary\|info]` | Detect and display system hardware (OS, CPU, GPU, RAM) |
| `/model [list\|add\|remove\|info]` | Manage registered models |
| `/provider [list\|add\|remove\|models]` | Configure API providers and credentials |
| `/exit` or `/quit` | Exit the REPL |

## Status

### ✅ Phase 0 — Project Scaffolding & CLI Shell
- [x] Project structure and build system (`pyproject.toml`)
- [x] CLI entry point with Click argument parsing (`--version`, `--model`, `--runtime`)
- [x] REPL shell with prompt_toolkit (history, auto-suggest, vi mode)
- [x] Configuration system (Pydantic models, JSON loading, env overrides)
- [x] Slash command framework (`/help`, `/exit`, `/quit`)
- [x] Terminal UI components (Rich renderer, status bar, themes)
- [x] SQLite state database (sessions, messages, usage tracking)

### ✅ Phase 1 — System/Runtime Detection Layer
- [x] OS detection: Windows, macOS, Linux (version and build)
- [x] Architecture detection: x86_64, arm64, x86, armv7
- [x] CPU detection: brand, cores, threads, features (AVX, Neon via py-cpuinfo)
- [x] RAM detection: total and available (via psutil)
- [x] GPU detection: NVIDIA CUDA (nvidia-smi), Apple Metal, AMD ROCm, Vulkan
- [x] Environment detection: WSL, Docker, remote/SSH session

### ✅ Phase 2 — Provider & Model Registry
- [x] Model registry with JSON persistence (`models.json`)
- [x] Model CRUD: add, remove, list, update, set default
- [x] Provider catalog: 8 known providers across 2 tiers
- [x] Credential manager: OS keyring → env vars → file fallback
- [x] `/provider` command: list, add, remove, enable, disable, models
- [x] `/model` command: list, add, remove, info
- [x] `/runtime` command: detect, summary, info

## Architecture

```
CLI (click) → SystemDetector → SystemInfo
                                    ↓
REPL (prompt_toolkit) ←─────────── PrysmREPL
  ├── /help       → HelpCommand
  ├── /runtime    → RuntimeCommand → SystemDetector (system info)
  ├── /provider   → ProviderCommand → CredentialManager + ProviderRegistry
  ├── /model      → ModelCommand → ModelRegistry (JSON file)
  └── /exit       → ExitCommand
```

## Test Suite

```bash
cd prysm-cli
pytest           # 171 tests, all passing
```

| Test File | Tests | Coverage |
|---|---|---|
| `test_cli.py` | 2 | CLI entry point |
| `test_config.py` | 8 | Config loading, merging, saving |
| `test_commands.py` | 13 | CommandRegistry, HelpCommand, ExitCommand |
| `test_repl.py` | 18 | REPL init, banner, command dispatch, stop |
| `test_detector.py` | 45 | SystemInfo, GPUInfo, SystemDetector (all OS/CPU/RAM/GPU) |
| `test_runtime_cmd.py` | 15 | /runtime command subcommands |
| `test_model_cmd.py` | 12 | /model command CRUD |
| `test_provider.py` | 43 | ModelEntry, ModelRegistry, CredentialManager |
| **Total** | **171** | **All passing** |

## Development

```bash
# Clone and install in development mode
git clone https://github.com/shreyashjagtap157/claude-code.git
cd prysm-cli
pip install -e ".[development]"

# Run all tests
pytest

# Run specific test file
pytest tests/test_detector.py -v

# Type check
mypy prysm/

# Lint
ruff check prysm/
```

## License

MIT
