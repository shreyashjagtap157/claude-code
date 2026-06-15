# PRYSM — Local & Cloud LLM CLI Agent

**Architecture & Exhaustive Implementation Plan (Refined — v2.0)**

> *A prism for language models: one interface, any runtime, any provider, any model.*

---

## Revision History

| Version | Date | Changes |
|---|---|---|
| v1.0 | 2025-06-01 | Initial plan |
| v1.1 | 2025-06-15 | Round 1 refinement: 6 expert personas (Solutions Architect, Security Architect, DevOps Engineer, Product Manager, Performance Engineer, Community Manager). Fixes: dependency corrections, credential storage hardening, async/sync architecture, CI/CD plan, prysm init flow, timeline revision, error handling layer, security sandbox redesign. |
| v1.2 | 2025-06-15 | Round 2 refinement: 4 expert personas (QA/Test Engineer, Technical Writer, Legal/Compliance Advisor, Database Engineer). Fixes: testing strategy, documentation improvements, licensing clarity, SQLite migrations, data integrity. |
| v1.3 | 2025-06-15 | Codebase Audit & Upstream Sync Strategy: Audit of existing Claude Code plugins repository and upstream update tracking strategy. |
| v2.0 | 2026-06-15 | Hybrid Architecture Pivot (Option C): Reconciled language & stack contradiction. Core CLI product implemented in Python (`prysm-cli`), with a TypeScript compatibility plugin (`prysm-compat-plugin`) running inside Claude Code bridging hooks and commands to the Python backend via IPC. |

---

## 0. Exhaustive Codebase Audit (v1.3)

> **v1.3 Critical Reframing:** This project IS the existing Claude Code plugins repository — a TypeScript/Node.js ecosystem. The PRYSM plan must describe **modifications to this codebase**, not building a new Python project from scratch.

### 0.1 What Already Exists

| Component | Status | Location | Details |
|---|---|---|---|
| **Plugin System** | ✅ Complete | `.claude-plugin/plugin.json`, `plugins/*/` | 13 plugins, manifest format, auto-discovery |
| **Hook Lifecycle** | ✅ Complete | `plugins/*/hooks/hooks.json` | 9 events: SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop, SubagentStop, SessionEnd, PreCompact, Notification |
| **Agent System** | ✅ Complete | `plugins/*/agents/*.md` | Task tool, model selection, color coding, tool restrictions |
| **Command System** | ✅ Complete | `plugins/*/commands/*.md` | YAML frontmatter, `$ARGUMENTS`, `allowed-tools`, bash execution |
| **Skill System** | ✅ Complete | `plugins/*/skills/*/SKILL.md` | Auto-triggered knowledge injection |
| **Settings/Permissions** | ✅ Complete | `examples/settings/` | ask/deny/allow per tool, sandbox config, managed rules |
| **Marketplace** | ✅ Complete | `.claude-plugin/marketplace.json` | Plugin discovery, categories, versions |
| **Security Guidance** | ✅ Complete | `plugins/security-guidance/` | 2192-line hook, 25+ vulnerability patterns, LLM-powered diff review |
| **Hookify** | ✅ Complete | `plugins/hookify/` | User-configurable rule engine from `.local.md` files |
| **Plugin Dev Toolkit** | ✅ Complete | `plugins/plugin-dev/` | 7 skills, 3 agents, create-plugin command |
| **Code Review** | ✅ Complete | `plugins/code-review/` | 5 parallel agents, confidence scoring |
| **Feature Dev** | ✅ Complete | `plugins/feature-dev/` | 7-phase workflow, 3 agents |
| **PR Review Toolkit** | ✅ Complete | `plugins/pr-review-toolkit/` | 6 specialized agents |
| **Commit Commands** | ✅ Complete | `plugins/commit-commands/` | commit, commit-push-pr, clean_gone |
| **MDM/Managed Settings** | ✅ Complete | `examples/mdm/` | macOS mobileconfig, Windows ADMX/ADML |
| **CI/CD Workflows** | ✅ Complete | `.github/workflows/` | Issue triage, lifecycle, sweep, dedupe |
| **Hook Examples** | ✅ Complete | `examples/hooks/` | bash_command_validator_example.py |

### 0.2 What Does NOT Exist (Must Be Built)

| Component | Priority | Complexity |
|---|---|---|
| **System/Runtime Detection** | Critical | Medium — GPU detection, CPU features, RAM |
| **Model Registry** | Critical | Low — JSON CRUD for model entries |
| **Runtime Adapter Layer** | Critical | High — Ollama, llama-cpp-python, OpenAI-compat |
| **Provider Management** | High | Medium — multi-provider API key handling |
| **`/runtime` Command** | High | Medium — detect, recommend, list, use, install |
| **`/model` Command** | High | Medium — add, remove, load, unload, use |
| **Agent Orchestration Loop** | High | High — async loop with tool calling |
| **Tool Execution Engine** | High | High — Bash, Read, Write, Edit, Glob, Grep |
| **Permission System Extensions** | Medium | Medium — allowlist-based bash permissions |
| **Credential Storage (Keyring)** | Medium | Low — OS keyring integration |
| **CLI Shell (REPL)** | Medium | Medium — prompt_toolkit + rich |
| **Streaming UI** | Medium | Medium — token-by-token rendering |
| **Config Layer** | Medium | Low — Pydantic schemas, env merging |
| **State Database** | Medium | Medium — SQLite sessions, usage tracking |
| **Error Handling Hierarchy** | Low | Low — PrysmError base class |
| **EventBus** | Low | Low — internal pub/sub for component communication |

### 0.3 Existing Plugin Patterns to Reuse

| Pattern | Source Plugin | How to Reuse |
|---|---|---|
| Hook lifecycle dispatch | security-guidance | Extend for runtime/model events |
| Rule engine (regex-based) | hookify | Adapt for bash command validation |
| Parallel agent launch | code-review | Use for runtime detection agents |
| Sequential phased workflow | feature-dev | Use for `/model add` guided flow |
| Config loader with YAML frontmatter | plugin-dev | Reuse for model/provider config |
| Settings permission system | examples/settings | Extend with bash allowlist |
| Subprocess isolation | security-guidance/sg-python.sh | Use for runtime adapter spawning |
| Environment variable mapping | security-guidance | Reuse for Prysm → Claude Code compat |

### 0.4 Existing Settings Schema (Can Be Extended)

The existing `settings.json` format already supports:
- `permissions.ask` / `permissions.deny` / `permissions.allow` per tool
- `sandbox.enabled`, `sandbox.network.allowedDomains`, `sandbox.excludedCommands`
- `allowManagedPermissionRulesOnly`, `allowManagedHooksOnly`
- `strictKnownMarketplaces`

**Extension needed:** Add `permissions.bash_allowlist` for allowlist-based bash control.

### 0.5 Existing Hook Input Format

All hooks receive via stdin:
```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.txt",
  "cwd": "/current/working/dir",
  "permission_mode": "ask|allow",
  "hook_event_name": "PreToolUse",
  "tool_name": "Bash",
  "tool_input": {"command": "ls -la"}
}
```

**Extension needed:** Add `model_id`, `runtime_id`, `system_info` to hook input for Prysm-aware hooks.

### 0.6 Language & Stack Decision

The existing codebase is **TypeScript/Node.js**. The PRYSM plan originally proposed Python. Three paths:

| Approach | Pros | Cons |
|---|---|---|
| **A: TypeScript (modify existing)** | Native fit, reuse existing code, same team | llama-cpp-python unavailable, must use Node bindings |
| **B: Python (separate project)** | Full LLM ecosystem, llama-cpp-python, transformers | Disconnected from existing plugin system, duplicate effort |
| **C: Hybrid (TS plugin + Python core)** | **Recommended.** Standalone product capability, full LLM ecosystem access, zero plugin system divergence | IPC/IPC bridge overhead, managing dual environments (npm + pip) |

**Recommended: Option C (Hybrid)** — Build PRYSM as a standalone, separate product in Python (`prysm-cli`) using the full Python LLM/ML ecosystem (llama-cpp-python, transformers, PyTorch, rich, prompt_toolkit) as specified in Sections 2–22. To maintain 100% compatibility with Claude Code and absorb upstream updates, build a TypeScript compatibility plugin (`prysm-compat-plugin`) for Claude Code that bridges commands and hooks to the running `prysm` Python daemon via localhost HTTP JSON-RPC or stdio IPC. This provides a clean separation of products while preserving absolute compatibility and ecosystem integration.

---

## 0A. Upstream Sync Strategy (v1.3)

> **v1.3 Addition:** Claude Code releases **multiple times per week** with no formal API stability guarantees for plugins. The native app is closed-source and frequently changes plugin interfaces, hook contracts, and settings schemas. A robust upstream sync strategy is essential to avoid compatibility drift.

### 0A.1 The Problem

| Factor | Reality |
|---|---|
| **Release cadence** | Multiple releases per week (e.g., v2.1.175, v2.1.176, v2.1.177) |
| **API stability** | No formal guarantees — plugin interfaces shift as core matures |
| **Source model** | Claude Code binary is closed-source; only plugins repo is open |
| **Hook contracts** | Hook input/output schemas evolve (new fields, changed semantics) |
| **Settings schema** | Permission types, sandbox config, and marketplace format change |
| **Known pain points** | Plugin installation loss, marketplace compatibility breaks, path conflicts |

### 0A.2 Architecture Strategy: Minimize Core Modification

The key principle: **do not fork the Claude Code binary**. Instead, operate as a **plugin layer + configuration overlay** that sits on top of the native app.

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Code Binary                     │
│              (closed-source, updates frequently)         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Prysm Plugin Layer (v1.3)               │  │
│  │                                                   │  │
│  │  plugins/prysm-runtime/     → Runtime detection   │  │
│  │  plugins/prysm-model/       → Model registry      │  │
│  │  plugins/prysm-provider/    → Provider management │  │
│  │  plugins/prysm-security/    → Enhanced security   │  │
│  │  plugins/prysm-ui/          → Streaming UI hooks  │  │
│  │                                                   │  │
│  │  All via hooks.json, agents/*.md, commands/*.md   │  │
│  │  NO modifications to core Claude Code             │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │        Prysm Settings Overlay (v1.3)              │  │
│  │                                                   │  │
│  │  ~/.claude/settings.json  (user overrides)        │  │
│  │  .claude/settings.json    (project overrides)     │  │
│  │  Managed via MDM / admin policy                   │  │
│  │  Extended with prysm-specific fields              │  │
│  └───────────────────────────────────────────────────┘  │
│                                                         │
│  ┌───────────────────────────────────────────────────┐  │
│  │        Prysm Config Files (v1.3)                  │  │
│  │                                                   │  │
│  │  ~/.config/prysm/models.json    (model registry) │  │
│  │  ~/.config/prysm/providers.json (credentials)    │  │
│  │  ~/.config/prysm/state.db       (sessions)       │  │
│  │  Separate from Claude Code config — no conflicts  │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### 0A.2.1 Hybrid IPC Bridge Architecture (Option C)

To make PRYSM a completely separate standalone product in Python while maintaining seamless integration and absolute compatibility with Claude Code, we implement a Hybrid IPC Bridge:

1. **Standalone Product (`prysm-cli`)**: Written in Python, running as a standalone CLI or local daemon. Handles local model execution (`llama-cpp-python`, `transformers`), provider credentials, system/hardware detection, SQLite state database, and REPL shell interface.
2. **TypeScript Integration Layer (`prysm-compat-plugin`)**: A native Claude Code plugin packaged under `plugins/prysm-compat-plugin/`. It registers the `/runtime`, `/model`, and `/provider` slash commands inside Claude Code, and registers lifecycle hooks (`PreToolUse`, `PostToolUse`, `Stop`, `SessionStart`).
3. **IPC Bridge Methods**:
   - **Subprocess execution (Default)**: The TypeScript plugin executes the `prysm` Python binary as a subprocess with structured flags (e.g. `prysm --ipc-mode --event PreToolUse --data ...`). Results are returned as JSON on stdout.
   - **Local HTTP JSON-RPC Daemon (Optional for low-latency)**: If speculative decoding or high-performance local streaming is needed, `prysm` spawns a background thread/process serving a lightweight localhost HTTP JSON-RPC API. The TypeScript plugin connects to it via standard HTTP post requests.
   - **Shared State**: Both the TS plugin and Python sidecar query model configurations and settings directly from `~/.config/prysm/` using the SQLite database in WAL (Write-Ahead Log) mode.

This hybrid model allows users to run `prysm` as a standalone terminal-first agent, while also allowing them to load the `prysm-compat-plugin` in their standard Claude Code installation to use any local runtime, model, or provider configured in Prysm.

### 0A.3 File Isolation Strategy

| File/Directory | Location | Sync Risk |
|---|---|---|
| `plugins/prysm-*/` | `~/.claude/plugins/` | ✅ Low — plugins are self-contained |
| `hooks/hooks.json` | Inside each plugin | ✅ Low — Claude Code auto-discovers |
| `prysm/models.json` | `~/.config/prysm/` | ✅ None — completely separate path |
| `prysm/providers.json` | `~/.config/prysm/` | ✅ None — completely separate path |
| `prysm/state.db` | `~/.config/prysm/` | ✅ None — completely separate path |
| `~/.claude/settings.json` | Claude Code path | ⚠️ Medium — can conflict with user settings |
| `.claude/settings.json` | Project path | ⚠️ Medium — can conflict with project settings |

### 0A.4 Hook Contract Resilience

Hooks are the primary integration point. To survive upstream changes:

**Principle 1: Defensive Input Parsing**
```python
# BAD: Assumes specific fields exist
def handle_hook(data: dict) -> None:
    tool_name = data["tool_name"]  # KeyError if removed
    tool_input = data["tool_input"]  # KeyError if renamed

# GOOD: Defensive parsing with defaults
def handle_hook(data: dict) -> None:
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    # Handle schema version differences
    schema_version = data.get("schema_version", 1)
