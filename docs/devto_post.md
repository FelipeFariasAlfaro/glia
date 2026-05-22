---
title: GLIA — A holographic memory for AI agents that isn't a graph and isn't RAG
published: true
tags: ai, python, opensource, machinelearning
---

Every AI coding agent I've used (Cline, Claude, Cursor) has the same problem: it forgets everything between sessions. You fix a complex race condition on Monday, and on Tuesday the agent suggests the same broken pattern again.

RAG (Retrieval-Augmented Generation) is the standard fix. You chunk files, embed them, and search by similarity. It works for direct questions. But it fails at **associative reasoning**. It can't connect "rate limiting fails open" with "shared Redis connection pool" if those concepts never appear in the same text chunk. The relationship exists in the architecture, but RAG is blind to it.

Graphs are the other option. Nodes and edges. Better at relationships, but rigid. If you delete 30% of your edges, you lose entire paths. And let's be honest: maintaining a massive knowledge graph for a changing codebase is a schema nightmare.

I wanted something different. Something that behaves more like a brain than a database. So I built GLIA.

## What GLIA actually does

GLIA stores knowledge as 1024-dimensional vectors. Not text chunks. Not nodes. Patterns.

In GLIA, every piece of knowledge (a function, a decision, a bug fix) is a **glyph** — a distributed pattern across 1024 dimensions. No single dimension carries the meaning; the meaning is the "interference pattern" of the whole vector.

### Holographic Binding (The "Secret Sauce")

Relationships aren't stored as edges in a table. They are encoded **holographically** using Circular Convolution.

Think of it as "folding" two patterns into each other. When you `bind(A, B)`, you create a new vector that is mathematically related to both but looks like noise to anything else.
*   **Superposition**: You can add thousands of these bindings into the same 1024-d vector space. They don't overwrite each other; they coexist as interference patterns.
*   **Unbinding**: Later, if you have A and the "memory substrate", you can mathematically `unbind` them to recover B.

This means GLIA has **Zero Edges**. If you open the database, there is no `relationships` table. The architecture is the memory.

## Why this beats a Graph

Three things a graph can't do that GLIA does natively:

1.  **Graceful Degradation**: If you corrupt 30% of a glyph's dimensions, its similarity only drops to ~0.85. It's still recognizable. In a graph, deleting 30% of edges destroys entire paths permanently.
2.  **Analogical Reasoning**: Because it's a vector space, `king - man + woman` produces a vector close to `queen`. In a codebase, this translates to structural analogies across different modules without explicit links.
3.  **Hebbian Plasticity**: GLIA isn't static. When a pattern "resonates" (is retrieved), it gets stronger. Patterns that aren't used decay over time and eventually fade to zero. The memory auto-cleans itself.

## The Benchmarks (Rigorous & Reproducible)

I didn't just "feel" it was better. I benchmarked GLIA v2 against a Graph (Spreading Activation) and BM25 (the algorithm behind Elasticsearch) across 3 real-world projects (Python backend, ML pipeline, React frontend).

I used 21 **multi-hop questions** per project — questions that require connecting 3 or 4 different files or concepts to answer correctly.

| Metric | GLIA | Graph (V1) | BM25 |
|---|---|---|---|
| **MRR (Avg)** | **0.851** | 0.344 | 0.870 |
| **Token Savings** | **97.8%** | — | — |
| **Latency** | **94ms** | 2ms | <1ms |
| **Edges in DB** | **0** | 696 | 0 |

**The result:** GLIA outperforms the graph-based approach by **2.5x** in retrieval accuracy (MRR). It stays within **~2%** of BM25 — a 30-year-old algorithm optimized specifically for keyword matching — while providing associative capabilities that BM25 could never dream of.

Against RAG with Gemini 3.1 embeddings: RAG wins on precision by ~10%, but GLIA wins on **cost ($0)**, **offline capability**, and **plasticity** (learning as it goes).

## How to use it

GLIA is a local-first tool. No API keys required for the core engine.

```bash
git clone https://github.com/FelipeFariasAlfaro/glia.git
cd glia && pip install -e .

cd your-project
python -m glia init
python -m glia scan    # AST parsing, $0, instant
python -m glia recall "session expiration bug"
```

It exposes an **MCP (Model Context Protocol) server**, so it plugs directly into Cline, Cursor, Claude Desktop, or Gemini CLI. Add this to your MCP config:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "/path/to/your/project"
      }
    }
  }
}
```

Once connected, the agent gets `glia_recall`, `glia_learn`, `glia_scan`, `glia_forget`, and `glia_changes`. Tell it in your custom instructions to query GLIA before answering and to teach it after completing tasks — the memory grows on its own from there.

## What's the catch?

Single-hop precision. If you ask "what does exactly this line do?", RAG with high-end embeddings will be more surgical. GLIA is a **Structural Memory**. It's designed to help an agent understand the *relationships* and *history* of a project, not to replace a grep tool.

## The Stack

- **Binding**: Circular Convolution via FFT (Fast Fourier Transform).
- **Encoding**: Deterministic hash-projection + Synonyms + Stemming.
- **Storage**: SQLite BLOBs (No edge tables, no complex joins).
- **Plasticity**: Hebbian reinforcement + Temporal decay.

Everything is open source (MIT). If you're tired of your AI agents having the memory of a goldfish, give it a try.

GitHub: [github.com/FelipeFariasAlfaro/glia](https://github.com/FelipeFariasAlfaro/glia)
