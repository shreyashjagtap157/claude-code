# Exhaustive Audit: Orchestration & CLI UI Rendering in Claude Code Plugins

**Repository:** `github.com/anthropics/claude-code` (plugins repository only)
**Commit:** `8bae02d` (HEAD on main)
**Date:** 2026-06-01
**Scope:** All 14 plugins, 3 repo-level commands, plugin system architecture

---

## Table of Contents

1. [Plugin System Architecture](#1-plugin-system-architecture)
2. [Orchestration Primitives](#2-orchestration-primitives)
3. [CLI UI Rendering Signals](#3-cli-ui-rendering-signals)
4. [Plugin-by-Plugin Analysis](#4-plugin-by-plugin-analysis)
5. [Cross-Plugin Pattern Catalog](#5-cross-plugin-pattern-catalog)
6. [Hook System Deep Analysis](#6-hook-system-deep-analysis)
7. [Agent System Deep Analysis](#7-agent-system-deep-analysis)
8. [Command System Deep Analysis](#8-command-system-deep-analysis)
9. [Skill System Deep Analysis](#9-skill-system-deep-analysis)
10. [Environment Variables & Paths](#10-environment-variables--paths)
11. [Orchestration Trade-offs & Decision Framework](#11-orchestration-trade-offs--decision-framework)

---

## 1. Plugin System Architecture

### 1.1 Directory Structure Convention

Every plugin follows this standardized layout:

```
plugin-name/
├── .claude-plugin/
│   └── plugin.json          # Manifest (REQUIRED)
├── commands/                 # Slash commands (auto-discovered .md files)
├── agents/                   # Subagent definitions (auto-discovered .md files)
├── skills/                   # Agent skills (subdirs with SKILL.md)
│   └── skill-name/
│       └── SKILL.md
├── hooks/
│   ├── hooks.json            # Event handler config
│   └── *.sh / *.py           # Hook handler scripts
├── hooks-handlers/           # Alternative handler location
│   └── *.sh
├── scripts/                  # Helper scripts
└── .mcp.json                 # MCP server definitions
```

**Auto-discovery**: All `.md` files in `commands/` and `agents/`, all `SKILL.md` in `skills/*/`, and `hooks/hooks.json` are auto-discovered.

### 1.2 Plugin Manifest (plugin.json)

```json
{
  "name": "plugin-name",              // Required, kebab-case
  "version": "1.0.0",                 // Recommended, semver
  "description": "...",               // Recommended
  "author": {"name": "...", "email": "..."},  // Recommended
  "homepage": "...",                  // Optional
  "repository": "...",                // Optional
  "license": "MIT",                   // Optional
  "keywords": ["..."],                // Optional
  "commands": "./custom-commands",    // Optional, custom paths
  "agents": ["./agents", "./..."],    // Optional, multiple paths
  "hooks": "./config/hooks.json",     // Optional
  "mcpServers": "./.mcp.json"         // Optional
}
```

**Critical rule**: Custom paths SUPPLEMENT defaults, they don't replace them. All standard directories load regardless.

### 1.3 Plugin Lifecycle

1. **Installation**: Plugin directory placed in `~/.claude/plugins/` (user) or project `.claude-plugin/` (project)
2. **Registration**: Claude Code reads `.claude-plugin/plugin.json` on session start
3. **Discovery**: Auto-scans `commands/`, `agents/`, `skills/*/`, `hooks/hooks.json`, `.mcp.json`
4. **Activation**: Components become available:
   - Commands appear in `/help` listing
   - Agents auto-trigger based on `description` field matching
   - Skills auto-load based on task context matching
   - Hooks fire on matching events
   - MCP servers auto-start
5. **Namespace**: Commands available as `/plugin-name:command-name`, agents as `plugin:subdir:agent-name`

---

## 2. Orchestration Primitives

The Claude Code plugin system exposes **4 orchestration primitives**:

### 2.1 Command Orchestration

Commands are Markdown files with YAML frontmatter. When a user types `/command-name`, the command body becomes Claude's instructions.

**Execution model**: Single message — Claude reads the command, executes the instructions in one or more tool calls, and produces output.

**Key orchestration patterns within commands**:
- **Multi-step sequential**: "Do X, then Y, then Z" (e.g., `commit-push-pr`: branch→commit→push→PR in single message)
- **Multi-agent parallel**: Command instructs Claude to launch multiple Task agents (e.g., `code-review`: 5 parallel agents)
- **Sequential agent launch**: Command instructs phased agent launches (e.g., `feature-dev`: 7 sequential phases)
- **Bash execution**: Inline `!`command` to gather context before processing
- **File references**: `@filepath` to inject file content into the command prompt
- **Argument interpolation**: `$ARGUMENTS`, `$1`, `$2`, etc. from user input

### 2.2 Agent Orchestration

Agents are autonomous subprocesses launched via the **Task tool**. When Claude determines an agent's description matches the current context, it launches the agent with:

```javascript
Task({
  description: "What the agent should do (from frontmatter)",
  prompt: "Detailed instructions for agent (from system prompt body)",
  subagent_type: "general"  // or "explore"
})
```

**Agent frontmatter fields**:
- `name`: Identifier (lowercase, hyphens, 3-50 chars)
- `description`: Triggering conditions + `<example>` blocks (the trigger matching mechanism)
- `model`: `inherit` | `sonnet` | `opus` | `haiku` (which model the subagent uses)
- `color`: `blue` | `cyan` | `green` | `yellow` | `magenta` | `red` (visual identity in UI)
- `tools`: Array of tool names (principle of least privilege)

**Agent triggering**:
1. User says something matching the `description` field
2. Claude (the orchestrator) decides to launch the agent
3. Claude uses the Task tool with `subagent_type` matching the agent
4. The agent gets the system prompt from the markdown body
5. Agent runs autonomously, calls tools, produces output
6. Agent returns result to orchestrator Claude
7. Orchestrator Claude presents results to user

**Important**: The orchestrator Claude decides WHEN and IF to launch agents. The `description` field is the ONLY mechanism for triggering — there's no automatic pattern matching. Claude is prompted (via examples in the description) to recognize scenarios and launch the agent.

### 2.3 Hook Orchestration

Hooks are event-driven scripts that fire automatically in response to Claude Code lifecycle events.

**Execution model**: Hook scripts run as subprocesses, receive JSON via stdin, output JSON via stdout. They run in **parallel** (all matching hooks for an event fire simultaneously).

**Hook types**:
- `command`: Executes a bash command/script
- `prompt`: Uses an LLM to evaluate (recommended for complex logic)

**Output format**:
```json
{
  "continue": true,          // false = halt processing
  "suppressOutput": false,   // hide from transcript
  "systemMessage": "...",    // shown to Claude
  "hookSpecificOutput": {    // varies by hook type
    "hookEventName": "...",
    "additionalContext": "...",
    "permissionDecision": "allow|deny|ask",
    "updatedInput": {...}
  }
}
```

**Exit codes**: `0`=success, `2`=blocking error (stderr→Claude), other=non-blocking error

**Hook events** (9 total):
| Event | When Fires | Use Case |
|-------|-----------|----------|
| `PreToolUse` | Before any tool runs | Approve/deny/modify tool calls |
| `PostToolUse` | After tool completes | Feedback, logging, reactions |
| `UserPromptSubmit` | When user submits a prompt | Add context, validate, block |
| `Stop` | When main agent considers stopping | Completeness check |
| `SubagentStop` | When subagent finishes | Task validation |
| `SessionStart` | Session begins | Load context, set environment |
| `SessionEnd` | Session ends | Cleanup, logging |
| `PreCompact` | Before context compaction | Preserve critical info |
| `Notification` | Claude sends notifications | Logging, reactions |

**Matchers**: Filter which tool calls trigger the hook — exact match, `|` for multiple, `*` for all, or regex like `mcp__.*`.

### 2.4 Skill Orchestration

Skills are reusable instruction files that Claude auto-loads when the task context matches the `description` field.

**Execution model**: When Claude decides the task matches a skill's description, it reads the skill's `SKILL.md` and incorporates the instructions into its working context.

**Skill structure**: `skills/skill-name/SKILL.md` with YAML frontmatter. Supporting files in `references/`, `examples/`, `scripts/` subdirectories.

**Skill description format** (third person):
```yaml
description: Use this skill when the user asks to [X], [Y], or [Z]. Also use when...
```

**Key difference from agents**: Skills add to Claude's context; agents run as separate processes. Skills are "passive knowledge injection"; agents are "active autonomous execution."

### 2.5 Combined Orchestration Patterns

The most sophisticated plugins combine all four:

**feature-dev** (the most complex plugin):
1. User types `/feature-dev my-feature`
2. Command loads → Claude reads the command body
3. Phase 1: Claude interacts with user via AskUserQuestion
4. Phase 2-7: Claude launches sub-agents via Task tool
5. Each agent returns results → Claude aggregates and presents

**security-guidance** (the most complex hook setup):
1. SessionStart hook loads security context
2. PreToolUse hooks evaluate every Write/Edit/Bash tool call for security issues
3. Stop hook performs comprehensive security review before Claude stops
4. UserPromptSubmit hook adds security reminders
5. PostToolUse hooks react to tool results

---

## 3. CLI UI Rendering Signals

The plugins repository does NOT contain the Claude Code CLI rendering engine (that's in the closed-source `@anthropic-ai/claude-code` npm package). However, it provides strong signals about how the UI renders:

### 3.1 Agent Colors (6 colors)

Agents have a `color` frontmatter field that maps to visual identity:

| Color    | Semantic Meaning | Usage Examples |
|----------|-----------------|----------------|
| `blue`   | Analysis, review | code-reviewer, comment-analyzer |
| `cyan`   | Tests, verification | pr-test-analyzer, skill-reviewer |
| `green`  | Success, generation | code-simplifier, code-architect, code-explorer |
| `yellow` | Caution, validation | plugin-validator, silent-failure-hunter, ralph-wiggum agents |
| `red`    | Security, critical | code-reviewer (critical agent), security-analyzer |
| `magenta`| Creative, transformation | agent-creator |

**Implication**: The CLI renders agent output with color-coded headers/borders/sidebars. Users see a colored badge or label indicating which agent is responding.

**Color distribution across all agents**:
- green: 6 agents (most common)
- yellow: 5 agents
- red: 3 agents (but only code-reviewer pr-review-toolkit)
- blue: 2 agents
- cyan: 2 agents
- magenta: 1 agent

### 3.2 Model Visibility

Agent frontmatter specifies `model`:
- `inherit`: Uses the parent session's model (most common — 10+ agents)
- `sonnet`: Explicitly Claude Sonnet (3 agents: code-explorer, agent-sdk-verifier-py, agent-sdk-verifier-ts)
- `opus`: Explicitly Claude Opus (2 agents: code-reviewer in pr-review-toolkit, code-simplifier)

**Implication**: The UI likely shows which model a subagent is using, perhaps in a header/badge alongside the color.

### 3.3 Hook Output Rendering Patterns

Hooks inject content into the transcript via `hookSpecificOutput.additionalContext` and `systemMessage`:

**Pattern A: System Message Injection** (explanatory-output-style)
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "You are in 'explanatory' output style mode..."
  }
}
```
This adds invisible context to the system prompt — the user never sees it directly, but it changes Claude's behavior.

**Pattern B: Visual Separator** (explanatory-output-style)
```
`★ Insight ─────────────────────────────────────`
[2-3 key educational points]
`─────────────────────────────────────────────────`
```
This is a user-visible formatting pattern using backtick-delimited code-style lines with Unicode characters and dashes to create a visual divider in the terminal. The `★` is U+2605.

**Pattern C: Structured Reports** (security-guidance, code-review)
Security and code review hooks produce JSON-like structured output with severity levels. The UI presumably formats these as collapsible sections or bullet lists.

**Pattern D: Hook output context** (ralph-wiggum)
The ralph-wiggum stop hook outputs iteration tracking data via `additionalContext`, which gets fed back to Claude on the next iteration. The user sees iteration number and progress.

### 3.4 Tool Output Display

**Task tool rendering**: When Claude launches a subagent via the Task tool, the subagent's output is returned to the orchestrator Claude, which then presents it to the user. The CLI likely shows:
- A header with agent name/color/model
- The agent's output (structured or free text)
- An "Agent completed" footer

**Bash tool rendering**: The `!`command`` inline execution happens transparently — the result feeds into the command processing but the user may or may not see the raw output.

**Hook execution display**: Hook scripts run in the background. Their stdout appears in the transcript (unless `suppressOutput: true`). Users running `claude --debug` see detailed hook registration, execution, input/output JSON, and timing.

### 3.5 Confidence Scoring Display

Two plugins use numeric confidence/severity scoring that likely affects UI rendering:

**code-review** (5-agent parallel):
```yaml
confidence_levels:
  high: "≥ 90"
  medium: "≥ 80"
  low: "< 80"
```

**pr-review-toolkit agents**:
- code-reviewer: Score 0-100 (91-100 = critical)
- pr-test-analyzer: Rate 1-10 (10 = absolutely essential)
- type-design-analyzer: Rate 4 dimensions 1-10

**Implication**: The CLI likely renders these as colored badges (red for critical, yellow for warning, green for info) or in a severity-sorted list.

### 3.6 Command Argument Hints

Commands with `argument-hint` frontmatter appear in `/help` with argument suggestions. This drives autocomplete and usage documentation.

### 3.7 Allowed-Tools Display

Commands with `allowed-tools` restrictions display only available tools. The CLI presumably grays out or hides unavailable tools.

---

## 4. Plugin-by-Plugin Analysis

### 4.1 code-review (Boris Cherny)

**Orchestration pattern**: 5-agent parallel with confidence-based filtering

**Components**: 1 command (`code-review.md`), 5 agents

**Command execution flow**:
1. User types `/code-review [scope]`
2. Claude reads `$ARGUMENTS` to determine scope
3. Claude creates a todo list
4. Claude reads `git diff HEAD` to get changes
5. Claude launches 5 agents IN PARALLEL (single Task call batch):
   - `codebase-architect` (green, opus): Architecture review
   - `business-logic-analyzer` (yellow, opus): Business logic review
   - `code-style-enforcer` (blue, opus): Style and formatting
   - `security-analyzer` (red, opus): Security analysis
   - `test-quality-advisor` (cyan, opus): Test coverage
6. ALL 5 agents run in parallel as independent subprocesses
7. Claude aggregates all 5 results
8. Claude filters issues by confidence level (≥90 high, ≥80 medium, <80 low)
9. Claude writes structured output as a GitHub comment (optional) and presents summary
10. User can follow up with specific agents for detail

**Key orchestration innovation**: True parallel execution. All 5 agents run simultaneously, each on its own model instance. The orchestrator Claude waits for all to complete, then merges/filters results.

**Confidence scoring mechanism**: Each issue gets a 0-100 score embedded in the agent's system prompt. The orchestrator uses thresholds to filter: only show ≥80 by default, `--detailed` also shows <80.

**colors used**: green, yellow, blue, red, cyan, plus uncolored orchestrator

### 4.2 feature-dev (Siddharth Bidasaria)

**Orchestration pattern**: 7-phase sequential workflow with subagent delegation and user interaction

**Components**: 1 command (`feature-dev.md`), 3 agents

**Command execution flow**:
1. User types `/feature-dev [description]`
2. **Phase 1 — Discovery**: Claude asks clarifying questions via AskUserQuestion tool (what, where, requirements, test strategy). All questions asked at once.
3. **Phase 2 — Codebase Exploration**: Launches `code-explorer` agent (sonnet, yellow) via Task tool. Agent reads relevant files, returns findings.
4. Claude presents exploration findings to user.
5. **Phase 3 — Architecture Design**: Launches `code-architect` agent (sonnet, green) via Task tool. Creates plan with requirements, affected files, data flow, UI, testing strategy.
6. Claude presents architecture to user and asks for approval.
7. **Phase 4 — Implementation**: Claude implements code changes directly (no subagent). Uses a focused approach: "Focus on readability and maintainability. Avoid over-engineering."
8. **Phase 5 — Review**: Launches `code-reviewer` agent (sonnet, red) via Task tool. Reviews implementation with scoring.
9. Claude presents review findings to user.
10. **Phase 6 — Polish**: "Address the issues raised by code-reviewer. Be judicious — don't change everything, focus on real issues."
11. **Phase 7 — Done**: Lists what was implemented, skipped, and future improvements.

**Key orchestration innovation**: Sequential phased execution with user interaction at decision gates. Each phase feeds into the next. User approval gates at Architecture (Phase 3) and Review (Phase 5).

**Interaction pattern**: Uses AskUserQuestion at phase boundaries. All questions asked simultaneously in Phase 1.

**colors used**: yellow (code-explorer), green (code-architect), red (code-reviewer)

### 4.3 ralph-wiggum (Daisy Hollman)

**Orchestration pattern**: Iterative self-referential loop via Stop hook + state files

**Components**: 3 commands, 3 agents, hooks (Stop), scripts

**Execution flow**:
1. User types `/ralph-loop "task description"` or asks Claude directly
2. Setup script (`setup-ralph-loop.sh`) runs: creates state file at `$CLAUDE_PROJECT_DIR/.ralph-state.md` with YAML frontmatter (iteration, max iterations, task, conversation log, promises)
3. Claude starts working on the task
4. **Stop hook** (`stop-hook.sh`, 580+ lines) fires when Claude considers stopping:
   a. Reads state file, increments iteration counter
   b. Detects "promises" (TODO patterns) in Claude's response using grep patterns
   c. Extracts promise descriptions using regex on "I'll | I will | Let me | I should" patterns
   d. If max iterations not reached: outputs `additionalContext` with previous iteration info → forces Claude to continue
   e. If max iterations reached: outputs completion summary → allows stop
5. Claude continues with context of previous iterations
6. User types `/cancel-ralph` to clean up: removes state file, stops the loop

**Stop hook output format**:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "Stop",
    "additionalContext": "## Previous Work\n..."
  },
  "systemMessage": "...",
  "continue": true
}
```

**Exit code semantics**: Exit 2 forces Claude to continue (blocking error → fed back). Exit 0 allows stop.

**State file format** (`.ralph-state.md`):
```yaml
---
iteration: 3
max_iterations: 10
task: "description"
---
```

**Promises mechanism**: Detects implicit promises (I'll, I will, Let me, I should) and explicit TODOs, extracts them as structured items with regex, adds to state file for next iteration.

**Key orchestration innovation**: Using Stop hook as a continuation mechanism — the hook intercepts Claude's natural stopping point and forces it to continue. State file is the cross-iteration persistence mechanism. This is the ONLY plugin that uses a Stop hook for orchestration rather than validation.

### 4.4 security-guidance (David Dworken)

**Orchestration pattern**: Multi-hook security validation with agentic commit review

**Components**: hooks (SessionStart, UserPromptSubmit, PreToolUse, PostToolUse, Stop), 12 hook scripts

**Hook execution flow**:

**SessionStart hook**: 2192-line Python script (`security_reminder_hook.py`)
1. Checks git diff baseline via `diffstate.py` (reads `.claude/security-guidance-diff-sha`)
2. Prompts user with security reminders
3. Outputs via `additionalContext` to inject into system prompt

**PreToolUse hooks**:
- `pretooluse.py`: Validates Write/Edit/Bash tool calls against vulnerability patterns
  - Uses `patterns.py` (25+ regex patterns): SQL injection ($SQL_INJECTION), XSS ($XSS_PATTERNS), SSRF, Command Injection, Path Traversal, Server-Side Request Forgery, Insecure Direct Object References, Security Misconfiguration, Sensitive Data Exposure, Broken Authentication, XML External Entities, Deserialization attacks, Hardcoded secrets/API keys/tokens/passwords
  - Checks file paths against `.claude/security-guidance-paths.txt`
  - Returns `permissionDecision: "ask"` to prompt user for confirmation
  - Uses `asyncRewake: true` for non-blocking pattern check

**PostToolUse hooks**:
- `posttooluse.py`: Logs tool usage, checks for security issues created by edits
- `review_api.py`: Public API for agentic commit review — calls Claude API independently via `llm.py`

**UserPromptSubmit hook**: Injects security reminders via `additionalContext`. Matches prompt against security patterns.

**Stop hook** (`stop-hook.py`): Performs final security sweep — runs `git diff` through all patterns, calls `llm.py` for agentic review of the entire diff using Claude API.

**Async rewake mechanism**: `asyncRewake: true` in hook config means the hook runs in background and injects results later — doesn't block the main flow.

**Colors used**: red (security-analyzer agent — in code-review plugin's scope)

**Key orchestration innovation**: Multiple hook types working together (4 event types), Python-based hook scripts (not bash), external LLM API calls from hooks for agentic review, async rewake for non-blocking validation, git SHA baseline tracking with TTL (Time-To-Live) to avoid re-scanning unchanged files.

### 4.5 hookify (Daisy Hollman)

**Orchestration pattern**: User-configurable rule-based hooks with regex validation

**Components**: 3 commands, 4 hooks, 1 agent, core engine (2 Python files)

**Execution flow**:
1. User writes rules in `.claude/hookify.*.local.md` files (markdown with YAML frontmatter)
2. User types `/hookify` to activate rules
3. `config_loader.py` reads all `.claude/hookify.*.local.md` files
4. `rule_engine.py` parses rules and compiles regex patterns (with caching)
5. Hooks fire on events matching the rules

**Hook script flow**:
- `pretooluse.py`: Checks tool input against rules via rule_engine. Can block tool calls.
- `posttooluse.py`: Evaluates tool results against rules.
- `stop.py`: Validates completion against rules.
- `userpromptsubmit.py`: Checks user prompts against rules.

**conversation-analyzer agent** (model: inherit): Detects unwanted conversation patterns. Launched by hooks when a pattern matches.

**Rule format** (in `.local.md`):
```markdown
---
name: no-debug-logs
event: PreToolUse
tool: Write
---
description: Prevent debug log statements in production code
pattern: console\.(log|debug|trace)\(
action: deny
message: Remove debug statements before committing
```

**Key orchestration innovation**: Rule-based hook activation driven by user-editable markdown files. Multi-event rules (same rule can apply to different hook events). Regex pattern caching in rule_engine.py for performance.

### 4.6 commit-commands (Anthropic)

**Orchestration pattern**: Single-message orchestration with tool restrictions

**Components**: 3 commands (no agents, no hooks)

**`commit` command**: Single-message orchestration
1. Reads `ARGUMENTS` for commit message
2. Runs `git add -A` (if no files specified)
3. Runs `git commit -m "$ARGUMENTS"` (or prompts for message)
4. Handles commit failure (stash, retry, etc.)
5. All steps in ONE message — no user interaction, no agent launch

**`commit-push-pr` command**: Multi-step single-message
1. Creates new branch if on main (`git checkout -b`)
2. Stages all changes (`git add`)
3. Creates commit with auto-generated message
4. Pushes branch (`git push`)
5. Creates PR (`gh pr create`)
6. **Mandatory**: "You MUST do all of the above in a single message."

**`clean_gone` command**: Git branch cleanup
1. Runs `git fetch --prune`
2. Lists merged/gone branches
3. Deletes local branches tracking deleted remotes
4. Handles worktrees with `git worktree list`
5. Skips current branch and worktree-attached branches

**Key orchestration innovation**: `allowed-tools` restrictions enforce tool discipline (Bash(git only) for commit, specific git + gh tools for commit-push-pr). Single-message constraint forces all steps in one response. No feedback loops — fire and forget.

### 4.7 agent-sdk-dev (Ashwin Bhat)

**Orchestration pattern**: Interactive scaffold + verification agent

**Components**: 1 command, 2 agents

**`new-sdk-app` command flow**:
1. Asks ONE question at a time (Language → Project name → Agent type → Starting point → Tooling). Explicit instruction: "Ask these questions one at a time. Wait for the user's response before asking the next question."
2. Uses WebFetch to read SDK docs for latest version
3. Creates project files
4. Runs TypeScript type checking (`npx tsc --noEmit`)
5. Launches verifier agent: `agent-sdk-verifier-ts` or `agent-sdk-verifier-py`
6. Verifier agent reads all files, references SDK docs via WebFetch, produces structured report

**Agents**:
- `agent-sdk-verifier-py` (sonnet, no color): Python SDK verification
- `agent-sdk-verifier-ts` (sonnet, no color): TypeScript SDK verification
- Both produce structured report: Overall Status (PASS | PASS WITH WARNINGS | FAIL) + Critical Issues + Warnings + Passed Checks + Recommendations

**Key orchestration innovation**: Sequential question-asking (one at a time, not batched). Post-scaffold verification via subagent. WebFetch integration for live documentation reference.

### 4.8 pr-review-toolkit (Daisy)

**Orchestration pattern**: Agent battery with parallel/sequential launch options

**Components**: 1 command, 6 agents

**`review-pr` command flow**:
1. Parses arguments to determine review scope
2. Checks `git diff --name-only` for changed files
3. Determines applicable reviews based on file types
4. Launches agents either sequentially or in parallel

**6 agents (color/model)**:
1. `code-reviewer` (green, opus): General code review, 0-100 confidence scoring, ≥80 threshold
2. `silent-failure-hunter` (yellow, inherit): Error handling auditor, severity levels (CRITICAL/HIGH/MEDIUM)
3. `comment-analyzer` (green, inherit): Comment accuracy, identifies comment rot
4. `pr-test-analyzer` (cyan, inherit): Test coverage, 1-10 rating
5. `type-design-analyzer` (pink, inherit): Type design, 4-dimension 1-10 ratings
6. `code-simplifier` (no color, opus): Code simplification, preserves functionality

**Key orchestration innovation**: Agents can run in parallel (faster) or sequential (deeper analysis, each informed by previous). Results aggregated into structured PR comment format with severity grouping. Different confidence scoring systems per agent. "pink" is a unique color not used elsewhere.

### 4.9 frontend-design (Prithvi Rajasekaran & Alexander Bricken)

**Orchestration pattern**: Passive skill (no commands, no agents, no hooks)

**Components**: 1 skill (`SKILL.md`)

**Skill content**: Frontend design guidelines covering:
- Bold aesthetic direction (purpose, tone, constraints, differentiation)
- Typography guidelines (distinctive fonts, no generic fonts like Inter/Arial/Roboto)
- Color & theme (cohesive palettes, CSS variables, sharp accent colors)
- Motion design (CSS animations, scroll-triggering, hover states)
- Spatial composition (asymmetry, overlap, diagonal flow, grid-breaking)
- Backgrounds & visual details (gradient meshes, noise textures, geometric patterns)
- Anti-patterns to avoid (no purple-on-white gradients, no Space Grotesk, no generic AI slop)

**Activation**: Auto-triggers when Claude detects frontend/UI work in the conversation.

### 4.10 explanatory-output-style (Dickson Tsai)

**Orchestration pattern**: SessionStart hook — system prompt augmentation

**Components**: 1 hook (SessionStart)

**Hook execution** (`session-start.sh`):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "You are in 'explanatory' output style mode..."
  }
}
```

**What it does**: Adds instructions for Claude to provide educational insights about implementation choices. Defines a visual output format:
```
`★ Insight ─────────────────────────────────────`
[2-3 key educational points]
`─────────────────────────────────────────────────`
```

**Key orchestration innovation**: SessionStart hooks as system prompt modifiers. Equivalent to CLAUDE.md but distributable via plugins. Backtick-delimited visual separators with Unicode star character.

### 4.11 learning-output-style (Boris Cherny)

**Orchestration pattern**: SessionStart hook — interactive learning mode

**Components**: 1 hook (SessionStart)

**Hook execution** (`session-start.sh`):
```json
{
  "hookSpecificOutput": {
    "hookEventName": "SessionStart",
    "additionalContext": "You are in 'learning' output style mode..."
  }
}
```

**What it does**: Adds instructions for interactive learning — Claude identifies 5-10 line code sections for the user to write. Includes both learning and explanatory modes.

**When to request user contributions**: Business logic, error handling, algorithm choices, data structures, UX decisions, design patterns.

**When NOT to request**: Boilerplate, obvious implementations, configuration, simple CRUD.

**Key orchestration innovation**: Same pattern as explanatory-output-style (SessionStart hook + additionalContext), but content focuses on interactive participation rather than passive explanation.

### 4.12 claude-opus-4-5-migration (William Hu)

**Orchestration pattern**: Passive skill (no commands, no agents, no hooks)

**Components**: 1 skill (`SKILL.md`)

**Skill content**: Migration guide covering:
- Model string mapping (4 platforms × 3 source models → Opus 4.5)
- Unsupported beta headers to remove
- Prompt adjustments (tool overtriggering, over-engineering, under-exploration, thinking sensitivity)
- Over 20 specific model string patterns across platforms

**Activation**: Auto-triggers when user asks about model migration.

### 4.13 plugin-dev (Daisy Hollman)

**Orchestration pattern**: Self-referential meta-plugin — the toolkit for building plugins

**Components**: 1 command, 3 agents, 7 skills (the most comprehensive plugin)

**7 skills**:
1. `plugin-structure`: Directory layout, manifest format, auto-discovery, portable paths
2. `command-development`: YAML frontmatter, `$ARGUMENTS`, `$1-$9`, `!`bash``, `@file`, `allowed-tools`, `CLAUDE_PLUGIN_ROOT`
3. `agent-development`: Agent file format, frontmatter fields, description with examples, system prompt design, colors/tools/models
4. `hook-development`: Hook types (command vs prompt), events, matchers, output format, parallel execution, security best practices
5. `skill-development`: SKILL.md format, description best practices, progressive disclosure
6. `mcp-integration`: MCP server types (stdio/SSE), authentication, tool naming
7. `plugin-settings`: Settings files, `.local.md` format, configuration patterns

**3 agents**:
1. `agent-creator` (magenta, sonnet): AI-assisted agent generation. Takes user description, outputs complete agent file with frontmatter, examples, system prompt
2. `plugin-validator` (yellow, inherit): Comprehensive plugin validation — checks manifest, directory structure, commands, agents, skills, hooks, MCP, naming conventions, security
3. `skill-reviewer` (cyan, inherit): Skill quality review — evaluates description, trigger phrases, progressive disclosure, content quality

**1 command**: `create-plugin` — 7-phase end-to-end plugin creation workflow:
1. Discovery → 2. Component Planning → 3. Detailed Design → 4. Structure Creation → 5. Component Implementation → 6. Validation → 7. Testing & Documentation

**Key orchestration innovation**: Self-referential — the plugin uses its OWN agents and skills during development. `create-plugin` command loads plugin-structure skill, then loads skill-development/command-development/agent-development/hook-development skills at appropriate phases. It launches agent-creator for agent creation, plugin-validator for validation, skill-reviewer for skill review.

### 4.14 Repo-level Commands

**`triage-issue`**: GitHub issue triage with allowed-tools restrictions (`Bash(./scripts/gh.sh:*)`). Uses CLI wrappers for `gh` and label editing. Conditional logic based on event type (issues vs issue_comment). No agents — purely command-driven orchestration.

**`dedupe`**: Duplicate issue detection. 5 parallel search agents → filter agent → comment script. True parallel launch pattern: "launch 5 parallel agents to search Github for duplicates."

**`commit-push-pr`**: Same as commit-commands plugin version — single-message orchestration constraint.

---

## 5. Cross-Plugin Pattern Catalog

### 5.1 Orchestration Patterns

| Pattern | Plugin(s) | Description |
|---------|-----------|-------------|
| **Parallel agents** | code-review, dedupe (repo) | Multiple agents launched simultaneously via Task tool |
| **Sequential phases** | feature-dev, create-plugin | Phases execute in order, each feeding into next |
| **Hybrid parallel/sequential** | pr-review-toolkit | Configurable — sequential by default, parallel on request |
| **Iterative loop** | ralph-wiggum | Stop hook forces continuation with accumulated context |
| **Single-message fire** | commit-commands | All steps in one message, no user feedback loops |
| **Interactive scaffold** | agent-sdk-dev | One-at-a-time questions, then execute |
| **Passive skill** | frontend-design, claude-opus-4-5-migration | Auto-triggered knowledge injection |
| **Hook-based augmentation** | explanatory-output-style, learning-output-style | SessionStart hook adds context |
| **Multi-hook security** | security-guidance | 4+ hook types working together |
| **Rule-driven hooks** | hookify | User-editable rules drive hook behavior |
| **Meta-orchestration** | plugin-dev | Plugin builds plugins using itself |

### 5.2 Agent Launch Patterns

```markdown
# Pattern 1: Parallel launch (code-review)
Launch ALL 5 agents simultaneously:
<Task tool> codebase-architect
<Task tool> business-logic-analyzer
<Task tool> code-style-enforcer
<Task tool> security-analyzer
<Task tool> test-quality-advisor

# Pattern 2: Sequential launch (feature-dev)
Phase 2: Launch code-explorer agent
→ Wait for result → Present to user
Phase 3: Launch code-architect agent
→ Wait for result → Present to user → Get approval
Phase 5: Launch code-reviewer agent
→ Wait for result → Present to user

# Pattern 3: Multi-search parallel (dedupe)
Launch 5 parallel agents to search for duplicates
→ Feed all results into filter agent
→ Execute comment script

# Pattern 4: Proactive trigger (pr-review-toolkit)
Agent triggers based on context matching:
- After writing code → code-reviewer
- After adding docs → comment-analyzer
- Before creating PR → multiple agents
- After adding types → type-design-analyzer
```

### 5.3 User Interaction Patterns

| Pattern | Plugin | Mechanism |
|---------|--------|-----------|
| **Batch questions** | feature-dev Phase 1 | AskUserQuestion — all asked at once |
| **Sequential questions** | agent-sdk-dev | AskUserQuestion — one at a time, wait for each |
| **Approval gate** | feature-dev Phase 3 | "Ask user to approve before proceeding" |
| **No interaction** | commit-commands | "You MUST do all in a single message" |
| **Interactive learning** | learning-output-style | "Ask user to write 5-10 lines of code" |

### 5.4 Tool Restriction Patterns

| Pattern | Syntax | Example |
|---------|--------|---------|
| **Specific tools** | `allowed-tools: Read, Write, Edit` | `review-pr` |
| **Bash subcommands** | `Bash(git:*)` | `commit`, `commit-push-pr` |
| **Bash with scripts** | `Bash(./scripts/gh.sh:*)` | `triage-issue` |
| **Array format** | `allowed-tools: ["Read", "Write", "Grep"]` | `create-plugin` |
| **No restriction** | Field omitted | Most commands |

### 5.5 Argument Passing Patterns

| Pattern | Syntax | Example |
|---------|--------|---------|
| **All arguments** | `$ARGUMENTS` | `/commit added user auth` → `$ARGUMENTS` = "added user auth" |
| **Positional** | `$1`, `$2`, `$3` | `/review-pr 123 high` → `$1`=123, `$2`=high |
| **Mixed** | `$1`, `$3` (rest) | `/deploy api staging --force` → `$1`=api, `$3`="--force" |
| **None** | No hint | `/ralph-loop` — uses conversational input |

### 5.6 Bash Execution Patterns

| Pattern | Syntax | Purpose |
|---------|--------|---------|
| **Inline context** | ``!`git diff --name-only` `` | Get changed files |
| **Validation** | ``!`test -f $1 && echo "EXISTS"` `` | Check file existence |
| **Script execution** | ``!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/setup.sh` `` | Run plugin scripts |
| **Chained check** | ``!`command 2>&1 || echo "FAILED"` `` | Error handling |

---

## 6. Hook System Deep Analysis

### 6.1 Hook Configuration Structures

**Plugin format** (wrapped):
```json
{
  "description": "Optional description",
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {"type": "command", "command": "...", "timeout": 30},
          {"type": "prompt", "prompt": "Evaluate...", "timeout": 30}
        ]
      }
    ]
  }
}
```

**Settings format** (flat):
```json
{
  "PreToolUse": [
    {
      "matcher": "Write|Edit",
      "hooks": [
        {"type": "command", "command": "..."}
      ]
    }
  ]
}
```

### 6.2 Input Format (stdin JSON)

All hooks receive via stdin:

```json
{
  "session_id": "abc123",
  "transcript_path": "/path/to/transcript.txt",
  "cwd": "/current/working/dir",
  "permission_mode": "ask|allow",
  "hook_event_name": "PreToolUse"
}
```

**Event-specific fields**:
- **PreToolUse**: `tool_name`, `tool_input`
- **PostToolUse**: `tool_name`, `tool_input`, `tool_result`
- **UserPromptSubmit**: `user_prompt`
- **Stop/SubagentStop**: `reason`

### 6.3 Detailed Hook Implementations

**PreToolUse hooks** (security-guidance, hookify):
- Receive: `tool_name`, `tool_input`
- Can: Approve, deny, or ask for permission
- Can: Modify tool input (`updatedInput`)
- Output key: `hookSpecificOutput.permissionDecision` ("allow"|"deny"|"ask")
- Exit 0 = allow (or no opinion), Exit 2 = deny (block)

**PostToolUse hooks** (security-guidance):
- Receive: `tool_name`, `tool_input`, `tool_result`
- Can: Log, analyze, inject system messages
- Output: `systemMessage` fed back to Claude
- Exit 0: stdout shown in transcript

**Stop hooks** (ralph-wiggum, security-guidance, hookify):
- Receive: `reason` (why Claude thinks it should stop)
- Can: Approve stop (exit 0) or force continue (exit 2)
- Can: Inject `additionalContext` to influence next iteration
- ralph-wiggum: Uses Exit 2 to force continuation
- security-guidance: Uses Exit 0 or 2 based on security check results

**SessionStart hooks** (explanatory-output-style, learning-output-style, security-guidance):
- Receive: basic session info
- Can: Inject system prompt additions via `additionalContext`
- Can: Set environment variables via `$CLAUDE_ENV_FILE`
- **Persist env vars**: `echo "export VAR=value" >> "$CLAUDE_ENV_FILE"`

**UserPromptSubmit hooks** (security-guidance, hookify):
- Receive: `user_prompt`
- Can: Inject context, security reminders, or deny prompt

### 6.4 Async Rewake (unique to security-guidance)

```json
{
  "PostToolUse": [
    {
      "matcher": "Write|Edit",
      "asyncRewake": true,
      "hooks": [...]
    }
  ]
}
```

**What it does**: The hook runs in the background without blocking the main conversation flow. When the hook completes, its result is injected later (rewaken) into the conversation. Used for non-blocking security pattern scanning — the hook scans the file after it's written and injects warnings if issues are found.

### 6.5 Parallel Hook Execution

**Rule**: All hooks matching the same event AND the same matcher run in parallel:
```json
{
  "PreToolUse": [
    {
      "matcher": "Write",
      "hooks": [
        {"type": "command", "command": "check1.sh"},  // parallel
        {"type": "command", "command": "check2.sh"},  // parallel
        {"type": "prompt", "prompt": "Validate..."}   // parallel
      ]
    }
  ]
}
```

**Design implications**: Hooks cannot depend on each other's output. Non-deterministic ordering. Design for independence.

---

## 7. Agent System Deep Analysis

### 7.1 Triggering Mechanism

The `description` field in agent frontmatter is the triggering mechanism. It works through:

1. **<example> blocks**: Provide concrete scenarios showing when the agent should trigger
2. **Context demonstration**: Each example shows: Context → user message → assistant response → commentary explaining WHY the agent triggers
3. **Proactive + reactive**: Examples show both user-requested and assistant-proactive triggering

**Example breakdown** (from `agent-creator.md`):
```markdown
<example>
Context: User wants to create a code review agent
user: "Create an agent that reviews code for quality issues"
assistant: "I'll use the agent-creator agent to generate the agent configuration."
<commentary>
User requesting new agent creation, trigger agent-creator to generate it.
</commentary>
</example>
```

The commentary section is critical — it explains the reasoning for triggering, helping Claude's orchestrator learn when to use this agent.

### 7.2 Tool Availability

Agents can restrict tools via the `tools` frontmatter:

| Restriction | Example | Use Case |
|-------------|---------|----------|
| No restriction | Field omitted | code-reviewer (full access) |
| Read-only | `["Read", "Grep", "Glob"]` | plugin-validator, skill-reviewer |
| Code generation | `["Read", "Write", "Grep"]` | agent-creator |
| Full analysis | `["Read", "Write", "Edit", "Grep", "Glob", "Bash", "Task"]` | code-explorer, code-architect |
| Test & analysis | `["Read", "Bash", "Grep"]` | (common pattern) |

**Principle**: Least privilege. The absence of a tool restriction means access to ALL tools.

### 7.3 Agent to Agent Communication

Agents do NOT directly communicate with each other. Communication patterns:

| Pattern | How It Works | Example |
|---------|-------------|---------|
| **Orchestrator-mediated** | Claude launches agent A → gets result → launches agent B with A's result embedded in prompt | feature-dev (explorer→architect→reviewer) |
| **Parallel collection** | Claude launches A,B,C simultaneously → collects all results → merges | code-review (5 agents) |
| **Filter chain** | Claude launches A,B,C,D,E → launches filter agent F with all results → filter returns deduplicated | dedupe (repo) |

### 7.4 Agent Model Selection

| Model | When Used | Rationale |
|-------|-----------|-----------|
| `inherit` | Default for most agents | Uses same model as parent session — no extra cost for trivial agents |
| `sonnet` | Agents needing specific capability | Cheaper than opus but more capable than haiku. Used for focused tasks like code exploration |
| `opus` | Critical analysis agents | Used for code review (complex reasoning), code simplification (nuanced judgment). More expensive but higher quality |

**Recommendation** from `agent-development` skill: "Use `inherit` unless agent needs specific model capabilities."

---

## 8. Command System Deep Analysis

### 8.1 Frontmatter Fields (complete reference)

| Field | Type | Required | Purpose |
|-------|------|----------|---------|
| `description` | string | No | Shown in `/help` (falls back to first line of body) |
| `allowed-tools` | string/array | No | Restrict tools (inherits from conversation by default) |
| `model` | string | No | Override model (sonnet/opus/haiku) |
| `argument-hint` | string | No | Document arguments for autocomplete |
| `hide-from-slash-command-tool` | bool | No | Prevent programmatic invocation |
| `disable-model-invocation` | bool | No | Prevent SlashCommand tool from calling it |

### 8.2 Dynamic Argument Substitution

Commands support runtime substitution:

- `$ARGUMENTS`: All arguments as a single string
- `$1`, `$2`, ..., `$9`: Positional arguments
- `$@`: All remaining arguments after positional ones
- ``!`command` ``: Inline bash execution, result substituted into command
- `@filepath`: File content injected at that point

### 8.3 Project vs Plugin vs User Commands

| Scope | Location | Shown in `/help` as |
|-------|----------|---------------------|
| Project | `.claude/commands/` | "(project)" |
| Plugin | `plugin-name/commands/` | "(plugin-name)" |
| User (personal) | `~/.claude/commands/` | "(user)" |

All three scopes merge — commands are available simultaneously.

---

## 9. Skill System Deep Analysis

### 9.1 Skill Structure

```
skills/skill-name/
├── SKILL.md           # Required: Core skill content
├── references/        # Reference material (deeper docs)
├── examples/          # Working code examples
└── scripts/           # Utility scripts
```

### 9.2 SKILL.md Format

```yaml
---
name: Skill Name
description: Use this skill when [specific scenario]. Also use when [related scenarios].
license: ...
version: ...
---
```

**Body writing style**: Third person, imperative form. "To do X, follow Y." Not "You should do X."

**Word count best practice**: 1,000-3,000 words for SKILL.md body. Detailed content goes in `references/`.

### 9.3 Skill Description Best Practices

- **Third person**: "This skill should be used when..." not "Load this skill when..."
- **Specific trigger phrases**: Include exact phrases users would say
- **Length**: 50-500 characters for description
- **Example triggers**: List specific user queries

### 9.4 Skill vs Agent vs Command

| Aspect | Skill | Agent | Command |
|--------|-------|-------|---------|
| **Trigger** | Auto (task context match) | Auto (description match + Claude decision) | Manual (`/command`) |
| **Execution** | Adds to context | Runs as subprocess | Runs in current context |
| **Persistence** | Single message | Multi-step autonomous | Until command completes |
| **Visibility** | Invisible to user | Visible (colored output) | Visible (user-initiated) |
| **Use case** | Knowledge injection | Complex multi-step tasks | Quick workflows |

---

## 10. Environment Variables & Paths

### 10.1 Available Variables

| Variable | Set When | Purpose |
|----------|----------|---------|
| `$CLAUDE_PLUGIN_ROOT` | Session start | Plugin's absolute directory path |
| `$CLAUDE_PROJECT_DIR` | Session start | Project root |
| `$CLAUDE_ENV_FILE` | Session start | Write env vars for persistence (SessionStart only) |
| `$CLAUDE_CODE_REMOTE` | Session start | Set if running in remote context |
| `$CLAUDE_CODE_REMOTE_SESSION_ID` | Session start | Remote session identifier |
| `$ARGUMENTS` | Command invocation | All command arguments |
| `$1`..`$9` | Command invocation | Positional arguments |

### 10.2 $CLAUDE_PLUGIN_ROOT Usage

**Primary usage contexts**:
1. Hook commands: `"command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/script.sh"`
2. Command scripts: ``!`bash ${CLAUDE_PLUGIN_ROOT}/scripts/run.sh` ``
3. Command file references: `@${CLAUDE_PLUGIN_ROOT}/config/settings.json`
4. MCP server commands: `"command": "node", "args": ["${CLAUDE_PLUGIN_ROOT}/server.js"]`
5. Hook script paths: `source "${CLAUDE_PLUGIN_ROOT}/lib/common.sh"`

---

## 11. Orchestration Trade-offs & Decision Framework

### 11.1 When to Use Each Primitive

| Need | Primitive | Why |
|------|-----------|-----|
| User-initiated workflow | Command | `/command-name` invocation, argument passing |
| Complex multi-step analysis | Agent | Autonomous subprocess, focused model/tools |
| Event-driven validation | Hook | Fires automatically on lifecycle events |
| Knowledge/guidance injection | Skill | Auto-triggered context addition |
| User interaction needed | Command + AskUserQuestion | Questions, decisions, approvals |

### 11.2 Parallel vs Sequential Agents

**Parallel** (code-review pattern):
- **Pro**: Faster total time (all agents run simultaneously)
- **Con**: Agents can't build on each other's results
- **Con**: Higher peak resource usage (multiple model instances)
- **Use when**: Independent analysis dimensions, no cross-agent dependencies

**Sequential** (feature-dev pattern):
- **Pro**: Each agent informed by previous results
- **Pro**: User can intervene between phases
- **Con**: Slower total time
- **Con**: Orchestrator must manage state between phases
- **Use when**: Phases have dependencies, user approval gates needed

**Hybrid** (pr-review-toolkit pattern):
- Sequential by default (easier to understand)
- Parallel on explicit request (faster for experienced users)

### 11.3 Hook vs Agent for Validation

| Aspect | Hook | Agent |
|--------|------|-------|
| **Trigger** | Automatic on event | Requires Claude's decision |
| **Latency** | Sub-second (bash) to seconds (prompt) | Seconds to minutes |
| **Context** | Limited (stdin JSON, env vars) | Full context (project files, git, etc.) |
| **Capability** | Simple validation (regex, LLM prompt) | Complex analysis (multi-step reasoning) |
| **Output** | JSON (structured) | Any (natural language + tools) |
| **Use case** | Fast security checks | Deep code review |

### 11.4 State Management Patterns

| Pattern | Mechanism | Plugin |
|---------|-----------|--------|
| **State file** | `.ralph-state.md` with YAML frontmatter | ralph-wiggum |
| **Git baseline** | `.claude/security-guidance-diff-sha` | security-guidance |
| **Rule files** | `.claude/hookify.*.local.md` | hookify |
| **Env file** | `$CLAUDE_ENV_FILE` | System-provided |
| **Path allowlist** | `.claude/security-guidance-paths.txt` | security-guidance |
| **TTL cache** | `diffstate.py` with timestamps | security-guidance |

### 11.5 Plugin Complexity Spectrum

```
Simple ──────────────────────────────────────────────────> Complex
  │                                                           │
  v                                                           v

frontend-design    commit-commands    code-review         security-guidance
claude-opus-4-5    hookify            feature-dev         (2192-line hook,
   (skills only)   (user rules)       (7 phases, 3 agents)  12 scripts, 4 events)

explanatory        agent-sdk-dev      pr-review-toolkit   plugin-dev
  (1 hook)          (scaffold +        (6 agents,           (7 skills, 3 agents,
                    2 verifiers)        launch options)       1 command, self-referential)
```

---

## Appendix A: Complete Agent Inventory

| Plugin | Agent | Model | Color | Tools | Files | Purpose |
|--------|-------|-------|-------|-------|-------|---------|
| code-review | codebase-architect | opus | green | — | agents/codebase-architect.md | Architecture review |
| code-review | business-logic-analyzer | opus | yellow | — | agents/business-logic-analyzer.md | Business logic review |
| code-review | code-style-enforcer | opus | blue | — | agents/code-style-enforcer.md | Style checking |
| code-review | security-analyzer | opus | red | — | agents/security-analyzer.md | Security analysis |
| code-review | test-quality-advisor | opus | cyan | — | agents/test-quality-advisor.md | Test coverage review |
| feature-dev | code-explorer | sonnet | yellow | — | agents/code-explorer.md | Codebase exploration |
| feature-dev | code-architect | sonnet | green | — | agents/code-architect.md | Architecture design |
| feature-dev | code-reviewer | sonnet | red | — | agents/code-reviewer.md | Implementation review |
| pr-review-toolkit | code-reviewer | opus | green | — | agents/code-reviewer.md | General code review |
| pr-review-toolkit | silent-failure-hunter | inherit | yellow | — | agents/silent-failure-hunter.md | Error handling audit |
| pr-review-toolkit | comment-analyzer | inherit | green | — | agents/comment-analyzer.md | Comment accuracy |
| pr-review-toolkit | pr-test-analyzer | inherit | cyan | — | agents/pr-test-analyzer.md | Test coverage |
| pr-review-toolkit | type-design-analyzer | inherit | pink | — | agents/type-design-analyzer.md | Type design |
| pr-review-toolkit | code-simplifier | opus | — | — | agents/code-simplifier.md | Code simplification |
| agent-sdk-dev | agent-sdk-verifier-py | sonnet | — | — | agents/agent-sdk-verifier-py.md | Python SDK verification |
| agent-sdk-dev | agent-sdk-verifier-ts | sonnet | — | — | agents/agent-sdk-verifier-ts.md | TypeScript SDK verification |
| plugin-dev | agent-creator | sonnet | magenta | Write, Read | agents/agent-creator.md | AI agent generation |
| plugin-dev | plugin-validator | inherit | yellow | Read, Grep, Glob, Bash | agents/plugin-validator.md | Plugin validation |
| plugin-dev | skill-reviewer | inherit | cyan | Read, Grep, Glob | agents/skill-reviewer.md | Skill quality review |

## Appendix B: Complete Command Inventory

| Plugin | Command | Allowed Tools | Arguments | Hooks? |
|--------|---------|---------------|-----------|--------|
| code-review | code-review | — | $ARGUMENTS | No |
| feature-dev | feature-dev | — | $ARGUMENTS | No |
| ralph-wiggum | ralph-loop | — | — | Stop |
| ralph-wiggum | cancel-ralph | — | — | No |
| ralph-wiggum | help | — | — | No |
| commit-commands | commit | Bash(git:*) | $ARGUMENTS | No |
| commit-commands | commit-push-pr | git*, gh pr create | — | No |
| commit-commands | clean_gone | Bash(git:*) | — | No |
| agent-sdk-dev | new-sdk-app | — | [project-name] | No |
| pr-review-toolkit | review-pr | Bash, Glob, Grep, Read, Task | [review-aspects] | No |
| hookify | hookify | — | — | Yes |
| hookify | configure | — | — | No |
| hookify | help | — | — | No |
| hookify | list | — | — | No |
| plugin-dev | create-plugin | Read, Write, Grep, Glob, Bash, TodoWrite, AskUserQuestion, Skill, Task | — | No |
| Repo (project) | triage-issue | Bash(./scripts/gh.sh:*), Bash(./scripts/edit-issue-labels.sh:*) | — | No |
| Repo (project) | dedupe | Bash(./scripts/gh.sh:*), Bash(./scripts/comment-on-duplicates.sh:*) | — | No |
| Repo (project) | commit-push-pr | git*, gh pr create | — | No |

## Appendix C: Complete Hook Inventory

| Plugin | Event | Type | Matcher | Handler |
|--------|-------|------|---------|---------|
| ralph-wiggum | Stop | command | — | stop-hook.sh |
| security-guidance | SessionStart | command | — | security_reminder_hook.py |
| security-guidance | UserPromptSubmit | command | — | security_reminder_hook.py (subprocess) |
| security-guidance | PreToolUse | command | Write, Edit, Bash | security_reminder_hook.py (subprocess) |
| security-guidance | PostToolUse | command | Write, Edit | security_reminder_hook.py (subprocess) |
| security-guidance | Stop | command | — | security_reminder_hook.py (subprocess) |
| hookify | PreToolUse | command | Write, Edit | pretooluse.py |
| hookify | PostToolUse | command | * | posttooluse.py |
| hookify | Stop | command | * | stop.py |
| hookify | UserPromptSubmit | command | * | userpromptsubmit.py |
| explanatory-output-style | SessionStart | command | — | session-start.sh |
| learning-output-style | SessionStart | command | — | session-start.sh |

## Appendix D: Complete Skill Inventory

| Plugin | Skill Name | Subdirectory |
|---------|-----------|--------------|
| frontend-design | frontend-design | skills/frontend-design/ |
| claude-opus-4-5-migration | claude-opus-4-5-migration | skills/claude-opus-4-5-migration/ |
| plugin-dev | Plugin Structure | skills/plugin-structure/ |
| plugin-dev | Command Development | skills/command-development/ |
| plugin-dev | Agent Development | skills/agent-development/ |
| plugin-dev | Hook Development | skills/hook-development/ |
| plugin-dev | Skill Development | skills/skill-development/ |
| plugin-dev | MCP Integration | skills/mcp-integration/ |
| plugin-dev | Plugin Settings | skills/plugin-settings/ |

---

*End of exhaustive audit. This document catalogs every orchestration mechanism, CLI UI rendering signal, hook configuration, agent definition, command definition, and skill definition across all 14 plugins in the repository.*