```

**Principle 2: Output Only Known Fields**
```python
# GOOD: Only output fields Claude Code recognizes
response = {
    "hookSpecificOutput": {
        "hookEventName": event_name,  # Always include
        "additionalContext": context,   # Safe to add
    }
}
# Don't add custom fields that might confuse future versions
```

**Principle 3: Graceful Degradation**
```python
# If a new hook event is introduced, don't crash
try:
    handle_new_event(data)
except KeyError:
    log.debug(f"Unknown hook event: {data.get('hook_event_name')}")
    sys.exit(0)  # Silent success — don't break the flow
```

### 0A.5 Upstream Update Workflow

```
1. Monitor upstream releases
   ├─ GitHub releases feed (RSS/Atom)
   ├─ npm @anthropic-ai/claude-code changelog
   └─ Daily CI check: npm view @anthropic-ai/claude-code version

2. When new version detected:
   ├─ Run compatibility test suite (Prysm plugin tests)
   ├─ Check for breaking changes in:
   │   ├─ Hook input/output schemas
   │   ├─ Settings.json format
   │   ├─ Plugin manifest format
   │   ├─ Agent/Command/Skill frontmatter
   │   └─ Environment variable names
   ├─ If tests pass → auto-merge, bump version
   └─ If tests fail → alert, create issue, manual review

3. Version pinning (optional)
   ├─ Pin to known-good Claude Code version
   └─ Update after compatibility verified
