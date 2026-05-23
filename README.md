# 🧠 GLIA - Holographic Distributed Memory for AI Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Multi-Provider](https://img.shields.io/badge/AI-Gemini%20|%20OpenAI%20|%20Claude-blueviolet.svg)](#configuration)

**GLIA** is a persistent memory system for AI agents based on **Holographic Distributed Memory (HDM)**. It gives agents long-term epistemic context across sessions. Not a graph. Not RAG. A genuinely distinct architecture where knowledge is stored as distributed patterns in a high-dimensional vector space, and retrieval works by **resonance** — parallel pattern projection, not text search or node traversal.

**Works with any project** (Python, JavaScript, TypeScript, Java, Go, Rust, C#, C/C++, Ruby, PHP, Kotlin, Swift, and more). GLIA is a tool written in Python that analyzes and memorizes any codebase.

---

## Table of Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Quick Start](#quick-start)
- [CLI Commands](#cli-commands)
- [MCP Integration (IDE / CLI)](#mcp-integration-ide--cli)
- [Instructing the Agent to Use GLIA](#instructing-the-agent-to-use-glia)
- [Available MCP Tools](#available-mcp-tools)
- [Supported Languages](#supported-languages)
- [Recommended Workflow](#recommended-workflow)
- [Folder Structure](#folder-structure)
- [What problem does it solve?](#what-problem-does-it-solve)
- [How does GLIA work internally?](#how-does-glia-work-internally)
- [Demo](#demo-no-api-key-needed)
- [Requirements](#requirements)
- [Project Structure](#project-structure)
- [Troubleshooting](#troubleshooting)
- [Benchmarks](#benchmarks)
- [Author](#author)

---

## Installation

GLIA is installed **once** on your machine as a global tool.

```bash
# Basic install (Gemini support included)
pip install -e .

# With OpenAI support
pip install -e ".[openai]"

# With Anthropic (Claude) support
pip install -e ".[anthropic]"

# All providers
pip install -e ".[all]"
```

---

## Configuration

Create a `glia.env` file in your project root:

```ini
# Provider: gemini, openai, or anthropic
GLIA_PROVIDER=gemini

# API key for your chosen provider
GEMINI_API_KEY=your_key_here
# OPENAI_API_KEY=your_key_here
# ANTHROPIC_API_KEY=your_key_here

# Model (optional — uses provider default if not set)
# GLIA_MODEL=gemini-2.5-flash
```

| Provider | Default model | Get your key |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | https://aistudio.google.com/apikey |
| `openai` | `gpt-4o-mini` | https://platform.openai.com/api-keys |
| `anthropic` | `claude-sonnet-4-20250514` | https://console.anthropic.com/ |

> **Note:** The API key is only needed for `glia learn`. All other commands (`scan`, `recall`, `stats`, `forget`, `changes`) work **offline without any API key or cost**.

> **Note:** If no `glia.env` is found, GLIA falls back to `.env` for backward compatibility. Using `glia.env` avoids conflicts with your project's own `.env` file.

---

## Quick Start

```bash
# 1. Initialize GLIA in your project
python -m glia init

# 2. Scan your codebase (free, uses AST parsing)
python -m glia scan

# 3. Query the memory
python -m glia recall "authentication flow"

# 4. Teach something new (uses AI)
python -m glia learn "The session bug was caused by token expiring in ms instead of seconds"

# 5. Install git hook for automatic learning
python -m glia hook
```

---

## CLI Commands

| Command | What it does | Cost |
|---|---|---|
| `python -m glia init` | Initialize GLIA in the current directory | Free |
| `python -m glia scan` | Scan project with AST (all languages) | Free |
| `python -m glia recall "query"` | Retrieve by resonance | Free |
| `python -m glia learn "text"` | Teach new knowledge (AI distillation) | Tokens |
| `python -m glia stats` | Memory statistics | Free |
| `python -m glia forget` | Apply temporal decay | Free |
| `python -m glia changes` | Detect manually modified files | Free |
| `python -m glia hook` | Install post-commit git hook | Free |
| `python -m glia serve` | Start MCP server | Free |
| `python -m glia context "query"` | Get raw context to inject into LLM | Free |

---

## MCP Integration (IDE / CLI)

GLIA exposes itself as an MCP server compatible with any MCP client. The provider is configured via `glia.env` in your project, or via environment variables in the MCP config.

### Kiro

In `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "."
      }
    }
  }
}
```

### Cline (VS Code)

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "C:\\path\\to\\your\\project"
      }
    }
  }
}
```

### Cursor

Create `.cursor/mcp.json` in the project root:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "."
      }
    }
  }
}
```

### Claude Desktop

Edit `%APPDATA%\Claude\claude_desktop_config.json` (Windows) or `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "/path/to/project"
      }
    }
  }
}
```

### Antigravity (Google)

Click "Manage MCP Servers" → "View raw config" to open `mcp_config.json`, then add:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "."
      }
    }
  }
}
```

### Gemini CLI

Create `.gemini/settings.json` in your project:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "."
      }
    }
  }
}
```

### Overriding provider via MCP config

If you want to use a different provider than what's in `glia.env`, pass it as env vars:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": ".",
        "GLIA_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

---

## Instructing the Agent to Use GLIA

Connecting the MCP server is not enough — you need to tell the agent **when and how** to use GLIA. Without explicit instructions, most agents won't consult GLIA on their own.

### Recommended system rule (add to your IDE's agent rules)

```
## GLIA Memory

You have access to GLIA, a persistent project memory via MCP.

**ALWAYS do this:**
- At the START of every task, call `glia_recall` with the topic you're about to work on. This gives you context about past decisions, bugs, and architecture.
- After fixing a bug or making an important decision, call `glia_learn` to record what you did and why.
- When you modify a file significantly, call `glia_learn_file` so the memory stays current.

**Examples:**
- Before fixing a bug: `glia_recall("login authentication error")`
- After fixing it: `glia_learn("Login failed because JWT token expiry was in milliseconds instead of seconds. Fixed in auth_service.py by converting to seconds.")`
- After a design decision: `glia_learn("Chose PostgreSQL over MongoDB for the orders service because we need ACID transactions for payments.")`
```

### Where to put this rule in each IDE

| IDE | File / Location |
|---|---|
| **Kiro** | `.kiro/steering/glia.md` |
| **Cursor** | `.cursor/rules/glia.mdc` or `.cursorrules` |
| **Cline** | `.clinerules` |
| **Claude Desktop** | Include in your system prompt |
| **Antigravity** | `AGENTS.md` or `GEMINI.md` in project root |
| **Gemini CLI** | `GEMINI.md` in project root |
| **Windsurf** | `.windsurfrules` |

### Example: Kiro steering file

Create `.kiro/steering/glia.md`:

```markdown
---
inclusion: auto
---

## GLIA Memory System

This project uses GLIA for persistent memory across sessions.

Before starting any task, call `glia_recall` with the relevant topic to get context about past decisions and bugs.

After completing a task, call `glia_learn` to record:
- What was done
- Why it was done that way
- Any gotchas or lessons learned

This ensures future sessions have full context without re-discovering everything.
```

### Example: Cursor rules

Create `.cursor/rules/glia.mdc`:

```
---
description: GLIA memory integration
globs: **/*
alwaysApply: true
---

You have access to GLIA memory via MCP tools.

ALWAYS call glia_recall at the start of a task to check for existing context.
ALWAYS call glia_learn after fixing bugs or making architectural decisions.
```

### Example: Antigravity (AGENTS.md)

Create `AGENTS.md` in your project root:

```markdown
# Agent Instructions

## Memory
Use GLIA MCP tools for persistent memory:
- `glia_recall(query)` — Check memory before starting work
- `glia_learn(content, source)` — Record decisions and bug fixes
- `glia_scan()` — Re-scan after major refactors
```

### Pro tip: The git hook handles commits automatically

If you ran `python -m glia hook`, commit messages are already captured automatically. The rules above are for teaching the agent to use GLIA **during** the session — for the reasoning and decisions that don't end up in commit messages.

---

## Available MCP Tools

| Tool | Description | Cost |
|---|---|---|
| `glia_recall(query, top_k)` | Retrieve context by resonance | Free |
| `glia_learn(content, source)` | Teach new knowledge | Tokens |
| `glia_scan(path)` | Scan project with AST | Free |
| `glia_learn_file(file_path)` | Re-scan a specific file | Free |
| `glia_stats()` | Memory statistics | Free |
| `glia_forget(decay_rate)` | Apply temporal decay | Free |
| `glia_changes()` | Detect modified files | Free |

---

## Supported Languages

The AST scanner extracts functions, classes, methods, imports, and dependencies from:

Python • JavaScript • TypeScript • Java • Go • Rust • C# • C/C++ • Ruby • PHP • Kotlin • Swift • Gherkin (.feature) • Markdown • Config files (JSON, YAML, TOML)

---

## Recommended Workflow

```bash
# Initial setup (once)
python -m glia init
python -m glia scan
python -m glia hook
# Configure MCP in your IDE

# Then work normally — GLIA learns automatically:
# • The agent calls glia_learn after fixing bugs or making decisions
# • The git hook captures commit messages
# • Modified files are re-scanned when reconnecting the MCP server
```

---

## Folder Structure

```
~/tools/glia/                  ← GLIA source code (cloned once)
    src/glia/
    pyproject.toml

~/projects/my-api/             ← YOUR project
    .glia/                     ← Created by 'glia init' (add to .gitignore)
        memory.db              ← Holographic memory of this project
    glia.env                   ← Your provider config (add to .gitignore)
    src/
    ...

~/projects/other-project/      ← Another project (separate memory)
    .glia/
        memory.db
    glia.env
    ...
```

Each project has its own memory. GLIA is installed once and used across many projects.

---

## What problem does it solve?

AI agents (Cline, Claude, Cursor, Copilot, Kiro, etc.) lose context between sessions. Every new chat starts from scratch — no memory of past bugs, architectural decisions, or how parts of the project relate to each other.

GLIA solves this by maintaining a **persistent relational memory** that grows with every interaction and strengthens with use.

---

## How does GLIA work internally?

### The analogy: The brain is not a hard drive

When you remember the smell of a cake, your brain doesn't search for a folder named "Memories/Cakes/smell.txt". A small stimulus (the smell) **activates a pattern** of neurons that, by interference, reconstructs the complete memory: the kitchen, your grandmother, the conversation you had.

Knowledge is not in a point. It is **distributed** in an activation pattern.

GLIA replicates this computational principle.

---

### Step 1: Encoding — Converting knowledge into patterns

When GLIA scans your project or learns something new, it converts each unit of knowledge into a **glyph**: a 1024-dimensional vector.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  "Generate a JWT token for the user"                            │
│                                                                  │
│         │ encode_text()                                          │
│         ▼                                                        │
│                                                                  │
│  [0.023, -0.041, 0.087, ..., -0.012, 0.055, 0.031]             │
│   ←──────────── 1024 dimensions ───────────────────→            │
│                                                                  │
│  Each dimension does NOT have an individual meaning.            │
│  The meaning is DISTRIBUTED across the complete pattern.        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

The encoding is **deterministic** — the same text always produces the same vector. It uses no AI, spends no tokens. It is pure hashing + random projection with a fixed seed.

---

### Step 2: Storage — Superposition in the Substrate

Glyphs are not saved in rows of a table. They are **superposed** (summed) in a region of the substrate:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUBSTRATE (Region "default")                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Glyph 1: "JWT authentication"                                  │
│  [0.02, -0.04, 0.08, ..., -0.01, 0.05, 0.03]                   │
│                          +                                       │
│  Glyph 2: "Token refresh endpoint"                              │
│  [0.05, 0.01, -0.03, ..., 0.07, -0.02, 0.04]                   │
│                          +                                       │
│  Glyph 3: "Session timeout bug"                                 │
│  [-0.01, 0.06, 0.02, ..., 0.03, 0.08, -0.05]                   │
│                          =                                       │
│  ─────────────────────────────────────────────                   │
│  Region vector:                                                  │
│  [0.06, 0.03, 0.07, ..., 0.09, 0.11, 0.02]                     │
│                                                                  │
│  All 3 glyphs COEXIST in the same vector.                       │
│  Region size is CONSTANT (1024 floats) regardless               │
│  of how many glyphs are stored.                                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 3: Relationships — Holographic Encoding (no edges)

In a graph, "A is connected to B" is stored as an explicit edge. In GLIA, relationships are encoded **within the same vector space** using circular convolution:

```
bind(A, B) = circular_convolution(A, B)

Properties:
• bind(A,B) is DIFFERENT from A and B
• unbind(bind(A,B), A) ≈ B
• Creates no explicit "edge"
• The relationship LIVES in the vector itself
```

**There is no edge table. Relationships are interference patterns within the vectors.**

---

### Step 4: Retrieval — Resonance (not search)

When you ask something, GLIA encodes your question as a vector and **projects** it against all glyphs simultaneously:

```
Query: "why do tokens expire?"
         │
         ▼ encode_text()
    [1024-d stimulus vector]
         │
         ▼ cosine similarity against ALL glyphs (parallel)
         │
    cosine(stimulus, glyph_1) = 0.69  ← RESONATES!
    cosine(stimulus, glyph_2) = 0.13
    cosine(stimulus, glyph_3) = 0.12
    ...
    cosine(stimulus, glyph_N) = 0.01
```

**Key difference with a graph:** In a graph, if there is no path between A and B, you never connect them. In GLIA, if A and B share a pattern (even if never explicitly "connected"), they resonate together.

---

### Step 5: Plasticity — The memory is alive

- **Reinforcement (Hebbian):** Every time a glyph resonates, its magnitude increases. Frequent patterns "sound louder" in future queries.
- **Decay:** Glyphs that are NOT used lose magnitude over time. The memory auto-cleans.
- **Co-activation:** If two glyphs resonate together, a binding is created between them. "What resonates together, binds stronger."

---

### Why is this NOT a graph?

| Property | Graph | GLIA |
|---|---|---|
| Structure | Nodes + Explicit edges | Superposed vectors in continuous space |
| Relationships | Edge table | Interference patterns (bindings) |
| Retrieval | Sequential traversal (BFS/DFS) | Parallel projection (cosine similarity) |
| If you delete 30% | You lose entire paths | Keeps working (holographic property) |
| Analogies | Impossible | Native (vector arithmetic) |
| Storage | Grows with each relationship O(N²) | Constant per region O(D) |
| Edge table in DB | Yes | **NO** |

---

## Demo (no API key needed)

```bash
python examples/demo_v2.py
```

Demonstrates: resonance, one-shot learning, graceful degradation, analogical reasoning, conjunctive queries, and storage efficiency.

---

## Requirements

- **Python 3.11+**
- **numpy**
- **Git** (for the automatic hook)
- **API Key** (optional — only for `glia learn`, any supported provider)

---

## Project Structure

```
glia/
├── src/glia/
│   ├── config.py            # Multi-provider configuration (glia.env)
│   ├── binding.py           # Circular convolution (bind/unbind)
│   ├── encoder.py           # Deterministic encoding text→vector
│   ├── synonyms.py          # Static programming synonym dictionary
│   ├── substrate.py         # Memory regions with superposition
│   ├── resonance.py         # Retrieval by parallel projection + unbinding
│   ├── plasticity.py        # Hebbian reinforcement + temporal decay
│   ├── cognitive_map.py     # Structured output for LLMs
│   ├── brain.py             # Main orchestrator
│   ├── storage.py           # SQLite persistence (BLOB vectors, no edges)
│   ├── embeddings.py        # Optional embeddings (enhanced mode)
│   ├── distiller.py         # Multi-provider LLM distillation
│   ├── ast_scanner_v2.py    # Multi-language scanner for substrate
│   ├── scanner.py           # Project scanner (incremental)
│   ├── mcp_server.py        # MCP Server
│   └── cli.py               # Command line interface
├── docs/
│   ├── ARCHITECTURE.md      # Detailed architecture with diagrams
│   └── benchmarks/          # Benchmark results
├── benchmarks/              # Reproducible benchmark scripts
├── examples/
│   └── demo_v2.py           # Holographic capabilities demo
└── benchmark_project*/      # Test projects for benchmarks
```

---

## Troubleshooting

**"glia" is not recognized** → Use `python -m glia` or add Python Scripts to your PATH.

**MCP server does not connect** → Verify that `python -m glia.mcp_server` runs without errors. Verify that `GLIA_WORKSPACE` points to a directory with an initialized `.glia/`.

**"No resonating patterns"** → Run `python -m glia scan` first, then `python -m glia stats` to verify glyphs exist.

**"resource busy or locked"** → Disconnect the MCP server in your IDE before deleting `.glia/`.

**Provider errors** → Verify your `glia.env` has the correct `GLIA_PROVIDER` and corresponding API key. Run `python -c "from glia.config import get_config; c = get_config(); print(c.provider, c.model)"` to check.

---

## Benchmarks

GLIA was evaluated against Graph (Spreading Activation) and BM25 (Elasticsearch) on three projects from different domains, using standard Information Retrieval metrics (MRR, nDCG, Precision@K) with real token counting (tiktoken).

### Results (local mode, $0, no embeddings)

| Project | GLIA | Graph (SA) | BM25 | GLIA vs Graph |
|----------|------|-----------|------|---------------|
| E-Commerce (Python, 31 files) | MRR **0.771** | 0.409 | 0.785 | **+88%** |
| ML Pipeline (Python, 27 files) | MRR **0.904** | 0.203 | 0.941 | **+344%** |
| Frontend (TypeScript, 32 files) | MRR **0.877** | 0.421 | 0.885 | **+108%** |

### Efficiency

| Metric | Average Value |
|---------|---------------|
| Token savings | **97.8%** (47x compression) |
| Latency | **94ms** average |
| Scan | **3.4s** average, $0 |
| Edges | **0** (holographic) |

### GLIA vs RAG (Gemini Embeddings)

| System | MRR | Cost |
|---------|-----|-------|
| RAG (Gemini embedding-001) | 0.873 | ~$0.001/query |
| **GLIA (local)** | 0.783 | **$0** |
| GLIA + embeddings (optional) | 0.835 | ~$0.001/query |

**Conclusion:** GLIA outperforms traditional graphs by 2.5x. It matches BM25 (-2.2%). It loses to RAG in pure precision (-10%) but at $0 cost and with capabilities RAG lacks (plasticity, unbinding, offline).

### Methodological Integrity

1. **Zero-Shot Evaluation:** GLIA was not pre-trained on the test projects. All evaluations are zero-shot using the standard AST scanner.
2. **Industry Metrics:** MRR (Mean Reciprocal Rank) and nDCG ensure optimal context ordering for the LLM.
3. **Real Token Calculation:** Measured using `tiktoken` (cl100k_base), not character approximations.
4. **Reproducibility:** All evaluation scripts and test repositories are included for public verification.

📊 [View full benchmarks](docs/benchmarks/BENCHMARK_SUMMARY.md)

---

## Author

**Felipe Farías Alfaro**
- GitHub: [FelipeFariasAlfaro](https://github.com/FelipeFariasAlfaro)
- Web: [felipefariasalfaro.github.io](https://felipefariasalfaro.github.io)

---

## License

[MIT](LICENSE)
