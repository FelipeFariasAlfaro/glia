# GLIA: Holographic Distributed Memory for AI Agents

[Read in Spanish](README_ES.md) | [Changelog](CHANGELOG.md)

Current release target: `0.4.0` (unreleased).

GLIA is a persistent memory system for AI agents based on Holographic Distributed Memory (HDM). It stores knowledge as distributed high-dimensional patterns, retrieves it by resonance, and encodes relationships as reversible holographic contributions. It is not a graph database, a BM25 index, or a conventional RAG pipeline.

GLIA is designed for agents that need durable project context: architectural decisions, code structure, source provenance, operational knowledge, and bounded memory adaptation across sessions.

## What GLIA does

- Encodes text and code deterministically into 1024-dimensional vectors without requiring an API key.
- Stores glyphs in superposed memory regions and scores them through parallel vector resonance.
- Encodes associations through circular binding and explicit, reversible relationship contributions rather than graph edges.
- Scans supported source files incrementally, tracks source hashes, and removes contributions for deleted or ignored files.
- Provides stable, read-only recall by default; optional `adapt` persists bounded Hebbian reinforcement and optional `explore` reserves results for holographic associations.
- Persists project memory in SQLite with WAL, full synchronous durability, optimistic revisions, validation, backups, and recovery from transient lock contention.

## Core model

```text
source text or code
        |
        v
 deterministic encoding
        |
        v
 glyph vector + metadata
        |
        v
 superposition in a region
        |
        +-- reversible bound relationship contributions
        |
        v
 resonance against a query vector
        |
        v
 ranked glyphs, sources, and cognitive context
```

A region is the sum of each glyph vector weighted by its magnitude plus its relationship contributions. This invariant is validated before every persistent commit. Glyphs, relationships, and regions managed by the substrate expose immutable vector data; supported mutation APIs preserve regional superposition atomically.

GLIA still persists glyph metadata to support provenance, ranking, source removal, and exact recovery. Region vectors have fixed dimension, while the total durable footprint includes glyph and relationship metadata. It does not claim constant total database size as memory grows.

## Reliability and scalability

The current implementation focuses on predictable behavior under failures, concurrent writers, and growing memory.

- SQLite commits use optimistic revisions. A stale writer is rejected rather than overwriting newer knowledge.
- `GliaBrain` reloads and reapplies deterministic mutations after revision conflicts.
- `BEGIN IMMEDIATE` retries transient `SQLITE_BUSY` and `SQLITE_LOCKED` errors with bounded backoff.
- Dirty tracking writes changed regions, glyphs, and relationships only, while membership reconciliation still detects externally cleared dictionaries and removes stale rows exactly.
- Dirty state is cleared only after a successful commit. A conflict or rollback leaves pending work intact.
- SQLite load and save validate vector dimension, finite values, region membership, glyph counts, and exact holographic superposition.
- Scanner updates and scan-state changes are committed atomically. Per-file scanner failures restore prior source contributions and tracking state.
- Resonance uses an immutable cached vector matrix. Repeated queries avoid rebuilding the matrix; supported mutations invalidate the cache.
- Backups use SQLite's backup API and are published atomically with unique names.

## Installation

Requirements:

- Python 3.11 or newer
- NumPy
- Git for optional post-commit integration
- A Gemini API key only for LLM-assisted `learn`

```bash
cd ~/tools
git clone https://github.com/FelipeFariasAlfaro/glia.git
cd glia
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/glia --help
```

## Quick start

Run these commands inside the project you want GLIA to remember.

```bash
# Initialize the local durable memory
python -m glia init

# Scan supported source and documentation files
python -m glia scan

# Stable read-only recall
python -m glia recall "authentication session token"

# Explicit bounded adaptation
python -m glia recall "authentication session token" --adapt

# Explicit holographic association exploration
python -m glia recall "authentication session token" --explore

# Inspect durable storage
python -m glia doctor --deep
```

`recall` is read-only by default. Use `--adapt` only when reinforcement should be persisted. Use `--explore` only when association discovery is desired; stable ranking does not mix unbinding evidence into its primary results.

To teach distilled knowledge with an LLM, configure the optional environment variables in the target project:

```text
GEMINI_API_KEY=your_key_here
GLIA_MODEL=gemini-3.1-flash-lite-preview
```

```bash
python -m glia learn "The session token expiry is expressed in seconds, not milliseconds."
```

## CLI and MCP

Useful CLI commands include:

| Command | Purpose |
|---|---|
| `python -m glia init` | Create project-local `.glia` storage |
| `python -m glia scan` | Incrementally scan the project |
| `python -m glia recall "query"` | Retrieve stable resonance results |
| `python -m glia recall "query" --adapt` | Persist bounded reinforcement |
| `python -m glia recall "query" --explore` | Include holographic association exploration |
| `python -m glia learn "text"` | Distill and store new knowledge |
| `python -m glia forget` | Apply temporal decay |
| `python -m glia stats` | Report memory statistics |
| `python -m glia doctor --deep` | Run SQLite integrity checks |
| `python -m glia backup` | Create a durable SQLite backup |

GLIA also exposes an MCP server. Configure your client to run `python -m glia.mcp_server` and set `GLIA_WORKSPACE` to the target project. Restart or reconnect the MCP server after upgrading GLIA so its process loads the updated implementation.

## Supported extraction

The scanner extracts useful structure from Python, JavaScript, TypeScript, Java, Go, Rust, C#, C/C++, Ruby, PHP, Kotlin, Swift, Gherkin, Markdown, text, and common configuration files. It uses source-qualified identities so files with the same basename do not collide.

## Benchmarks

The reproducible phase-2 benchmark compares GLIA with direct HDM retrieval, Okapi BM25, and SQLite FTS5 on versioned relevance judgments. It also measures persistence and query scaling locally.

Run it with:

```bash
.venv/bin/python benchmarks/benchmark_phase2.py --sizes 100 1000 5000 --query-count 10
```

Final phase-3 local results at 5,000 glyphs:

| Metric | Result |
|---|---:|
| Initial full save | 180.08 ms |
| Validated incremental save of one glyph | 26.26 ms |
| Rows changed by that incremental save | 1 region and 1 glyph |
| Cold query, including matrix construction | 32.13 ms |
| Warm cached query | 6.10 ms |
| Stable public recall | 7.10 ms |
| Adaptive recall | 65.13 ms |
| SQLite database, WAL, and SHM footprint | 86,047 KiB |

Retrieval MRR in the same benchmark was 0.837 for the backend fixture, 0.802 for the ML fixture, and 0.776 for the TypeScript/React fixture. BM25 and FTS5 remain stronger and faster lexical baselines for exact-term retrieval; GLIA's differentiated value is persistent HDM resonance, reversible binding, bounded plasticity, source-aware scanning, and association exploration.

Benchmark timings depend on hardware and process state. Quality is measured against versioned query relevance judgments rather than inferred during the run.

## Operational notes

- Add `.glia/` to the target project's `.gitignore` unless you intentionally share its memory database.
- Do not edit SQLite files while an MCP server or CLI operation is writing. GLIA retries transient locks, but long external write transactions should be avoided.
- Use `glia doctor --deep` when diagnosing persistence concerns.
- Use `glia backup` before moving, manually inspecting, or recovering project memory.
- If an MCP server still runs old code after an upgrade, reconnect it from the MCP client.

## License

GLIA is distributed under the [MIT License](LICENSE).