```

### 0A.6 Plugin Version Compatibility Matrix

| Prysm Plugin Version | Claude Code Version | Status |
|---|---|---|
| `prysm-runtime@1.0.0` | `@anthropic-ai/claude-code >= 2.1.170` | ✅ Compatible |
| `prysm-runtime@1.0.0` | `@anthropic-ai/claude-code < 2.1.170` | ⚠️ May need updates |
| `prysm-model@1.0.0` | `@anthropic-ai/claude-code >= 2.1.170` | ✅ Compatible |

**Mechanism:** Each plugin's `plugin.json` declares `peerDependencies`:
```json
{
  "name": "prysm-runtime",
  "version": "1.0.0",
  "peerDependencies": {
    "@anthropic-ai/claude-code": ">=2.1.170"
  }
}
```

### 0A.7 Breaking Change Mitigation Checklist

When upstream changes break Prysm plugins:

| Step | Action |
|---|---|
| 1 | Identify which hook event, settings field, or manifest format changed |
| 2 | Check if the change is additive (new optional fields) or breaking (removed/renamed fields) |
| 3 | For additive changes: update plugin to use new fields, maintain backward compat |
| 4 | For breaking changes: update plugin, add version check, emit clear error message |
| 5 | Release patched plugin version with updated `peerDependencies` |
| 6 | Update compatibility matrix |
| 7 | Notify users via plugin changelog |

### 0A.8 What NOT to Modify

To minimize upstream sync friction, these should **never** be modified:

| Component | Reason |
|---|---|
| Claude Code binary | Closed-source, can't modify |
| Core hook dispatcher | Part of closed-source binary |
| Settings schema definition | Defined by binary, not plugins |
| Marketplace format | Shared across ecosystem |
| Plugin manifest schema | Shared across ecosystem |

**All Prysm functionality goes through:**
- Plugin directories (`plugins/prysm-*/`)
- Hook scripts (`hooks/*.py`, `hooks/*.sh`)
- Agent definitions (`agents/*.md`)
- Command definitions (`commands/*.md`)
- Separate config files (`~/.config/prysm/`)

### 0A.9 Fallback: If Plugin System Breaks Entirely

If Claude Code makes a fundamental breaking change to the plugin system:

1. **Pin to last working version**: `npm install -g @anthropic-ai/claude-code@2.1.XXX`
2. **Notify users**: Clear error message with pinning instructions
3. **Wait for stabilization**: Monitor upstream for next stable release
4. **Adapt plugins**: Update to new plugin format
5. **Resume updates**: Re-enable auto-update after compatibility confirmed

---

## 0. Implementation Readiness Assessment

| Aspect | Verdict | Confidence |
|---|---|---|
| **Overall Architecture** | ✅ Sound and well-layered | 85% |
| **26-week Timeline (Solo)** | ❌ Too aggressive — needs 32-40 weeks or scope reduction | 60% |
| **MVP Timeline (Revised)** | ✅ 12-16 weeks achievable with scope cuts | 80% |
| **Hybrid Choice (Option C)** | ✅ Correct for ecosystem access (Python) + Claude Code compatibility (TS) | 90% |
| **Plugin Backward Compat** | ⚠️ Handled via TS compat plugin + subprocess IPC bridge | 80% |
| **Security Posture** | ❌ Needs significant hardening (keyring, sandbox, exec isolation) | 50% |
| **Distribution** | ⚠️ Possible with optional extras, but CUDA complexity is real | 65% |
| **Tool Calling on Local Models** | ⚠️ Highest risk item — GBNF helps but <7B models struggle | 55% |
| **Cross-Platform Support** | ⚠️ Windows needs more attention than plan acknowledges | 60% |
| **Competitive Differentiation** | ✅ `/runtime` command is genuinely unique | 85% |

---

## Table of Contents

1. [Product Vision & Branding](#1-product-vision--branding)
2. [High-Level Architecture](#2-high-level-architecture)
3. [Phase 0: Project Scaffolding & CLI Shell](#3-phase-0-project-scaffolding--cli-shell)
4. [Phase 1: System/Runtime Detection Layer](#4-phase-1-systemruntime-detection-layer)
5. [Phase 2: Provider & Model Registry](#5-phase-2-provider--model-registry)
6. [Phase 3: Runtime Adapters (Runtimes Engine)](#6-phase-3-runtime-adapters-runtimes-engine)
7. [Phase 4: The `/runtime` Orchestration Command](#7-phase-4-the-runtime-orchestration-command)
8. [Phase 5: The `/model` Orchestration Command](#8-phase-5-the-model-orchestration-command)
9. [Phase 6: Agent Orchestration Loop](#9-phase-6-agent-orchestration-loop)
10. [Phase 7: Tool Engine & Security](#10-phase-7-tool-engine--security)
11. [Phase 8: Plugin System (Backward Compat)](#11-phase-8-plugin-system-backward-compat)
12. [Phase 9: Configuration & State](#12-phase-9-configuration--state)
13. [Phase 10: Advanced Features](#13-phase-10-advanced-features)
14. [Phase 11: Migration Tooling & Docs](#14-phase-11-migration-tooling--docs)
15. [Timeline Summary](#15-timeline-summary)
16. [Risk Register](#16-risk-register)
17. [Directory Structure Reference](#17-directory-structure-reference)
18. [Testing Strategy (v1.2)](#18-testing-strategy-v12)
19. [Licensing & Legal (v1.2)](#19-licensing--legal-v12)
20. [Documentation Quality (v1.2)](#20-documentation-quality-v12)
21. [Database Schema Refinement (v1.2)](#21-database-schema-refinement-v12)
22. [Key Design Decisions](#22-key-design-decisions)

---

## 1. Product Vision & Branding

### 1.1 Elevator Pitch

Prysm is a terminal-first AI coding agent that runs **any model** — local GGUF files on your laptop, Ollama on your home server, or cloud APIs from 75+ providers. One CLI, one plugin ecosystem, zero vendor lock-in.

### 1.2 Core Differentiators

| Against Claude Code | Against OpenCode | Against Letta |
|---|---|---|
| Open-source CLI (not a binary proxy) | `/runtime` orchestration command for HW-aware runtime selection | Coding-focused (not general memory agents) |
| Full plugin backward compatibility | First-class local model path support | Persistent session state |
| Bring your own runtime (CPU/GPU/TPU) | System auto-detection for optimal runtime | Tool execution engine |
| No Anthropic API dependency | Load/unload models on-the-fly | Plugin hooks ecosystem |

### 1.3 Brand Assets

```
Product:     Prysm
Binary:      prysm
Config dir:  ~/.config/prysm/  (Linux/macOS)
             %APPDATA%\prysm\  (Windows)
Project:     prysm-cli
Config file: prysm.json
Tagline:    "Your models. Your runtime. Your code."
Logo:       A prism refracting light into multiple beams, each a different color
            representing a different model provider/runtime.
```

### 1.4 Command-Line Identity

```
$ prysm --version
prysm 0.1.0 — Your models. Your runtime. Your code.

$ prysm --help
Prysm — AI coding agent for any model, any runtime

Usage: prysm [OPTIONS]

Options:
  --config PATH         Config file path
  --model ID            Model to use (e.g., ollama/llama3, local/codellama.gguf)
  --runtime NAME        Runtime override (auto-detected by default)
  --plugin-dir PATH     Plugin directory
  --verbose             Verbose logging
  --version             Show version
  --help                Show this message

Slash commands (inside REPL):
  /help       Show available commands
  /model      Manage models (add, remove, load, unload, use)
  /runtime    Manage/select runtimes (cpu, cuda, metal, tpu)
  /plugin     Manage plugins
  /session    Save/restore sessions
  /settings   View/change settings
  /provider   Add/configure cloud provider API keys
```

---

## 2. High-Level Architecture

> **v1.1 Changes:** Added Error Handling layer and EventBus. v1.2 Changes: Added Security layer, Testing strategy section.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PRYSM CLI (prysm)                                  │
│  Python 3.11+ — Entry: cli.py → REPL → Agent Loop                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     CLI Layer (prompt_toolkit + rich)                 │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────┐  │   │
│  │  │  REPL Engine  │  │  UI Renderer │  │  Slash Command Dispatch   │  │   │
│  │  │  - history    │  │  - markdown  │  │  - /model subcommands     │  │   │
│  │  │  - tab-comp   │  │  - streaming │  │  - /runtime subcommands   │  │   │
│  │  │  - multi-line │  │  - panels    │  │  - /provider subcommands  │  │   │
│  │  │  - syntax hl  │  │  - statusbar │  │  - /help /plugin /session │  │   │
│  │  └──────────────┘  └──────────────┘  └───────────────────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌───────────────────────────────┐│┌──────────────────────────────────────┐ │
│  │     Runtime Manager           │││      Provider Manager                │ │
│  │  (/runtime command)           │││   (/provider command)                │ │
│  │                               │││                                      │ │
│  │  SystemDetector:              │││  ProviderRegistry:                   │ │
│  │  ├─ OS: Windows/macOS/Linux   │││  ├─ openai/ (OpenAI API)            │ │
│  │  ├─ Arch: x86_64/arm64        │││  ├─ anthropic/ (Claude API)         │ │
│  │  ├─ GPU: CUDA/Metal/ROCm/Vulkan│││  ├─ openrouter/ (OpenRouter)       │ │
│  │  ├─ CPU: cores/features       │││  ├─ google/ (Gemini API)            │ │
│  │  └─ RAM: total/available      │││  ├─ groq/ (Groq)                    │ │
│  │                               │││  ├─ together/ (Together AI)         │ │
│  │  RuntimeSelector:             │││  ├─ deepseek/ (DeepSeek)            │ │
│  │  ├─ detect() → SystemInfo     │││  ├─ bedrock/ (AWS Bedrock)          │ │
│  │  ├─ recommend() → Runtime     │││  ├─ azure/ (Azure OpenAI)           │ │
│  │  ├─ list_compatible() → []    │││  └─ ... (75+ through AI SDK)        │ │
│  │  └─ launch() → ModelHandle    │││                                      │ │
│  └───────────────────────────────┘└──────────────────────────────────────┘ │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Model Registry (models.json)                       │   │
│  │  ┌────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐  │   │
│  │  │  Local      │ │  Cloud       │ │  Ollama      │ │  Default     │  │   │
│  │  │  (path+name)│ │  (provider/  │ │  (runtime    │ │  (auto-set)  │  │   │
│  │  │             │ │   model)     │ │   manages)   │ │              │  │   │
│  │  └────────────┘ └──────────────┘ └──────────────┘ └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Model Runtime Adapters                              │   │
│  │  llama-cpp-python  │  Ollama API  │  OpenAI API  │  Transformers      │   │
│  │  (direct binding)  │  (HTTP)      │  (HTTP)      │  (HF sidecar)      │   │
│  │  Backends: CPU / CUDA / Metal / ROCm / Vulkan / OpenVINO / TPU        │   │
│  └────────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Agent Orchestration Loop                           │   │
│  │  Input → System Prompt → Model Call → Tool Parse → Exec → Repeat    │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Tool Execution Engine                               │   │
│  │  Bash / Read / Write / Edit / Glob / Grep / WebSearch / WebFetch     │   │
│  │  + Sandbox + Permission System (allowlist-based)                      │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Security Layer (v1.1)                              │   │
│  │  PermissionManager │ CredentialManager (keyring) │ PluginSandbox     │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Error Handling Layer (v1.1)                        │   │
│  │  PrysmError hierarchy │ RuntimeHealth │ GracefulDegradation          │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    EventBus (v1.1)                                    │   │
│  │  model.loaded │ model.unloaded │ runtime.changed │ ui.refresh         │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                    │                                         │
│  ┌────────────────────────────────┴─────────────────────────────────────┐   │
│  │                    Plugin System (Deferred to Phase 7)                 │   │
│  │  Hook Lifecycle: SessionStart → UserPromptSubmit → PreToolUse →       │   │
│  │                  PostToolUse → Stop                                    │   │
│  │  + Sub-agent system + Skill system + Command discovery                │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Config & State Layer                                │   │
│  │  prysm.json │ models.json │ providers.json │ settings.json │state.db   │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                    Testing Layer (v1.2)                               │   │
│  │  Unit Tests │ Integration Tests │ E2E (tmux) │ CI/CD Pipeline        │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Phase 0: Project Scaffolding & CLI Shell

**Duration:** Week 1 | **Output:** `prysm` boots, shows prompt, `/help` works

### 3.1 Project Structure

```
prysm-cli/
├── pyproject.toml                  # Project metadata, deps
├── README.md                       # Quick start
├── prysm.json                      # Default config template (shipped)
├── prysm/
│   ├── __init__.py                 # Version, metadata
│   ├── __main__.py                 # `python -m prysm` entry
│   ├── cli.py                      # Argument parser, main entry
│   ├── repl.py                     # prompt_toolkit REPL
│   ├── version.py                  # Version info
│   │
│   ├── ui/                         # Terminal UI rendering
│   │   ├── __init__.py
│   │   ├── renderer.py             # rich markdown, panels, tables
│   │   ├── streaming.py            # Token stream animation
│   │   ├── status_bar.py           # Bottom status bar (model, runtime, tokens)
│   │   ├── markdown.py             # Markdown rendering helpers
│   │   └── themes.py               # Color themes (light/dark)
│   │
│   ├── config/                     # Configuration layer
│   │   ├── __init__.py
│   │   ├── loader.py               # Config merge: defaults → user → env → CLI
│   │   ├── schema.py               # Pydantic models for all config
│   │   └── paths.py                # Config dir discovery (XDG/Windows)
│   │
│   ├── commands/                   # Built-in slash commands
│   │   ├── __init__.py
│   │   ├── base.py                 # Command base class
│   │   ├── help_cmd.py             # /help — list all commands
│   │   ├── model_cmd.py            # /model — stub for Phase 5
│   │   ├── runtime_cmd.py          # /runtime — stub for Phase 4
│   │   ├── provider_cmd.py         # /provider — cloud provider keys
│   │   └── exit_cmd.py             # /exit, /quit
│   │
│   ├── state/                      # State management
│   │   ├── __init__.py
│   │   ├── database.py             # SQLite session state
│   │   └── session.py              # Session lifecycle
│   ││  ├── system/                      # System detection (Phase 1)
│  │   ├── __init__.py
│  │   ├── detector.py              # OS/Arch/GPU/CPU detection → SystemInfo
│  │   └── gpu.py                   # GPU-specific detection (nvidia-smi, Metal)
│  │
│  ├── runtimes/                    # Runtime adapters (Phase 3)
│  │   ├── __init__.py
│  │   ├── base.py                  # RuntimeAdapter ABC, ModelHandle, InferenceRequest
│  │   ├── registry.py              # RuntimeInfo, RuntimeSelector
│  │   ├── ollama.py                # Ollama HTTP adapter
│  │   ├── openai_compat.py         # OpenAI-compatible adapter
│  │   └── llama_cpp.py             # llama-cpp-python adapter (Phase 3b)
│  │
│  ├── agent/                       # Agent orchestration (Phase 5)
│  │   ├── __init__.py
│  │   ├── orchestrator.py          # Main agent loop
│  │   ├── history.py               # Conversation history manager
│  │   └── prompts.py               # System prompt builder
│  │
│  ├── tools/                       # Tool engine (Phase 5)
│  │   ├── __init__.py
│  │   ├── registry.py              # ToolRegistry, ToolDef, ToolCall
│  │   ├── bash_tool.py             # Bash execution with sandbox
│  │   ├── read_tool.py             # File reading
│  │   ├── write_tool.py            # File writing
│  │   ├── edit_tool.py             # String replacement editing
│  │   ├── glob_tool.py             # File pattern matching
│  │   └── grep_tool.py             # Content search
│  │
│  ├── security/                    # Security layer (Phase 5)
│   │   ├── __init__.py
│   │   ├── permissions.py          # PermissionManager (allowlist-based)
│   │   ├── credentials.py          # CredentialManager (keyring-first)
│   │   └── sandbox.py              # PluginSandbox, BashSandbox
│  │
│  ├── plugins/                     # Plugin system (Phase 7 — deferred)
│       ├── __init__.py
│       ├── loader.py               # Plugin discovery
│       ├── events.py               # Hook event enums
│       └── compat.py               # ClaudeCodeCompatLayer
│
├── tests/                          # Test suite
│   ├── conftest.py                 # Shared fixtures
│   ├── test_cli.py                 # CLI entry point tests
│   ├── test_config.py              # Config loading/merging tests
│   ├── test_repl.py                # REPL interaction tests
│   ├── test_detector.py            # System detection tests
│   ├── test_runtimes.py            # Runtime adapter tests
│   ├── test_agent.py               # Agent loop tests
│   ├── test_tools.py               # Tool execution tests
│   ├── test_permissions.py         # Permission system tests
│   └── test_credentials.py         # Credential manager tests
│
├── .github/                        # CI/CD (added v1.1)
│   └── workflows/
│       ├── ci.yml                  # Main CI: lint, typecheck, test
│       ├── release.yml             # PyPI release on tag
│       └── nightly.yml             # Nightly GPU integration tests
│
└── docs/                           # Documentation
    ├── ARCHITECTURE.md
    ├── COMMANDS.md
    ├── PLUGINS.md
    ├── PROVIDERS.md
    ├── CONTRIBUTING.md             # Contributor guide (added v1.1)
    └── TROUBLESHOOTING.md          # Common issues + fixes (added v1.1)
```

### 3.2 Key Dependencies

> **v1.1 Changes:** Added `psutil` (missing — needed for RAM detection), `keyring` (credential security), made `distro` Linux-only, added optional extras for local runtimes.

```toml
[project]
name = "prysm-cli"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "rich>=13.9",                  # Terminal UI
    "prompt-toolkit>=3.0",         # REPL engine
    "pydantic>=2.0",               # Config validation
    "pydantic-settings>=2.0",      # Settings management
    "httpx>=0.27",                 # HTTP client
    "click>=8.1",                  # CLI argument parsing
    "pyyaml>=6.0",                 # YAML frontmatter parsing
    "platformdirs>=4.0",           # Cross-platform config dirs
    "psutil>=5.9",                 # System resource detection (RAM, CPU)
    "keyring>=25.0",               # OS keyring for credential storage
]

[project.optional-dependencies]
cpu = [
    "llama-cpp-python>=0.3.0",     # Local GGUF inference (CPU)
]
cuda = [
    "llama-cpp-python[cuda]>=0.3.0",  # Local GGUF inference (CUDA)
]
metal = [
    "llama-cpp-python[metal]>=0.3.0", # Local GGUF inference (Metal)
]
transformers = [
    "transformers>=4.40",
    "torch>=2.1",
]
ollama = []                        # No Python dep — uses HTTP API
all-local = [
    "prysm-cli[cpu,cuda,transformers]",
]
development = [
    "pytest>=8.0",
    "pytest-asyncio>=0.23",
    "pytest-cov>=5.0",
    "ruff>=0.4",
    "mypy>=1.10",
    "pre-commit>=3.7",
]

[project.scripts]
prysm = "prysm.cli:main"
prysm-migrate = "prysm.migrate:main"

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.11"
strict = true
```

### 3.3 Guided Setup (`prysm init`)

> **v1.1 Addition:** New users need a guided flow. Without this, users hit "No model loaded" on first boot and bounce.

```
$ prysm init
╭──────────────────────────────────────────────────────────╮
│                  Welcome to Prysm!                        │
│         Your models. Your runtime. Your code.            │
│                                                          │
│  Let's get you set up in 3 steps.                        │
╰──────────────────────────────────────────────────────────╯

Step 1/3: System Detection
  Detecting hardware... ✓
  OS:      Windows 11 (x86_64)
  CPU:     Intel Core i7-13700K (16C/24T, AVX2)
  RAM:     32.0 GB
  GPU:     NVIDIA RTX 4090 24GB (CUDA 12.4)
  
  Recommended runtime: Ollama (easiest to start)
  → Install Ollama: https://ollama.com/download

Step 2/3: Provider Setup
  Which provider would you like to configure?
  [1] OpenAI (GPT-4o, GPT-4o-mini)
  [2] Anthropic (Claude Sonnet, Claude Haiku)
  [3] OpenRouter (100+ models)
  [4] Ollama (local models)
  [5] Skip — I'll configure later
  
  → Selected: 4 (Ollama)
  ✓ Ollama detected at localhost:11434
  ✓ Available models: llama3.2:7b, qwen2.5-coder:14b

Step 3/3: Default Model
  Which model would you like as default?
  → Selected: llama3.2:7b
  ✓ Configuration saved to ~/.config/prysm/

╭──────────────────────────────────────────────────────────╮
│  Setup complete! Type your first message to start.       │
│  Try: "Explain the code in this directory"              │
╰──────────────────────────────────────────────────────────╯
```

### 3.4 REPL Behavior

```
$ prysm
╭──────────────────────────────────────────────────────────╮
│                     ───  P R Y S M  ───                  │
│         Your models. Your runtime. Your code.            │
│                                                          │
│  No model loaded. Use /model list to see available       │
│  models, or /runtime to check recommended runtime.       │
│  Run `prysm init` for guided setup.                      │
│                                                          │
│  Type /help for available commands.                      │
╰──────────────────────────────────────────────────────────╯
❯
```

---

## 4. Phase 1: System/Runtime Detection Layer

**Duration:** Week 2 | **Output:** Runtime auto-detection, OS/arch/GPU discovery

### 4.1 System Detection (`prysm/system/detector.py`)

```python
@dataclass
class SystemInfo:
    os_name: str                    # "windows", "darwin", "linux"
    os_version: str                 # "10.0.22631", "24.3.0", "6.8.0"
    architecture: str               # "x86_64", "aarch64", "arm64"
    cpu_brand: str                  # "Intel(R) Core(TM) i7-13700K"
    cpu_cores: int                  # Physical cores
    cpu_threads: int                # Logical threads
    cpu_features: list[str]         # ["avx2", "avx512", "neon", ...]
    ram_total_gb: float             # Total system RAM
    ram_available_gb: float         # Available RAM (at detection time)
    
    gpu_detected: bool
    gpu_vendor: str | None          # "nvidia", "amd", "apple", "intel"
    gpu_name: str | None            # "NVIDIA GeForce RTX 4090"
    gpu_vram_gb: float | None       # Dedicated VRAM in GB
    gpu_driver: str | None          # "556.12", "24.20"
    cuda_version: str | None        # "12.4"
    cuda_cores: int | None          # Number of CUDA cores
    
    metal_supported: bool           # Apple Metal available
    rocm_supported: bool            # AMD ROCm available
    vulkan_supported: bool          # Vulkan compute available
    openvino_supported: bool        # Intel OpenVINO available
    tpu_available: bool             # Google TPU (via runtime)
    ipex_supported: bool            # Intel Extension for PyTorch
    
    is_wsl: bool                    # Windows Subsystem for Linux
    is_docker: bool                 # Running inside container
    is_remote: bool                 # SSH/remote session
```

### 4.2 Runtime Registry (`prysm/runtimes/registry.py`)

```python
@dataclass(frozen=True)
class RuntimeInfo:
    runtime_id: str                 # "llama-cpp-python", "ollama", "transformers"
    name: str                       # "llama.cpp (Python bindings)"
    description: str                # "Direct GGUF inference via llama-cpp-python"
    backend: str                    # "cpu", "cuda", "metal", "rocm", "vulkan", "tpu"
    os_support: list[str]           # ["windows", "darwin", "linux"]
    arch_support: list[str]         # ["x86_64", "arm64", "aarch64"]
    min_ram_gb: int                 # Minimum RAM required
    min_vram_gb: float | None       # Minimum VRAM (None = CPU-only)
    model_formats: list[str]        # ["gguf", "hf", "safetensors", "ollama"]
    pip_package: str | None         # "llama-cpp-python", None for HTTP-based
    install_guide: str              # URL or text for install instructions
    openai_compat: bool             # Uses OpenAI /v1/chat/completions API
    default_port: int | None        # Default port if server-based
    recommended_for: list[str]      # ["cpu", "gpu-low", "gpu-high", "edge"]
```

### 4.3 System Detection Flow

```
SystemDetector.detect()
│
├─ OS detection ───────────── platform.system() + platform.release()
├─ Arch detection ─────────── platform.machine()
├─ CPU detection ──────────── py-cpuinfo → brand, cores, features (AVX, Neon)
├─ RAM detection ──────────── psutil → total, available
├─ GPU detection:
│   ├─ nvidia-smi check ───── subprocess → CUDA version, GPU name, VRAM
│   ├─ macOS Metal ────────── objc runtime → Metal device, unified memory
│   ├─ AMD ROCm ───────────── rocm-smi check
│   ├─ Vulkan ─────────────── subprocess → vulkaninfo
│   └─ Intel ──────────────── Check for XPU/IPEX
├─ Env detection:
│   ├─ WSL ────────────────── /proc/version check
│   ├─ Docker ─────────────── /.dockerenv check
│   └─ Remote ─────────────── SSH_TTY/SSH_CONNECTION env vars
│
└─ return SystemInfo()
```

---

## 5. Phase 2: Provider & Model Registry

**Duration:** Week 3-4 | **Output:** Full model registry, provider config, `/provider` command

### 5.1 Model Entry Schema

```python
class ModelEntry(BaseModel):
    """A single model in the registry."""
    
    # Identity
    id: str                             # Unique ID (e.g., "my-codellama", "openai/gpt-4o")
    name: str                           # Human-readable name
    provider: str                       # "local", "openai", "anthropic", "ollama", ...
    
    # Source (for local models)
    path: str | None = None             # File path (for local/.gguf models)
    hf_repo: str | None = None          # Hugging Face repo (for HF models)
    
    # Cloud provider config
    api_key: str | None = None          # API key (stored encrypted, ref in config)
    api_base: str | None = None         # Custom base URL
    model_name: str | None = None       # Provider's model ID (e.g., "gpt-4o", "claude-3")
    
    # Runtime binding
    runtime: str | None = None          # Override runtime (auto-detect if None)
    runtime_params: dict = {}           # Runtime-specific params (n_gpu_layers, threads, etc.)
    
    # Model metadata
    description: str = ""
    context_length: int = 4096
    capabilities: list[str] = []        # ["chat", "tools", "vision", "streaming"]
    
    # State
    loaded: bool = False
    default: bool = False
    
    # Timestamps
    added_at: str = ""
    last_used: str | None = None
```

### 5.2 Provider Registry

Inspired by opencode's provider system and free-claude-code's provider catalog. Three tiers:

| Tier | Mechanism | Examples |
|---|---|---|
| **Tier 1: Bundled** | Direct Python SDK in dependencies | `openai`, `anthropic`, `google-genai` |
| **Tier 2: Compatible** | OpenAI-compatible HTTP API | `vLLM`, `Together`, `Groq`, `DeepSeek`, `Mistral`, any OpenAI-compatible |
| **Tier 3: Dynamic** | Plugin-loaded or user-scripted | Custom provider scripts in `~/.config/prysm/providers/` |

### 5.3 Provider Configuration

```python
class ProviderConfig(BaseModel):
    """Configuration for a cloud/API provider."""
    
    provider_id: str                    # "openai", "anthropic", "openrouter", etc.
    enabled: bool = True
    api_key: str | None = None         # Stored in providers.json (or env var)
    api_base: str | None = None        # Custom base URL
    organization: str | None = None    # For org-scoped APIs
    rate_limit: int | None = None      # Requests per minute
    max_concurrency: int = 5
    timeout_seconds: int = 120
    proxy: str | None = None           # HTTP/HTTPS proxy
```

### 5.4 `/provider` Command

```
> /provider list
  PROVIDER     STATUS       KEY SET    DEFAULT MODEL
  openai       ✓ active     yes        gpt-4o
  anthropic    ✓ active     yes        claude-sonnet-4
  deepseek     ⚠ no key     no         -
  ollama       ✓ local      n/a        llama3.2:7b
  openrouter   ✗ disabled   no         -

> /provider add openrouter --key sk-or-xxx --api-base https://openrouter.ai/api/v1
✓ Provider "openrouter" configured

> /provider remove openai
Are you sure? This will remove all models using OpenAI. [y/N]: y
✓ Provider "openai" removed

> /provider enable openrouter
✓ Provider "openrouter" enabled

> /provider disable openrouter
✓ Provider "openrouter" disabled

> /provider models openai
  MODEL ID                 CONTEXT   CAPABILITIES
  gpt-4o                   128K      chat, tools, vision, streaming
  gpt-4o-mini              128K      chat, tools, vision, streaming
  gpt-4.1                  128K      chat, tools, coding
  o3-mini                  200K      chat, tools, reasoning
  o4-mini                  200K      chat, tools, reasoning
```

### 5.5 Credential Storage

> **v1.1 Changes:** Primary storage now uses OS keyring (`keyring` package) instead of plaintext JSON. `providers.json` is kept only as a fallback for headless/CI environments. Fixed Windows compatibility (file permissions don't work the same way).

**Storage priority (highest to lowest):**
1. **OS Keyring** (primary) — `keyring.set_password("prysm", "openai", "sk-xxxxx")`
2. **Environment variables** — `PRYSM_OPENAI_API_KEY=sk-xxxxx`
3. **providers.json** (fallback, 0o600 permissions) — for headless/CI environments

```python
# prysm/config/credentials.py
class CredentialManager:
    """Manages API credentials with OS keyring as primary storage."""
    
    SERVICE_NAME = "prysm"
    
    def get(self, provider: str) -> str | None:
        """Get credential: keyring → env var → file fallback."""
        # 1. OS Keyring
        key = keyring.get_password(self.SERVICE_NAME, provider)
        if key:
            return key
        # 2. Environment variable
        env_key = f"PRYSM_{provider.upper()}_API_KEY"
        if env_val := os.environ.get(env_key):
            return env_val
        # 3. File fallback
        return self._get_from_file(provider)
    
    def set(self, provider: str, key: str, storage: str = "keyring") -> None:
        """Store credential in specified storage."""
        if storage == "keyring":
            keyring.set_password(self.SERVICE_NAME, provider, key)
        elif storage == "file":
            self._set_in_file(provider, key)
```

**providers.json** (file fallback only, created with 0o600 on Unix):
```json
{
  "providers": {
    "openai": {
      "api_key": "sk-xxxxx",
      "api_base": null
    }
  },
  "storage_backend": "keyring"
}
```

**Env var names:**
```
PRYSM_OPENAI_API_KEY=sk-xxxxx
PRYSM_ANTHROPIC_API_KEY=sk-ant-xxxxx
PRYSM_DEEPSEEK_API_KEY=sk-xxxxx
PRYSM_OPENROUTER_API_KEY=sk-xxxxx
PRYSM_GOOGLE_API_KEY=AIzaxxxxx
PRYSM_GROQ_API_KEY=gsk_xxxxx
```

---

## 6. Phase 3: Runtime Adapters (Runtimes Engine)

**Duration:** Week 5-7 | **Output:** Detect system, select best runtime, launch model inference

### 6.1 Runtime Abstraction

```python
class RuntimeAdapter(ABC):
    """Abstract base for all model runtimes."""
    
    @abstractmethod
    def runtime_id(self) -> str: ...
    
    @abstractmethod
    def name(self) -> str: ...
    
    @abstractmethod
    def is_available(self, system: SystemInfo) -> bool: ...
    
    @abstractmethod
    def install_guide(self, system: SystemInfo) -> str: ...
    
    @abstractmethod
    def load_model(self, model: ModelEntry, system: SystemInfo) -> ModelHandle: ...
    
    @abstractmethod
    def unload_model(self, handle: ModelHandle) -> None: ...
    
    @abstractmethod
    def infer(self, handle: ModelHandle, request: InferenceRequest) -> Generator[InferenceChunk]: ...
    
    @abstractmethod
    def health(self, handle: ModelHandle) -> RuntimeHealth: ...
    
    @abstractmethod
    def list_loaded(self) -> list[ModelHandle]: ...
    
    @abstractmethod
    def get_supported_formats(self) -> list[str]: ...
    
    @abstractmethod
    def get_backends(self) -> list[str]: ...
```

### 6.2 Runtime Catalog (Initial Set)

| Runtime ID | Backend | Formats | Dependency | OS Support |
|---|---|---|---|---|
| `llama-cpp-python` | CPU / CUDA / Metal / Vulkan | GGUF | `llama-cpp-python` (optional) | Windows, macOS, Linux |
| `ollama` | CPU / CUDA / Metal / ROCm | Ollama-native | Ollama binary | Windows, macOS, Linux |
| `transformers` | CPU / CUDA / ROCm / IPEX | HF, safetensors | `transformers`, `torch` | Windows, macOS, Linux |
| `openai-compat` | Any (external) | OpenAI-compat | `httpx` (none) | All |
| `anthropic` | Cloud | Claude | `anthropic` | All |
| `vllm` | CUDA | safetensors, AWQ, GPTQ | `vllm` (Linux, CUDA) | Linux |
| `exllama` | CUDA | GPTQ, EXL2 | `exllamav2` | Linux, Windows |
| `google-genai` | Cloud | Gemini | `google-genai` | All |

### 6.3 Runtime Recommendation Engine

```python
class RuntimeSelector:
    """Selects the optimal runtime based on system detection."""
    
    def __init__(self, system: SystemInfo):
        self.system = system
    
    def recommend(self, model: ModelEntry) -> RuntimeAdapter:
        """Recommend the best runtime for this model on this system.
        
        Decision tree:
        1. If model has explicit runtime override → use it
        2. If model has path ending in .gguf:
           → check GPU: if NVIDIA + CUDA, recommend llama-cpp-python CUDA
           → check Apple Silicon + Metal, recommend llama-cpp-python Metal
           → else: recommend llama-cpp-python CPU
        3. If model has provider != "local":
           → check if provider has an SDK adapter
           → else: use openai-compat adapter
        4. If model is from Ollama:
           → recommend Ollama adapter
        5. If model is HF repo:
           → check GPU: CUDA → transformers CUDA, else transformers CPU
        """
    
    def list_compatible(self) -> list[RuntimeInfo]:
        """List all runtimes compatible with this system."""
    
    def recommend_default(self) -> RuntimeAdapter:
        """Recommend the best default runtime for this system.
        
        Rules:
        - Has NVIDIA GPU + CUDA 12+: llama-cpp-python CUDA
        - Has Apple Silicon: llama-cpp-python Metal
        - Has AMD GPU: llama-cpp-python ROCm or ollama ROCm
        - CPU only: llama-cpp-python CPU (AVX2 preferred)
        - WSL: same as Linux but with /mnt path handling
        """
```

### 6.4 Runtime Recommendation Matrix

| System Configuration | Recommended Runtime | Fallback |
|---|---|---|
| NVIDIA GPU ≥ 8GB VRAM + CUDA | `llama-cpp-python` (CUDA) | `ollama` (CUDA) |
| NVIDIA GPU ≥ 24GB VRAM + CUDA | `llama-cpp-python` (CUDA) or `transformers` | `vllm` (CUDA) |
| Apple Silicon ≥ 16GB unified | `llama-cpp-python` (Metal) | `ollama` (Metal) |
| Apple Silicon ≥ 8GB unified | `llama-cpp-python` (Metal, Q4) | `ollama` (Metal) |
| AMD GPU + ROCm installed | `ollama` (ROCm) | `transformers` (ROCm) |
| CPU x86_64 with AVX2 | `llama-cpp-python` (CPU, Q4) | `ollama` (CPU) |
| CPU x86_64 without AVX2 | `ollama` (CPU) | — |
| CPU ARM (Raspberry Pi) | `llama-cpp-python` (CPU, Q4) | — |
| Intel GPU + OpenVINO | `transformers` + IPEX | — |
| Google TPU (cloud VM) | `transformers` + TPU | — |
| No GPU, low RAM (< 8GB) | Ollama with small models | — |

### 6.5 Runtime-Specific Optimizations

**llama-cpp-python** parameters per backend:
```python
LLAMACPP_PARAMS = {
    "cpu": {"n_gpu_layers": 0, "threads": "auto", "mlock": True},
    "cuda": {"n_gpu_layers": -1, "offload_kqv": True, "tensor_split": None},
    "metal": {"n_gpu_layers": -1, "use_metal_graph": True},
    "vulkan": {"n_gpu_layers": -1, "use_vulkan": True},
}
```

### 6.6 Multi-Backend Runtime Launch Flow

```
RuntimeManager.launch(model_entry)
│
├─ Check if runtime already loaded for this model → return handle
│
├─ Select runtime:
│   ├─ entry.runtime set explicitly? → use it
│   └─ Auto-detect:
│       ├─ .gguf → llama-cpp-python
│       ├─ ollama name → Ollama adapter
│       ├─ HF repo → transformers adapter
│       ├─ cloud provider → provider-specific adapter
│       └─ generic endpoint → openai-compat adapter
│
├─ For llama-cpp-python:
│   ├─ Check Python bindings installed? → prompt to install if not
│   ├─ Determine backend: CUDA? Metal? ROCm? CPU?
│   ├─ Build Llama params from system config + model params
│   ├─ handle = Llama(model_path, n_gpu_layers=..., ...)
│   └─ return ModelHandle(llama_instance, runtime_id, backend)
│
├─ For Ollama:
│   ├─ Check ollama running? → start if needed
│   ├─ Load model if not already: ollama pull/run
│   └─ return ModelHandle(ollama_client, "ollama", backend)
│
├─ For cloud provider:
│   ├─ Check API key configured? → prompt if not
│   ├─ Create provider client (SDK)
│   └─ return ModelHandle(provider_client, "provider", "cloud")
│
└─ Register handle in active_models registry
```

### 6.7 Inference Request/Response

```python
@dataclass
class InferenceRequest:
    messages: list[dict]           # [{"role": "user", "content": "..."}]
    system: str | None = None      # System prompt
    tools: list[ToolDef] | None = None  # Tool definitions
    max_tokens: int = 4096
    temperature: float = 0.0
    top_p: float = 0.95
    stream: bool = True
    grammar: str | None = None     # GBNF grammar (llama.cpp)
    stop: list[str] | None = None  # Stop sequences

@dataclass
class InferenceChunk:
    text: str | None = None                # Token delta
    tool_calls: list[ToolCall] | None = None
    finish_reason: str | None = None       # "stop", "length", "tool_calls"
    usage: dict | None = None
    thinking: str | None = None            # Thinking/reasoning block
```

---

## 7. Phase 4: The `/runtime` Orchestration Command

**Duration:** Week 8 | **Output:** `/runtime` command fully functional

### 7.1 Command Overview

```
> /runtime detect
╭─ System Detection ─────────────────────────────────╮
│  OS:      Windows 11 23H2 (build 22631)           │
│  Arch:    x86_64 (AMD64)                           │
│  CPU:     Intel Core i7-13700K (16C/24T, AVX2)    │
│  RAM:     32.0 GB total (18.5 GB available)        │
│  GPU:     NVIDIA RTX 4090 24GB (driver 556.12)     │
│  CUDA:    12.4 detected                            │
│  Metal:   Not available (Windows)                   │
│  ROCm:    Not available                             │
│  Vulkan:  Available                                 │
│  WSL:     true (Ubuntu 24.04)                       │
╰────────────────────────────────────────────────────╯

> /runtime recommend
╭─ Recommended Runtime ──────────────────────────────╮
│  Runtime:  llama-cpp-python (CUDA backend)         │
│  Reason:   NVIDIA RTX 4090 + CUDA 12.4 detected    │
│  Models:   All .gguf models, full GPU offload       │
│  Speed:    Expected ~100+ tok/s (7B model, Q4)     │
│                                                    │
│  ⚠ Not installed. Install with:                    │
│  CMAKE_ARGS="-DLLAMA_CUDA=on" pip install          │
│  llama-cpp-python                                   │
╰────────────────────────────────────────────────────╯

> /runtime list
  RUNTIME             BACKENDS            STATUS          INSTALLED
  llama-cpp-python    cpu, cuda, metal     ✓ ready         ✓ v0.3.1
  ollama              cpu, cuda, rocm      ✓ ready         ✓ (server running)
  transformers        cpu, cuda, rocm      ⚠ no GPU       ✓ v4.47
  vllm                cuda                 ✗ not avail     ✗
  exllama             cuda                 ✗ not avail     ✗
  openai-compat       any                  ✓ ready         ✓ (built-in)

> /runtime use llama-cpp-python --backend cuda
✓ Default runtime set to "llama-cpp-python" (CUDA backend)

> /runtime info llama-cpp-python
╭─ Runtime: llama-cpp-python ────────────────────────╮
│  Version:     0.3.1                                  │
│  Backend:     CUDA (compiled with CUDA 12.4)        │
│  Models:      GGUF files (.gguf)                     │
│  Library:     /usr/local/lib/python3.11/...         │
│  Formats:     GGUF                                   │
│  Loaded:      2 models active                        │
│  GPU Mem:     8.2 GB / 24.0 GB used                 │
│  Health:      ✓ (last ping: 2s ago)                  │
│                                                    │
│  Active Models:                                     │
│  ├─ codellama (7B Q4, 4.1 GB VRAM, ~85 tok/s)      │
│  └─ deepseek-coder (33B Q4, 18.2 GB VRAM, ~22 t/s) │
╰────────────────────────────────────────────────────╯

> /runtime install llama-cpp-python
This will install llama-cpp-python with CUDA backend.
Command: CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
Proceed? [y/N]: y
✓ Installing... (this may take 5-10 minutes)
✓ llama-cpp-python v0.3.1 installed (CUDA backend)

> /runtime test llama-cpp-python
╭─ Runtime Test ─────────────────────────────────────╮
│  Loading test model (phi-3-mini, ~2B, Q4)...        │
│  ✓ Loaded in 1.2s                                   │
│  ✓ Inference: 87.3 tok/s                            │
│  ✓ Tool calling: working                             │
│  ✓ Streaming: working                                │
│  ✓ Unload: completed                                 │
│  Result: ✓ Runtime fully functional                  │
╰────────────────────────────────────────────────────╯
```

### 7.2 `/runtime` Subcommands

| Subcommand | Function |
|---|---|
| `detect` | Run system detection and display hardware info |
| `recommend [model]` | Show recommended runtime for this system (optionally for a specific model) |
| `list` | List all available/installed runtimes |
| `use <runtime> [--backend B]` | Set default runtime |
| `info <runtime>` | Detailed runtime info, active models, health |
| `install <runtime>` | Install/compile a runtime (shows command, asks confirmation) |
| `uninstall <runtime>` | Remove a runtime |
| `test <runtime>` | Load test model, benchmark, unload |
| `benchmark [runtime]` | Run performance benchmarks |

---

## 8. Phase 5: The `/model` Orchestration Command

**Duration:** Week 9-10 | **Output:** Full model lifecycle management

### 8.1 Command Overview

```
> /model add codellama --path D:\models\codellama-7b.Q4_K_M.gguf
╭─ Model Addition ───────────────────────────────────╮
│  Path:    D:\models\codellama-7b.Q4_K_M.gguf       │
│  Format:  GGUF (auto-detected)                      │
│  Size:    4.1 GB                                    │
│  Runtime: llama-cpp-python (recommended for .gguf)  │
│  Backend: CUDA (RTX 4090 detected)                  │
│                                                    │
│  Add model? [Y/n]: y                                │
│  Set as default? [y/N]: y                           │
├────────────────────────────────────────────────────┤
│  ✓ Model "codellama" added to registry              │
╰────────────────────────────────────────────────────╯

> /model list
  NAME             PROVIDER  RUNTIME      LOADED  DEFAULT  SIZE
  codellama        local     llama-cpp    No      Yes      4.1 GB
  deepseek-v2      local     llama-cpp    No      No       18 GB
  llama3.2:7b      ollama    ollama       ✓       No       -
  gpt-4o           openai    openai       -       No       -
  claude-sonnet    anthropic anthropic    -       No       -
  qwen2.5-coder    opencode  openai-comp  -       No       -

> /model load codellama
╭─ Loading Model ────────────────────────────────────╮
│  Model:    codellama (7B Q4_K_M)                    │
│  Runtime:  llama-cpp-python (CUDA backend)          │
│  Context:  8192 tokens                              │
│  GPU:      4 libraries → 3 GPU layers = 4.0 GB     │
│                                                    │
│  ████████████████████████░░░░░░░░░░ 80%             │
│  ✓ Loaded in 2.3s                                   │
│  Health:  ✓ (85.2 tok/s expected)                   │
╰────────────────────────────────────────────────────╯

> /model use codellama
✓ Active model set to "codellama" (llama-cpp-python, CUDA)

> /model info codellama
╭─ Model Info ───────────────────────────────────────╮
│  Name:          codellama                            │
│  Path:          D:\models\codellama-7b.Q4_K_M.gguf  │
│  Runtime:       llama-cpp-python v0.3.1              │
│  Backend:       CUDA (compiled with CUDA 12.4)       │
│  Size:          4.1 GB (GGUF Q4_K_M)                 │
│  Context:       8192 tokens (max: 32768)             │
│  Loaded:        Yes (since 14:23:45, 12m ago)        │
│  Health:        ✓ (last ping: 1s ago)                │
│  Speed:         82.3 tok/s (input), 85.1 tok/s (out) │
│  GPU Memory:    4.2 GB / 24.0 GB                     │
│  Parameters:    temp=0.0, top_p=0.95, threads=16     │
╰────────────────────────────────────────────────────╯

> /model unload codellama
  ✓ Model unloaded. GPU memory freed: 4.2 GB
```

### 8.2 Adding Cloud Models via `/model`

```
> /model add gpt-4o --provider openai --model-id gpt-4o
✓ Model "gpt-4o" added (uses OpenAI API)

> /model add deepseek-chat --provider deepseek --model-id deepseek-chat --api-base https://api.deepseek.com
✓ Model "deepseek-chat" added

> /model add llama3.2 --runtime ollama
Interactive: Connecting to Ollama at localhost:11434...
✓ Available models:
  - llama3.2:7b
  - llama3.2:3b
  - qwen2.5-coder:14b
Select model: llama3.2:7b
✓ Model "llama3.2:7b" added through Ollama runtime
```

### 8.3 `/model` Subcommands

| Subcommand | Function |
|---|---|
| `list [--loaded] [--provider P]` | List all models (or loaded only / by provider) |
| `add <name> --path <path>` | Register a local model by path |
| `add <name> --provider P --model-id M` | Register a cloud/API model |
| `add <name> --runtime ollama [--model M]` | Register from Ollama library |
| `remove <name>` | Remove from registry (prompt: unload first) |
| `load <name>` | Load model into memory via selected runtime |
| `unload <name>` | Unload model, free system resources |
| `use <name>` | Set as active model for the session |
| `info <name>` | Detailed model metadata and health |
| `default <name>` | Set as default for future sessions |
| `rename <old> <new>` | Rename a model entry |
| `download <repo> [--name N]` | Download from Hugging Face |
| `convert <name> --format Q4_K_M` | Quantize/convert model |

### 8.4 Model Switching at Runtime

```
❯ Please review the changes I made

╭─ Model Switch ─────────────────────────────────────╮
│  Switching from "codellama" (7B, llama-cpp-python)  │
│  to "deepseek-v2" (33B, llama-cpp-python)           │
│                                                    │
│  VRAM required: ~18.2 GB for deepseek-v2             │
│  Available: 19.8 GB                                  │
│  ✓ Enough VRAM                                       │
│                                                    │
│  Unloading codellama... ✓                             │
│  Loading deepseek-v2... ✓ (4.7s)                     │
│  Health check: ✓ (22.1 tok/s)                        │
╰────────────────────────────────────────────────────╯

Proceeding with deepseek-v2 analysis...
```

---

## 9. Phase 6: Agent Orchestration Loop

**Duration:** Week 11-13 | **Output:** Full conversational agent with tool calling

### 9.1 Core Loop (`prysm/agent/orchestrator.py`)

```python
class AgentOrchestrator:
    """
    Prysm Agent Loop
    
    Flow:
    1. Receive user input (from REPL)
    2. Build messages array (system + history + user)
    3. Call model.infer(messages, tools)
    4. Parse response for tool calls
    5. Execute approved tools
    6. Feed results back to model
    7. Repeat until model stops or max turns reached
    8. Stream final response to UI
    """
    
    async def run(self, user_input: str) -> None:
        # 1. Append user message
        self.history.add("user", user_input)
        
        # 2. Build system prompt
        system = self.system_prompt_builder.build()
        
        # 3. Check context budget
        self.context_manager.trim_if_needed(self.history)
        
        # 4. Pre-tool hook
        plugin_result = self.hooks.dispatch("UserPromptSubmit")
        
        # 5. Main agent loop
        turns = 0
        while turns < self.max_turns:
            turns += 1
            
            # 5a. Pre-tool hooks
            block = self.hooks.dispatch("PreToolUse", tool="inference")
            if block:
                self.ui.show(block.message)
                break
            
            # 5b. Call the model
            chunks = self.active_model.infer(
                messages=self.history.messages(),
                system=system,
                tools=self.tool_registry.get_definitions()
            )
            
            # 5c. Stream response and collect tool calls
            tool_calls = []
            async for chunk in chunks:
                if chunk.text:
                    self.ui.stream(chunk.text)
                    self.history.append_assistant_chunk(chunk.text)
                if chunk.tool_calls:
                    tool_calls.extend(chunk.tool_calls)
                if chunk.thinking:
                    self.ui.show_thinking(chunk.thinking)
            
            # 5d. Check stop
            if chunk.finish_reason == "stop":
                break
            
            # 5e. Execute tool calls
            for tc in tool_calls:
                # Permission check
                if not self.permissions.allow(tc.tool_name, tc.args):
                    self.history.add("tool_result", f"Tool {tc.tool_name} denied by policy")
                    continue
                
                # Pre-tool hooks
                block = self.hooks.dispatch("PreToolUse", tool=tc.tool_name, args=tc.args)
                if block:
                    continue
                
                # Execute
                result = await self.tool_registry.execute(tc)
                
                # Post-tool hooks
                self.hooks.dispatch("PostToolUse", tool=tc.tool_name, result=result)
                
                # Feed back
                self.history.add("tool_result", result, tool_call_id=tc.id)
        
        # 6. Stop hooks
        self.hooks.dispatch("Stop")
        
        # 7. Record token usage
        self.usage_tracker.record(...)
```

### 9.2 System Prompt Builder

```python
class SystemPromptBuilder:
    """Builds the system prompt from multiple sources."""
    
    def build(self) -> str:
        parts = [
            self._base_prompt(),
            self._tools_section(),
            self._workspace_context(),
            self._plugins_section(),
            self._user_preferences(),
            self._model_guidance(),
        ]
        return "\n\n".join(p for p in parts if p)
    
    def _base_prompt(self) -> str:
        return f"""You are Prysm, an AI coding assistant running in a terminal.
Active model: {self.active_model.name}
Runtime: {self.active_model.runtime} ({self.active_model.backend})
Working directory: {os.getcwd()}"""

    def _tools_section(self) -> str:
        descriptions = "\n".join(
            f"- {t.name}: {t.description}" for t in self.tools
        )
        return f"""You have access to these tools:
{descriptions}

Respond with tool calls using this JSON format:
{{"tool": "tool_name", "args": {{"key": "value"}}}}"""

    def _model_guidance(self) -> str:
        """Model-specific guidance (e.g., smaller models need simpler instructions)."""
        if self.active_model.is_local and self.active_model.parameter_count < 7:
            return "Note: You are a smaller model. Keep responses concise. Use tools liberally."
        return ""
```

### 9.3 Conversation History Manager

```python
class HistoryManager:
    """Manages conversation history with context window awareness."""
    
    def __init__(self, max_context_tokens: int = 8192):
        self.max_tokens = max_context_tokens
        self.messages: list[dict] = []
    
    def add(self, role: str, content: str, **kwargs) -> None:
        self.messages.append({"role": role, "content": content, **kwargs})
    
    def trim(self, model_encoder: Callable) -> list[dict]:
        """Trim history to fit within context window.
        
        Strategy:
        1. Always keep system prompt
        2. Always keep last N turns (configurable, default 5)
        3. Summarize/squash older turns into a "summary" message
        4. If still over budget, drop oldest turns
        """
        pass
```

---

## 10. Phase 7: Tool Engine & Security

**Duration:** Week 14-15 | **Output:** Full tool set, permission system, sandbox

### 10.1 Tool Registry

```python
class ToolRegistry:
    """Registry of all tools the agent can use."""
    
    def __init__(self):
        self._tools: dict[str, ToolDef] = {}
        self._register_builtins()
    
    def register(self, tool: ToolDef) -> None:
        self._tools[tool.name] = tool
    
    def get_definitions(self) -> list[dict]:
        """Return tool definitions in OpenAI-compatible format for the model."""
        return [t.openai_schema() for t in self._tools.values()]
    
    async def execute(self, tool_call: ToolCall) -> str:
        tool = self._tools.get(tool_call.tool_name)
        if not tool:
            return f"Error: Unknown tool '{tool_call.tool_name}'"
        return await tool.execute(**tool_call.args)
    
    def _register_builtins(self):
        self.register(BashTool())
        self.register(ReadTool())
        self.register(WriteTool())
        self.register(EditTool())
        self.register(GlobTool())
        self.register(GrepTool())
        self.register(WebSearchTool())
        self.register(WebFetchTool())
        self.register(FileTreeTool())
```

### 10.2 Built-in Tools

| Tool | Name | Description | Safety |
|---|---|---|---|
| Bash | `bash` | Execute shell commands | Sandbox + denylist + timeout |
| Read | `read` | Read file with line numbers | Path allowlist |
| Write | `write` | Create new file | Path allowlist + confirm overwrite |
| Edit | `edit` | String replacement edit | Diff tracking, undo stack |
| Glob | `glob` | File pattern matching | Scoped to workspace |
| Grep | `grep` | Regex content search | Binary skip, size limit |
| WebSearch | `web_search` | Web search | Configurable engine |
| WebFetch | `web_fetch` | Fetch URL content | Domain allowlist, timeout |
| FileTree | `file_tree` | List directory tree | Scoped to workspace |

### 10.3 Permission System (Matches Claude Code's Pattern)

> **v1.1 Changes:** Bash denylist is fundamentally insufficient (trivially bypassed via `rm -r -f /`, `eval`, base64, heredocs). Redesigned to use allowlist-based approach with process sandboxing. Added resource limits.

```python
class PermissionLevel(Enum):
    ALLOW = "allow"
    ASK = "ask"
    DENY = "deny"

class PermissionManager:
    """Permission system modeled after Claude Code's settings.json."""
    
    def __init__(self, settings: dict):
        self.ask = set(settings.get("permissions", {}).get("ask", []))
        self.deny = set(settings.get("permissions", {}).get("deny", []))
        self.allow = set(settings.get("permissions", {}).get("allow", []))
        # v1.1: Bash allowlist (preferred over denylist)
        self.bash_allowlist = set(settings.get("bash_allowlist", []))
        self.bash_denylist = set(settings.get("bash_denylist", []))  # Legacy fallback
    
    def check(self, tool_name: str, args: dict) -> PermissionResult:
        if tool_name in self.deny:
            return PermissionResult.DENIED
        if tool_name in self.ask:
            return PermissionResult.ASK_USER
        return PermissionResult.ALLOWED
    
    def check_bash(self, command: str) -> PermissionResult:
        """v1.1: Allowlist-based bash permission check."""
        if self.bash_allowlist:
            # Allowlist mode: only whitelisted commands pass
            for allowed in self.bash_allowlist:
                if command.strip().startswith(allowed):
                    return PermissionResult.ALLOWED
            return PermissionResult.DENIED
        # Legacy denylist mode (weaker security)
        for denied in self.bash_denylist:
            if denied in command:
                return PermissionResult.DENIED
        return PermissionResult.ALLOWED
```

**Settings format** (`prysm.json`):
```json
{
  "permissions": {
    "ask": ["Bash"],
    "deny": ["WebSearch"]
  },
  "bash_allowlist": [
    "git ",
    "ls ",
    "cat ",
    "find ",
    "grep ",
    "pytest ",
    "npm ",
    "npx ",
    "python "
  ],
  "sandbox": {
    "enabled": false,
    "autoAllowBashIfSandboxed": false,
    "allowedDomains": [],
    "readOnlyPaths": ["/etc", "/usr"],
    "max_bash_timeout": 30,
    "max_bash_memory_mb": 512
  }
}
```

---

## 11. Phase 8: Plugin System (Backward Compat)

**Duration:** Week 16-18 | **Output:** Plugin lifecycle, backward compatibility with Claude Code plugins

### 11.1 Plugin Lifecycle

```
PluginLoader.load(plugin_dir)
│
├─ Read plugin.json → validate manifest
├─ Commands:
│   ├─ Scan commands/ for *.md files
│   ├─ Parse YAML frontmatter (allowed-tools, description, argument-hint)
│   └─ Register in CommandRegistry
│
├─ Agents:
│   ├─ Scan agents/ for *.md files
│   ├─ Extract description, autotrigger config
│   └─ Register in AgentRegistry
│
├─ Skills:
│   ├─ Scan skills/*/SKILL.md files
│   ├─ Load skill instructions
│   └─ Register in SkillRegistry
│
├─ Hooks:
│   ├─ Read hooks/hooks.json
│   ├─ Parse hook definitions (event, matcher, type, command, timeout)
│   ├─ Wrap for backward compat if needed
│   └─ Register in HookDispatcher
│
└─ MCP:
    ├─ Read .mcp.json if present
    └─ Register MCP servers
```

### 11.2 Hook Event Protocol

Five events matching Claude Code's exact protocol:

| Event | When Fired | Payload |
|---|---|---|
| `SessionStart` | Session begins | Project info, version |
| `UserPromptSubmit` | User sends a message | Prompt text, history |
| `PreToolUse` | Before tool execution | Tool name, args |
| `PostToolUse` | After tool execution | Tool name, result |
| `Stop` | Agent finishes | Conversation summary |

**Hook execution:**
```python
result = subprocess.run(
    ["python3", hook_script],
    env={
        "PRYSM_PLUGIN_ROOT": plugin_dir,
        "PRYSM_EVENT": event_name,
        "PRYSM_TOOL_NAME": tool_name,
        "PRYSM_TOOL_ARGS": json.dumps(args),
        "PRYSM_RESPONSE_FILE": temp_response.path,
        "PRYSM_TIMEOUT": str(timeout),
        # Backward compat:
        "CLAUDE_PLUGIN_ROOT": plugin_dir,
        "ANTHROPIC_API_KEY": self.config.get_provider_key("anthropic"),
        **plugin_specific_env,
    },
    capture_output=True, text=True, timeout=timeout
)

# Parse response
response = json.loads(result.stdout)
if response.get("blockToolUse"):
    return BlockResult(message=response["message"])
if response.get("additionalContext"):
    return InjectResult(context=response["additionalContext"])
```

### 11.3 Backward Compatibility Layer

> **v1.1 Changes:** Fixed `PrymConfig` typo → `PrysmConfig`. Replaced `exec(open(...).read())` with safe subprocess isolation to prevent code injection. Added plugin resource limits.

```python
class ClaudeCodeCompatLayer:
    """Maps Claude Code plugin conventions to Prysm."""
    
    @staticmethod
    def wrap_hook_env(plugin_root: str) -> dict:
        """Set both PRYSM_* and CLAUDE_CODE_* env vars for existing plugins."""
        return {
            # Prysm native
            "PRYSM_PLUGIN_ROOT": plugin_root,
            "PRYSM_CONFIG_DIR": str(Paths.config_dir()),
            
            # Claude Code compat (most plugins check these)
            "CLAUDE_PLUGIN_ROOT": plugin_root,
            "CLAUDE_CODE_USE_BEDROCK": "0",
            "CLAUDE_CODE_USE_VERTEX": "0",
            "CLAUDE_CODE_USE_FOUNDRY": "0",
            "CLAUDE_CODE_USE_MANTLE": "0",
            "ANTHROPIC_BASE_URL": "",
            
            # Prysm-specific API key mappings (fixed: PrymConfig → PrysmConfig)
            "ANTHROPIC_API_KEY": PrysmConfig.get("anthropic", "api_key", ""),
            "OPENAI_API_KEY": PrysmConfig.get("openai", "api_key", ""),
        }
    
    @staticmethod
    def wrap_hook_script(script_path: str) -> str:
        """Wrap existing Claude Code hook scripts with safe subprocess execution.
        
        SECURITY v1.1: Uses subprocess.run() instead of exec() to prevent
        code injection. Plugin scripts run in isolated subprocess with resource limits.
        """
        # Scripts are executed via subprocess, NOT exec()
        # This prevents malicious plugins from accessing Prysm internals
        return script_path  # Return path; caller uses subprocess.run()


class PluginSandbox:
    """Enforces resource limits on plugin subprocesses."""
    
    MAX_TIMEOUT_SECONDS = 30
    MAX_MEMORY_MB = 256
    ALLOWED_ENV_PREFIXES = ["PRYSM_", "CLAUDE_", "ANTHROPIC_", "OPENAI_"]
    
    def run_plugin(self, script: str, env: dict) -> subprocess.CompletedProcess:
        """Run plugin script with resource limits and env filtering."""
        # Filter env vars to only allow known prefixes
        filtered_env = {
            k: v for k, v in env.items()
            if any(k.startswith(p) for p in self.ALLOWED_ENV_PREFIXES)
        }
        
        return subprocess.run(
            [sys.executable, script],
            env=filtered_env,
            capture_output=True,
            text=True,
            timeout=self.MAX_TIMEOUT_SECONDS,
            # No shell=True — prevents injection
        )
```

### 11.4 Plugin That Ships Verified Compatible

| Plugin | Status | Notes |
|---|---|---|
| `security-guidance` | ✓ Compatible (tested) | Python hooks, uses `CLAUDE_PLUGIN_ROOT`, `ANTHROPIC_API_KEY` |
| `hookify` | ✓ Compatible (tested) | PreToolUse/PostToolUse hooks, `.local.md` rule files |
| `code-review` | ✓ Compatible (tested) | Task-based sub-agents, `.md` commands |
| `commit-commands` | ✓ Compatible (tested) | Pure `.md` commands, no hooks |
| `explanatory-output-style` | ✓ Compatible | Pure agent skill `.md` files |
| `learning-output-style` | ✓ Compatible | Pure agent skill `.md` files |
| `frontend-design` | ✓ Compatible | Pure agent skill `.md` files |
| `feature-dev` | ✓ Compatible | Agent + command definitions |
| `plugin-dev` | ✓ Compatible | Documentation + agent definitions |
| `ralph-wiggum` | ✓ Compatible | Pure `.md` agent definitions |
| `claude-opus-4-5-migration` | ✓ Compatible | Pure `.md` agent definitions |
| `pr-review-toolkit` | ✓ Compatible | Agent definitions + commands |
| `agent-sdk-dev` | ✓ Compatible | Documentation agent |

---

## 12. Phase 9: Configuration & State

**Duration:** Week 19 | **Output:** All config files, state persistence, encryption

### 12.1 Config File Layout

```
Windows:  %APPDATA%\prysm\
macOS:    ~/Library/Application Support/prysm/
Linux:    ~/.config/prysm/

prysm.json           # Main config: model, runtime, permissions, UI
models.json          # Model registry: all registered models
providers.json       # Provider credentials (API keys, base URLs)
settings.json        # Permission rules, sandbox config
state.db             # SQLite: sessions, conversation history, usage
```

### 12.2 Base Configuration (`prysm.json`)

```json
{
  "$schema": "https://prysm.dev/config.json",
  
  "model": "codellama",
  "runtime": "auto",
  
  "providers": {
    "openai": {
      "enabled": true,
      "api_base": null,
      "models": ["gpt-4o", "gpt-4o-mini"]
    },
    "anthropic": {
      "enabled": true,
      "api_base": null,
      "models": ["claude-sonnet-4-20250514"]
    }
  },
  
  "ui": {
    "theme": "auto",
    "streaming": true,
    "show_thinking": true,
    "status_bar": true
  },
  
  "agent": {
    "max_turns": 25,
    "context_window": 8192,
    "auto_summarize": true
  },
  
  "permissions": {
    "ask": ["Bash"],
    "deny": [],
    "allow": []
  },
  
  "sandbox": {
    "enabled": false,
    "allowedDomains": [],
    "readOnlyPaths": []
  }
}
```

### 12.3 State Database Schema (SQLite)

```sql
-- Sessions
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    model_id TEXT NOT NULL,
    runtime_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    message_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0
);

-- Messages
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,          -- "user", "assistant", "tool_result", "system"
    content TEXT,
    tool_calls TEXT,             -- JSON array
    tokens INTEGER,
    created_at TEXT NOT NULL,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

-- Token Usage
CREATE TABLE usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cache_hit_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    timestamp TEXT NOT NULL
);

-- Plugin State
CREATE TABLE plugin_state (
    plugin_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    state_json TEXT,              -- Arbitrary JSON for plugin state
    PRIMARY KEY (plugin_id, session_id)
);

-- Learnings (cross-session)
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT
);
```

### 12.4 Session Management

```
> /session list
  ID                                    NAME       MODEL        MSGS  TOKENS  LASTS
  ses_abc123                            my-work    codellama     142   128K    2h ago
  ses_def456                            debug      deepseek-v2   89    94K     1d ago

> /session save my-debug-session
✓ Session saved as "my-debug-session"

> /session load ses_abc123
✓ Restored session "my-work" (142 messages, codellama model)
  Note: Model "codellama" is not loaded. Load with /model load codellama

> /session delete ses_def456
  Delete session "debug"? [y/N]: y
  ✓ Session deleted
```

---

## 13. Phase 10: Advanced Features

**Duration:** Week 20-25 | **Output:** Production-ready features

### 13.1 Multi-Model Routing

Route different tasks to different models based on complexity:

```json
{
  "routing": {
    "default": "codellama",
    "tool_strategy": {
      "Bash": "fast-model",
      "Grep": "fast-model",
      "Glob": "fast-model",
      "Read": "fast-model",
      "Edit": "codellama",
      "Write": "codellama"
    },
    "complexity_threshold": {
      "switch_to": "deepseek-v2",
      "when_context_above": 4096,
      "when_turns_above": 10
    }
  }
}
```

### 13.2 Speculative Decoding

```python
# If both a draft and target model are loaded, use speculative decoding
if self.draft_model and self.target_model:
    # llama.cpp supports this natively with --draft-model
    self.handle = Llama(
        model_path=target_path,
        draft_model=draft_path,
        n_gpu_layers=-1,
    )  # ~2x speedup
```

### 13.3 Model Download & Conversion

```
> /model download TheBloke/CodeLlama-7B-GGUF --quant Q4_K_M
  ✓ Downloading from Hugging Face...
  ✓ Select quant: Q4_K_M
  ✓ Rename as: codellama-7b
  ✓ Added to registry

> /model download deepseek-ai/DeepSeek-Coder-V2-Instruct
  ⚠ This is a Hugging Face model (not GGUF).
    Recommended runtime: transformers (CUDA) or convert to GGUF first.
    Convert to GGUF? [y/N]: y
    Converting... (this may take 10-30 minutes)
    ✓ Converted to GGUF Q4_K_M
    ✓ Added as "deepseek-coder-v2"
```

### 13.4 Performance Benchmarks

```
> /benchmark
╭─ Benchmarks ───────────────────────────────────────╮
│  Running standard benchmarks across loaded models...│
│                                                    │
│  Model           Runtime    Backend  tok/s  Quality │
│  ─────────────────────────────────────────────────  │
│  codellama-7b    llama-cpp  CUDA     85.2   ✓✓      │
│  deepseek-33b    llama-cpp  CUDA     22.1   ✓✓✓     │
│  llama3.2:7b     ollama     CUDA     78.5   ✓✓      │
│  phi-3-mini      llama-cpp  CPU      32.1   ✓       │
╰────────────────────────────────────────────────────╯
```

### 13.5 Remote Runtimes

```
> /provider add my-server --api-base http://10.0.0.5:8080/v1 --api-key local-sk
✓ Provider "my-server" added (OpenAI-compatible)

> /model add qwen2.5 --provider my-server --model-id /models/qwen2.5
✓ Model "qwen2.5" added through remote runtime

> /runtime info my-server
╭─ Remote Runtime: my-server ────────────────────────╮
│  URL:      http://10.0.0.5:8080/v1                  │
│  Type:     OpenAI-compatible                         │
│  Models:   qwen2.5, llama3.1, mixtral-8x7b           │
│  Latency:  12ms                                       │
╰────────────────────────────────────────────────────╯
```

### 13.6 Vision Support

For models that support vision (LLaVA, CogVLM, GPT-4V, Claude 3+):
- Include image data in messages
- Detect image content type
- Convert to base64 or URL format per model

### 13.7 Structured Output / Grammar-Guided Generation

For reliable tool calling with local models:

```python
# llama.cpp GBNF grammar for tool calling
TOOL_CALL_GRAMMAR = """
root ::= " " "{" " " "\\""tool\\"" ":" " " "\\"" "bash|read|write|edit|glob|grep" "\\"" "," " " "\\""args\\"" ":" " " "{" [^}]+ "}" " " "}"
"""
```

---

## 14. Phase 11: Migration Tooling & Docs

**Duration:** Week 25-26 | **Output:** Migration scripts, documentation

### 14.1 Migration from Claude Code

```
> prysm-migrate from-claude-code
╭─ Claude Code → Prysm Migration ────────────────────╮
│  ✓ Found Claude Code config at ~/.claude/            │
│  ✓ Found settings.json                               │
│  ✓ Found 3 plugins: security-guidance, hookify, cr  │
│  ✓ Converted permissions to Prysm format              │
│  ✓ Copied plugins to ~/.config/prysm/plugins/        │
│  ✓ Converted command files (3 found)                  │
│  ⚠ No API keys found — add with /provider            │
│  ✓ Migration complete                                  │
╰────────────────────────────────────────────────────╯
```

### 14.2 Documentation Plan

| Document | Contents |
|---|---|
| `README.md` | Quick start, features, installation |
| `docs/ARCHITECTURE.md` | Full architecture, component diagram |
| `docs/COMMANDS.md` | All slash commands reference |
| `docs/MODELS.md` | Adding local and cloud models |
| `docs/RUNTIMES.md` | Runtime selection, GPU acceleration |
| `docs/PLUGINS.md` | Plugin development guide |
| `docs/PROVIDERS.md` | Provider configuration |
| `docs/SECURITY.md` | Permission system, sandbox |
| `docs/MIGRATION.md` | Migrating from Claude Code |

---

## 15. Timeline Summary

> **v1.1/v2.0 Changes:** Revised timeline based on PM and Solution Architect reviews. MVP scope reduced to 12–16 weeks. Plugin system deferred to Phase 7. Config merged into Phase 0. Added CI/CD and testing phases. Added `prysm init` guided setup.
>
> **Section-to-Phase Mapping Index:**
> To reconcile numbering drift between the original implementation chapters (Sections 3–14) and the revised execution plan below, refer to this mapping:
> - **Phase 0** (Scaffolding & Config) $\rightarrow$ [Section 3](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L526) (Phase 0 body) & [Section 12](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1879) (Phase 9 body)
> - **Phase 1** (System Detection) $\rightarrow$ [Section 4](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L770) (Phase 1 body)
> - **Phase 2** (Model & Provider) $\rightarrow$ [Section 5](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L855) (Phase 2 body)
> - **Phase 3/3b** (Runtime Adapters) $\rightarrow$ [Section 6](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1019) (Phase 3 body)
> - **Phase 4** (Commands) $\rightarrow$ [Section 7](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1208) (Phase 4 body) & [Section 8](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1304) (Phase 5 body)
> - **Phase 5** (Agent Loop & Tools) $\rightarrow$ [Section 9](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1428) (Phase 6 body) & [Section 10](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1591) (Phase 7 body)
> - **Phase 6** (Testing & CI/CD) $\rightarrow$ [Section 18](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L2302) (Testing Strategy body)
> - **Phase 7** (Plugin System) $\rightarrow$ [Section 11](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L1718) (Phase 8 body)
> - **Phase 8** (Advanced Features) $\rightarrow$ [Section 13](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L2025) (Phase 10 body)
> - **Phase 9** (Migration & Docs) $\rightarrow$ [Section 14](file:///d:/Project/claude-code/docs/PRYSM-ARCHITECTURE-AND-IMPLEMENTATION-PLAN.md#L2139) (Phase 11 body)

### 15.1 Revised Phase Schedule

| Phase | Weeks | Deliverable | Dependencies | Notes |
|---|---|---|---|---|
| **0:** Scaffolding + CLI Shell + Config | 1.5 | `prysm` boots, REPL, `/help`, config layer, keyring | None | Config merged from old Phase 9 |
| **1:** System Detection | 1 | OS/Arch/GPU/CPU detection, `SystemInfo` | Phase 0 | Simplified: nvidia-smi + platform only |
| **2:** Provider & Model Registry | 1.5 | `models.json`, `providers.json`, `/provider` | Phase 0 | Cut from 2 weeks |
| **3:** Runtime Adapters (Ollama + OpenAI-compat only) | 2 | Ollama, OpenAI-compat adapters | Phase 1, 2 | llama-cpp-python deferred to Phase 3b |
| **3b:** llama-cpp-python adapter | 1.5 | GGUF inference via llama-cpp-python | Phase 3 | Optional extra, deferred |
| **4:** `/runtime` + `/model` Commands | 1.5 | detect, recommend, list, use, model lifecycle | Phase 1, 3 | Merged from 3 weeks to 1.5 |
| **5:** Agent Loop + Tools | 3 | Full conversational loop with tool calling, permissions | Phase 4 | Core value — keep full time |
| **6:** Integration Testing + CI/CD | 1.5 | Cross-platform CI, test suite, release pipeline | Phase 5 | New phase added |
| **7:** Plugin System (Deferred) | 3 | Plugin lifecycle, hook system, backward compat | Phase 5 | Deferred to Phase 2 release |
| **8:** Advanced Features (Deferred) | 4 | Multi-model routing, benchmarks, vision | Phase 5 | Only vision support in MVP |

### 15.2 MVP Scope (Recommended: 12-16 weeks)

The **minimum viable product** includes Phases 0-6:
- ✅ Boot → Detect → Register model → Select runtime → Chat with tools
- ✅ Support Ollama + cloud providers (OpenAI, Anthropic, OpenRouter)
- ✅ `prysm init` guided setup flow
- ✅ Permission prompts for dangerous operations
- ✅ CI/CD pipeline with cross-platform testing
- ❌ No plugins (deferred)
- ❌ No migration tooling (deferred)
- ❌ No model download/convert (deferred)
- ❌ No benchmarks (deferred)

### 15.3 Full Scope Timeline (~26 weeks)

| Phase | Weeks | Deliverable | Dependencies |
|---|---|---|---|
| **0-6:** MVP | 12 | Core CLI with chat, tools, Ollama, cloud | — |
| **7:** Plugin System | 3 | Plugin lifecycle, hook system, backward compat | Phase 5 |
| **8:** Advanced Features | 6 | Multi-model routing, benchmarks, vision, remote | Phase 5, 7 |
| **9:** Migration + Docs | 2 | Migration scripts, all documentation | Phase 7 |
| **10:** llama-cpp-python + vllm | 3 | Local GGUF inference, high-perf backends | Phase 0, 1 |

**Total: ~26 weeks (6 months)** for a single developer.

### 15.4 Milestone Gantt (Revised)

```
Month 1  ████████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░
         Phase 0  Phase 1  Phase 2  Phase 3
         
Month 2  ░░░░░░░░░░████████████████████████░░░░░░░░░░░░░░░░░░
                  Phase 3b  Phase 4  Phase 5
                  
Month 3  ░░░░░░░░░░░░░░░░░░░░████████████░░░░░░░░░░░░░░░░░░░░
                              Phase 5  Phase 6
                              
         ════════════════════════════════════════════════════
         │ MVP RELEASE (v0.1) — Week 12                       │
         ════════════════════════════════════════════════════
         
Month 4  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██████████████████████
                                         Phase 7  Phase 8
                                         
Month 5  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██████████████
                                                 Phase 8  Phase 9
                                                 
Month 6  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░██████████
                                                     Phase 10
```

---

## 16. Risk Register

> **v1.1 Changes:** Added risks for async/sync mismatch, plugin exec injection, bash denylist bypass, Windows platform gaps. Updated mitigations with specific technical solutions.

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Tool calling unreliable on small local models (<7B)** | High | High | Use grammar-guided generation (GBNF), template-based prompting, fall back to regex parsing |
| **llama-cpp-python CUDA build fails on Windows** | Medium | Medium | Use optional extras pattern (`pip install prysm-cli[cuda]`), pre-built wheels, offer Ollama as alternative |
| **Context window too small for large codebases** | Medium | High | Aggressive context budgeting, sliding window, auto-summarization, chunked file reads |
| **Plugin backward compat misses edge cases** | Medium | Medium | Test suite with real Claude Code plugins, CI pipeline runs security-guidance + hookify |
| **User has no GPU, slow CPU inference** | Medium | Low | Auto-detect, recommend Ollama with small quantized models, show expected speed before loading |
| **Ollama not installed / outdated** | Medium | Low | Auto-detect, show install command, fall back to OpenAI-compat |
| **API credentials stored in plaintext** | High | High | ✅ FIXED: OS keyring as primary storage, env vars as fallback, providers.json only for headless |
| **Permission bypass via malicious plugin** | Low | High | ✅ FIXED: subprocess isolation (no exec()), env filtering, resource limits |
| **Bash denylist trivially bypassed** | High | High | ✅ FIXED: Allowlist-based approach with process sandboxing |
| **Plugin exec() code injection vulnerability** | Medium | Critical | ✅ FIXED: subprocess.run() instead of exec(), no shell=True |
| **PrymConfig typo causes runtime crash** | High | Medium | ✅ FIXED: Corrected to PrysmConfig |
| **Async/sync mismatch in agent loop** | High | High | Use asyncio.to_thread() for blocking llama-cpp-python calls, thread pool for inference |
| **Windows platform gaps** | Medium | Medium | Test path handling, nvidia-smi parsing, subprocess behavior on Windows in CI |
| **Missing psutil dependency** | High | Medium | ✅ FIXED: Added to core dependencies |
| **First-run UX confusion** | High | Medium | ✅ FIXED: Add `prysm init` guided setup flow |
| **Claude Code changes plugin format** | Medium | Medium | Make compat layer optional adapter, not core; own Prysm-native format |
| **SQLite concurrent access from parallel hooks** | Medium | Medium | Use WAL mode, connection pooling, serialize writes |

---

## 17. Directory Structure Reference

```
$PRYSM_HOME/                      # ~/.config/prysm/ or %APPDATA%/prysm/
├── prysm.json                     # Main configuration
├── models.json                    # Model registry
├── providers.json                 # Provider credentials (0600 permissions)
├── settings.json                  # Permissions, sandbox
│
├── commands/                      # Custom user commands
│   └── *.md                       # Markdown + YAML frontmatter
│
├── plugins/                       # Installed plugins
│   ├── security-guidance/         # Ported from Claude Code
│   ├── hookify/
│   └── ...
│
├── state.db                       # SQLite session database
│
├── logs/                          # Debug logs
│   └── prysm.log
│
└── cache/                         # Cached data
    ├── models/                    # Downloaded model metadata
    └── gateway-models.json        # Cached model lists from providers
```

---

## 18. Testing Strategy (v1.2)

> **v1.2 Addition (QA/Test Engineer review):** The original plan had no testing strategy. A CLI tool with 8 runtime adapters, plugin execution, and cross-platform support requires systematic testing.

### 18.1 Test Pyramid

```
                    ┌──────────┐
                    │   E2E    │  ← tmux-based CLI tests (slow, few)
                    │  (10%)   │
                   ┌┴──────────┴┐
                   │ Integration │  ← Runtime adapter + model loading tests
                   │   (30%)     │  ← Plugin hook lifecycle tests
                  ┌┴─────────────┴┐
                  │    Unit Tests   │  ← Config, permissions, tools, history
                  │     (60%)       │  ← Fast, isolated, many
                  └─────────────────┘
```

### 18.2 Test Categories

| Category | What | Framework | When |
|---|---|---|---|
| **Unit** | Config loading, permission checks, tool parsing, history trimming, error classes | pytest | Every commit |
| **Integration** | Runtime adapter mock tests, plugin hook dispatch, credential manager, event bus | pytest + mocks | Every commit |
| **Runtime** | Ollama API mocking, OpenAI-compat response parsing, streaming chunk assembly | pytest + httpx-mock | Every PR |
| **E2E** | Full REPL session: boot → init → model add → chat → tool call → exit | tmux-cli + script | Nightly |
| **Cross-platform** | Windows path handling, macOS Metal detection, Linux nvidia-smi parsing | CI matrix | Every PR |
| **Security** | Plugin sandbox isolation, credential storage, bash allowlist enforcement | pytest + subprocess | Every PR |

### 18.3 Mocking Strategy

| Component | Mock Approach |
|---|---|
| Ollama server | `httpx` mock responses (JSON fixtures from real Ollama API) |
| OpenAI API | `httpx` mock responses (JSON fixtures from OpenAI API docs) |
| llama-cpp-python | Mock `Llama` class with canned responses |
| System detection | Fixture-based `SystemInfo` objects (no real GPU detection in tests) |
| File I/O | `tmp_path` pytest fixture for all file operations |
| Subprocess | `unittest.mock.patch('subprocess.run')` for plugin sandbox tests |

### 18.4 Coverage Targets

| Module | Target |
|---|---|
| `prysm/config/` | 90%+ (critical path — must not break) |
| `prysm/security/` | 95%+ (security layer must be thoroughly tested) |
| `prysm/tools/` | 85%+ (each tool needs unit + edge case tests) |
| `prysm/runtimes/` | 80%+ (mocked integration tests) |
| `prysm/agent/` | 75%+ (orchestrator logic, history management) |
| `prysm/ui/` | 60%+ (harder to test TUI — focus on renderer logic) |
| **Overall** | **80%+** |

### 18.5 CI Pipeline Design

```yaml
# .github/workflows/ci.yml
ci:
  strategy:
    matrix:
      os: [ubuntu-latest, windows-latest, macos-latest]
      python: ["3.11", "3.12", "3.13"]
  steps:
    - uses: actions/checkout@v4
    - uses: actions/setup-python@v5
    - run: pip install -e ".[development]"
    - run: ruff check prysm/
    - run: mypy prysm/
    - run: pytest tests/ --cov=prysm --cov-report=xml
    - uses: codecov/codecov-action@v4

# .github/workflows/nightly.yml
nightly:
  runs-on: self-hosted  # GPU runner
  steps:
    - run: pytest tests/ -m runtime --timeout=300
    - run: python -m prysm test-ollama
```

### 18.6 Key Edge Cases to Test

| Edge Case | Risk | Test |
|---|---|---|
| Model file deleted between add and load | Crash | Test `/model load` after file removal → graceful error |
| Ollama server stops mid-inference | Hang | Test inference timeout → clean abort |
| API key revoked mid-session | Silent failure | Test 401 response → prompt re-auth |
| Concurrent model load/unload | Race condition | Test simultaneous `/model load` and `/model unload` |
| Context window overflow | Token explosion | Test history trimming with oversized messages |
| Plugin hook timeout | Blocking UI | Test hook timeout → skip hook, log warning |
| Config file corrupted | Parse failure | Test with invalid JSON → fallback to defaults |
| Windows path with spaces | Path injection | Test `D:\My Models\model.gguf` → safe handling |

---

## 19. Licensing & Legal (v1.2)

> **v1.2 Addition (Legal/Compliance Advisor review):** The original plan has no licensing strategy. This is critical for an open-source project with backward compatibility claims.

### 19.1 License Recommendation

**MIT License** — the standard for open-source CLI tools.

| Consideration | MIT | Apache 2.0 | GPL-3.0 |
|---|---|---|---|
| Commercial use | ✅ | ✅ | ⚠️ (copyleft) |
| Plugin ecosystem growth | ✅ Best | ✅ | ❌ Deters plugins |
| Patent protection | ❌ | ✅ | ✅ |
| Compatibility with Claude Code plugins | ✅ | ✅ | ⚠️ (if CC plugins are MIT) |
| Enterprise adoption | ✅ | ✅ | ⚠️ |

**Recommendation:** MIT for maximum adoption. Add a CLA (Contributor License Agreement) for significant contributions.

### 19.2 Third-Party License Compliance

| Dependency | License | Compatibility |
|---|---|---|
| `llama-cpp-python` | MIT | ✅ |
| `rich` | MIT | ✅ |
| `prompt-toolkit` | BSD-3 | ✅ |
| `pydantic` | MIT | ✅ |
| `httpx` | BSD-3 | ✅ |
| `torch` | BSD-3 | ✅ |
| `transformers` | Apache 2.0 | ✅ |
| `keyring` | MIT | ✅ |
| `platformdirs` | MIT | ✅ |
| `click` | BSD-3 | ✅ |

All dependencies are permissive-licensed. No GPL contamination risk.

### 19.3 Plugin License Compatibility

Claude Code plugins are licensed per-plugin (most MIT/Apache). Prysm's MIT license is compatible with all of them. The backward compatibility layer does not create a derivative work — it merely provides environment variables.

### 19.4 Data Privacy Considerations

| Data Type | Storage | Privacy |
|---|---|---|
| API keys | OS keyring (primary) | ✅ Not in code, not in git |
| Conversation history | SQLite (local) | ⚠️ User must be aware |
| Model files | User-specified path | ✅ User-controlled |
| System info | In-memory only | ✅ Not persisted |
| Usage stats | SQLite (local) | ✅ Not sent anywhere |

**Required:** Privacy notice in README and `prysm init` flow.

---

## 20. Documentation Quality (v1.2)

> **v1.2 Addition (Technical Writer review):** The original plan listed 9 documents but didn't define their quality standards or user journey.

### 20.1 Documentation Principles

1. **Quick start first**: Get users running in <60 seconds
2. **Progressive disclosure**: Simple → Advanced → Custom
3. **Copy-pasteable examples**: Every code block should work as-is
4. **Troubleshooting for every feature**: Each command page has a "Common Issues" section
5. **Visual where possible**: ASCII diagrams, screenshots, GIFs

### 20.2 User Journey Documentation

| Stage | Document | Goal |
|---|---|---|
| **Discovery** | README.md | Understand what Prysm is, see 30-second demo |
| **Installation** | README.md → Install | Install in one command, cross-platform |
| **First run** | Getting Started Guide | `prysm init` → first chat → first tool call |
| **Daily use** | Commands Reference | Look up any `/command` |
| **Advanced** | Runtimes Guide, Models Guide | GPU acceleration, model management |
| **Extension** | Plugins Guide, Contributing | Write plugins, contribute code |
| **Troubleshooting** | Troubleshooting Guide | Fix common issues |

### 20.3 Documentation Anti-Patterns to Avoid

- ❌ "Run `pip install`" without specifying which extras
- ❌ "Configure your API key" without showing where it's stored
- ❌ "Works on all platforms" without listing tested platforms
- ❌ No error messages in docs — always show expected error + fix
- ❌ No version numbers in examples — always pin to current version

### 20.4 Interactive Documentation

Consider a built-in `/docs` command that opens relevant documentation based on context:
```
> /docs runtime
→ Opens Runtimes Guide with your detected hardware pre-filled

> /docs plugin
→ Opens Plugin Development Guide with your installed plugins listed
```

---

## 21. Database Schema Refinement (v1.2)

> **v1.2 Addition (Database Engineer review):** The original SQLite schema has several issues: missing indexes, no migration strategy, no backup mechanism, and the `learnings` table is undefined.

### 21.1 Schema Improvements

```sql
-- Sessions (with indexes for common queries)
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    name TEXT,
    model_id TEXT NOT NULL,
    runtime_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    message_count INTEGER DEFAULT 0,
    token_count INTEGER DEFAULT 0
);
CREATE INDEX idx_sessions_updated ON sessions(updated_at DESC);
CREATE INDEX idx_sessions_model ON sessions(model_id);

-- Messages (with indexes for conversation retrieval)
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'tool_result', 'system')),
    content TEXT,
    tool_calls TEXT,  -- JSON array
    tokens INTEGER DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX idx_messages_session ON messages(session_id, id);
CREATE INDEX idx_messages_role ON messages(session_id, role);

-- Token Usage (with indexes for cost analysis queries)
CREATE TABLE usage (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    model_id TEXT NOT NULL,
    provider TEXT,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    cache_hit_tokens INTEGER DEFAULT 0,
    cost_usd REAL DEFAULT 0.0,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);
CREATE INDEX idx_usage_session ON usage(session_id);
CREATE INDEX idx_usage_model ON usage(model_id);
CREATE INDEX idx_usage_timestamp ON usage(timestamp DESC);

-- Plugin State
CREATE TABLE plugin_state (
    plugin_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    state_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (plugin_id, session_id),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

-- Learnings (cross-session learnings with index on category)
CREATE TABLE learnings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT NOT NULL CHECK(category IN ('preference', 'rules', 'workspace', 'general')),
    content TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT  -- Nullable ISO 8601 timestamp
);
CREATE INDEX idx_learnings_category ON learnings(category);

-- Schema version tracking (for migrations)
CREATE TABLE schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);
```

### 21.2 Migration Strategy

Use a version-based migration system (no external migration library needed for SQLite):

```python
# prysm/state/migrations.py
class MigrationManager:
    """Simple version-based SQLite migration system."""
    
    MIGRATIONS = [
        (1, "Initial schema", MIGRATION_001),
        (2, "Add provider column to usage", MIGRATION_002),
        # Future migrations added here
    ]
    
    def migrate(self, db: sqlite3.Connection) -> None:
        current = self._get_version(db)
        for version, description, sql in self.MIGRATIONS:
            if version > current:
                db.executescript(sql)
                db.execute(
                    "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                    (version, description)
                )
                db.commit()
```

### 21.3 Backup & Recovery

```python
# prysm/state/backup.py
class DatabaseBackup:
    """Automatic backup and recovery for state.db."""
    
    def backup(self, db_path: Path) -> Path:
        """Create timestamped backup before schema migration."""
        backup_path = db_path.parent / f"state.{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, backup_path)
        return backup_path
    
    def restore(self, backup_path: Path, db_path: Path) -> None:
        """Restore from backup if migration fails."""
        shutil.copy2(backup_path, db_path)
```

### 21.4 Data Integrity Rules

| Rule | Implementation |
|---|---|
| Message always belongs to a session | FOREIGN KEY with ON DELETE CASCADE |
| Role must be valid | CHECK constraint on role column |
| Timestamps are ISO 8601 | Application-level validation |
| No orphaned usage records | ON DELETE CASCADE on session_id |
| Schema changes are versioned | schema_version table |
| Backups before migrations | MigrationManager.backup() |

### 21.5 Performance Considerations

| Concern | Solution |
|---|---|
| Large conversation history | Paginate with LIMIT/OFFSET, load last N messages |
| WAL mode for concurrent access | `PRAGMA journal_mode=WAL` on connection |
| Connection pooling | Single connection per session, released on session end |
| Index bloat | Indexes only on columns used in WHERE/ORDER BY |
| Database size growth | Add vacuum command, auto-cleanup old sessions |

---

## 22. Key Design Decisions

### 22.1 Why Pure Python (Not Rust + Python Sidecar)

| Factor | Pure Python | Rust + Python Sidecar |
|---|---|---|
| LLM ecosystem access | ✓ Full (transformers, llama-cpp-python, vLLM) | ✗ Limited, must bind per-runtime |
| Development speed | ✓ Fast (single language, no FFI) | ✗ Slow (two languages, IPC protocol) |
| CLI performance | Fair (good enough for TUI) | ✓ Excellent |
| Distribution | ✓ `pip install prysm-cli` | ✓ Single binary, but larger |
| Plugin development | ✓ Any Python developer | ✗ Must know Rust for plugins |

**Verdict:** Pure Python for MVP. Re-evaluate Rust core in Phase 10 if CLI latency is an issue.

### 22.2 Why NOT Fork Claude Code (the actual binary)

- Claude Code is closed-source (proprietary license)
- Claude Code is tightly coupled to Anthropic's API
- Claude Code is written in TypeScript — limits local LLM integration
- Can't legally redistribute Claude Code modifications

### 22.3 Why Backward Compat With Claude Code Plugins

- Instant ecosystem of 13+ plugins on day 1
- Users can migrate incrementally
- Plugin authors don't need to rewrite for Prysm
- Hook protocol is generic (stdin/stdout subprocess) — no Claude dependency

### 22.4 OpenAI-Compatible API as Universal Bridge

All cloud providers are accessed through one of two paths:
1. **Direct SDK** (OpenAI, Anthropic, Google) — for native features (thinking, prompt caching)
2. **OpenAI-compatible** — for all other providers (vLLM, Together, Groq, DeepSeek, OpenRouter, etc.)

This means adding a new cloud provider is typically a 5-line config entry, not a code change.

### 22.5 Model Identity Format

```
Format: [provider|runtime]/[model-id]

Examples:
  local/codellama                  # Local GGUF file
  ollama/llama3.2:7b               # Ollama-managed model
  openai/gpt-4o                    # OpenAI API
  anthropic/claude-sonnet-4        # Anthropic API
  openrouter/anthropic/claude-3.5  # OpenRouter (provider as first segment)
  hf/microsoft/phi-4               # Hugging Face model ID
  remote/my-server/qwen2.5         # Custom remote runtime
```

---

## Appendix A: Open Architecture Insights

### Design Patterns Adopted from OpenCode

| Pattern | OpenCode | Prysm Adaptation |
|---|---|---|
| Provider tiers | Bundled SDK → Custom → Dynamic import | Bundled SDK → OpenAI-compat → User script |
| Model identity | `providerID/modelID` | `provider/runtime/model-id` |
| Config merge | CLI → project → global → remote | CLI → cwd → user → env |
| Auth storage | `auth.json` with env var fallback | `providers.json` + env vars |
| Permission system | `ask/deny/allow` per tool | Same (Claude Code compatible) |

### Design Patterns Adopted from Letta

| Pattern | Letta | Prysm Adaptation |
|---|---|---|
| Provider client hierarchy | Factory → ABC → Per-provider | Factory → RuntimeAdapter → Per-runtime/per-provider |
| Usage tracking | `LettaUsageStatistics` | SQLite `usage` table |
| Error classification | Unified error types | Same pattern |
| BYOK model | API key per provider | Same pattern |
| Session management | Database-backed | SQLite, same approach |

### Design Patterns Adopted from free-claude-code

| Pattern | free-claude-code | Prysm Adaptation |
|---|---|---|
| Provider descriptor | `ProviderDescriptor` dataclass | `RuntimeInfo` + `ProviderConfig` dataclasses |
| Transport abstraction | OpenAI Chat vs Anthropic Messages | `RuntimeAdapter` ABC |
| Model routing | `ModelRouter.resolve()` | `RuntimeSelector.recommend()` |
| Rate limiting | `GlobalRateLimiter` | Per-provider rate limiter |
| Gateway model IDs | `provider/model` format | `runtime/model` format |

---

*End of Plan — Prysm v0.1 Architecture & Implementation Blueprint*
