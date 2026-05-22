# 🧠 GLIA: The Tech Lead Agent with Holographic Memory

This project is a submission for the **Google Cloud Rapid Agent Hackathon**. 

**GLIA** is more than just an agent; it is an **Epistemic Memory** architecture for AI agents that solves the "context amnesia" problem in software development. While most agents rely on RAG (slow and expensive) or Knowledge Graphs (rigid), GLIA uses **Holographic Distributed Memory** to give agents a historical and architectural sense of the project.

---

## 🚀 The Vision: An Agent that "Remembers"

AI agents often suggest code patterns that the team decided to abandon months ago. GLIA acts as an **Autonomous Digital Tech Lead** that:
1. **Remembers** past incidents, design decisions, and team conventions.
2. **Reasons** about new code by comparing it with that collective memory (via **Gemini 3.1 Flash Lite Preview**).
3. **Acts Proactively** by automatically reviewing Merge Requests in GitLab before they are merged.

---

## ☁️ Google Cloud Enterprise Architecture

To meet enterprise requirements and the hackathon's rules, this agent is hosted natively on **Google Cloud**:

1. **Reasoning Engine:** Powered by **Gemini 3.1 Flash Lite** orchestrated within a **FastAPI** autonomous agent.
2. **The Memory Tool (Cloud Run):** The GLIA Holographic Memory engine is exposed as a microservice deployed on **Google Cloud Run**.
3. **GitLab Webhook Integration:** The system acts as a pro-active auditor. GitLab sends real-time events (webhooks) to GLIA, triggering an autonomous review loop.
4. **The Workflow:** 
   *   **Push/MR** occurs in GitLab.
   *   **Webhook** triggers GLIA on Cloud Run.
   *   **GLIA** fetches the code diff and "resonates" with its holographic memory.
   *   **Gemini** generates a context-aware review.
   *   **GitLab API** receives the final review comment automatically.

---

## 📦 Prerequisites for Deployment

- **Google Cloud SDK (`gcloud` CLI)**
- A Google Cloud Project with Billing Enabled.
- **Gemini API Key** (obtained at [Google AI Studio](https://aistudio.google.com/apikey))
- **GitLab Personal Access Token** (with `api` scope to post comments).

---

## 🛠️ Step-by-Step Deployment

### 1. Deploy the Autonomous Agent to Cloud Run
From the root of the repository, deploy the project to Google Cloud:

```bash
gcloud run deploy glia-memory-api \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=your_gemini_key,GITLAB_PERSONAL_ACCESS_TOKEN=your_gitlab_token,GLIA_MODEL=gemini-3.1-flash-lite-preview"
```
*Take note of the provided **Service URL** (e.g., `https://glia-memory-api-xxx.a.run.app`).*

### 2. Configure the GitLab Webhook
1. Go to your repository on **GitLab.com**.
2. Navigate to **Settings** -> **Webhooks**.
3. Click **Add new webhook**.
4. **URL:** Enter your Cloud Run URL followed by `/webhook/gitlab` (e.g., `https://glia-api-xxx.a.run.app/webhook/gitlab`).
5. **Trigger:** Check the **"Merge request events"** box.
6. Click **Save changes**.

---

## 📖 The "Golden Demo": How to Test It

### Step 1: Inject Historical Knowledge (The "Teach" Phase)
Use PowerShell or curl to "teach" a critical rule directly to your production API:

```powershell
$body = @{
    content = "Incident #402: We had a critical CPU spike because the payment_service logger was using JSON.stringify(payload) on very large objects. RULE: Never use JSON.stringify in payment logs. Use CustomLogger.serialize() instead."
    source = "hackathon-manual-injection"
} | ConvertTo-Json

Invoke-RestMethod -Uri "https://YOUR_CLOUD_RUN_URL/learn" -Method Post -Body $body -ContentType "application/json"
```

### Step 2: Trigger the Autonomous Review
1. Create a new branch in your repository.
2. Add a code snippet that violates the rule (e.g., adding `JSON.stringify` to a log in a payment-related file).
3. Open a **Merge Request** in GitLab.
4. **Watch the Magic:** In seconds, a comment from **"🤖 GLIA Tech Lead Review"** will appear in the MR, identifying the specific historical incident and rejecting the change.

---

## 🧪 Benchmarks and Validation
GLIA is not just an idea; it has been rigorously tested:
- **2.5x better retrieval** than traditional knowledge graphs.
- **97.8% token savings** by sending only the resonant context to the LLM.
- **Latency < 100ms** for holographic lookups.

---

## 👨‍💻 Author
**Felipe Farías Alfaro**
Project developed for the Google Cloud Rapid Agent Hackathon (May 2026).



# 🧠 GLIA - Holographic Distributed Memory for AI Agents

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Version](https://img.shields.io/badge/version-0.1.0--alpha-orange.svg)]()

*[Leer en Español](README.md)*

**GLIA** is a persistent memory system for AI agents based on **Holographic Distributed Memory (HDM)**. It is not a graph. It is not RAG. It is a genuinely distinct architecture where knowledge is stored as distributed patterns in a high-dimensional vector space, and retrieval works by **resonance** — parallel projection of patterns, not text search or node traversal.

---

## What problem does it solve?

AI agents (Cline, Claude, Cursor, Copilot, etc.) lose context between sessions. Every new chat starts from scratch — no memory of past bugs, architectural decisions, or how parts of the project relate to each other.

GLIA solves this by maintaining a **persistent relational memory** that grows with every interaction and strengthens with use.

---

## How is it different?

| Feature | RAG | Graphs | Plain Text | **GLIA** |
|---|---|---|---|---|
| Stores | Vectorized chunks | Nodes + edges | Indexed text | **Distributed patterns (glyphs)** |
| Searches by | Cosine similarity | BFS/DFS traversal | Keywords | **Resonance (parallel projection)** |
| Relationships | None | Explicit edges | None | **Holographic (encoded in the vector)** |
| If you corrupt 30% | Loses chunks | Loses paths | Loses text | **Keeps working (holographic property)** |
| Analogical reasoning | No | No | No | **Yes (vector arithmetic)** |
| Cost to index | Tokens | Tokens | $0 | **$0 (AST parsing)** |
| Storage | O(N×D) | O(N + E) | O(N) | **Constant O(R×D) per region** |

---

## Capabilities a graph CANNOT do

GLIA demonstrates operations that are structurally impossible in a traditional graph:

1. **One-shot learning**: A single `bind(A, B)` operation creates a retrievable association. No iterative training.
2. **Graceful degradation**: Corrupt 30% of dimensions → similarity 0.85. A graph with 30% deleted edges loses entire paths.
3. **Analogical reasoning**: `king - man + woman ≈ queen`. Without an explicit "king→queen" edge.
4. **Conjunctive queries**: Search for things related to A **AND** B simultaneously via superposition.
5. **Storage O(D)**: 500 glyphs in 8KB. A graph would potentially need 250K edges.

Run `python examples/demo_v2.py` to see these capabilities in action.

---

## Installation

GLIA is installed **once** on your machine as a global tool. It is cloned to any location (NOT inside your project).

**Step 1: Clone GLIA**

```bash
# Anywhere on your machine
cd ~/tools
git clone https://github.com/FelipeFariasAlfaro/glia.git
cd glia
```

**Step 2: Install**

```bash
pip install -e .
```

**Step 3: Verify**

```bash
python -m glia --version
# Output: glia, version 0.1.0-alpha
```

> **Windows Note:** If you see a PATH warning, use `python -m glia` instead of `glia`.

---

## Usage in your project

Go to **your project** (the one you want GLIA to remember) and initialize:

**Step 1: Initialize**

```bash
cd /path/to/your/project
python -m glia init
```

Creates a `.glia/` folder with an empty `memory.db`. Add `.glia/` to your `.gitignore`.

**Step 2: Scan (free, instant, no AI)**

```bash
python -m glia scan
```

Parses all files with AST. Extracts functions, classes, imports, docstrings. Creates glyphs in the substrate. Takes seconds, costs $0, no API key needed.

**Step 3: Recall**

```bash
python -m glia recall "JWT authentication"
python -m glia recall "database configuration"
```

**Step 4: Teach (optional, uses Gemini Flash)**

```bash
python -m glia learn "The session bug was because the token expired in ms instead of seconds. Fix in auth.py line 25."
```

For this you need a `.env` in your project:
```
GEMINI_API_KEY=your_key_here
GLIA_MODEL=gemini-2.0-flash
```

Get your free key at: https://aistudio.google.com/apikey

> **Important:** The API key is only needed for `glia learn`. The `scan`, `recall`, `stats`, and `forget` commands work **without an API key**.

---

## Folder Structure

```
~/tools/glia/                  ← GLIA source code (cloned once)
    src/glia/
    pyproject.toml

~/projects/my-api/             ← YOUR project
    .glia/                     ← Created by 'glia init' (add to .gitignore)
        memory.db              ← Holographic memory of this project
    .env                       ← Your API key (add to .gitignore)
    src/
    ...

~/projects/other-project/      ← Another project (separate memory)
    .glia/
        memory.db
    ...
```

Each project has its own memory. GLIA is installed once and used across many projects.

---

## How does GLIA work internally?

### The analogy: The brain is not a hard drive

When you remember the smell of a cake, your brain doesn't search for a folder named "Memories/Cakes/smell.txt". What happens is that a small stimulus (the smell) **activates a pattern** of neurons that, by interference, reconstructs the complete memory: the kitchen, your grandmother, the conversation you had.

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

**Why 1024 dimensions?** In high-dimensional spaces, random vectors are nearly orthogonal to each other (similarity ≈ 0). This allows storing thousands of concepts without them "stepping" on each other.

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
│  Region:                                                         │
│  [0.06, 0.03, 0.07, ..., 0.09, 0.11, 0.02]                     │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │ All 3 glyphs COEXIST in the same       │                    │
│  │ vector. There are no separate rows.     │                    │
│  │ The region size is CONSTANT             │                    │
│  │ (1024 floats) regardless of how many    │                    │
│  │ glyphs are stored.                      │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**How is it possible they are not lost?** Because in 1024 dimensions, random vectors are nearly orthogonal. Each glyph "lives" in its own direction in space. When added, they do not destroy each other — they coexist like superposed waves.

---

### Step 3: Relationships — Holographic Encoding (no edges)

In a graph, the relationship "A is connected to B" is stored as an explicit edge in a table. In GLIA, relationships are encoded **within the same vector space** using circular convolution:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BINDING (Circular Convolution)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Concept A: "generate_token"                                    │
│  [0.02, -0.04, 0.08, ...]                                       │
│                                                                  │
│  Concept B: "jwt_secret"                                        │
│  [0.05, 0.01, -0.03, ...]                                       │
│                                                                  │
│         bind(A, B) = circular_convolution(A, B)                  │
│                                                                  │
│  Result: [0.07, -0.02, 0.01, ...]                               │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │ Binding properties:                     │                    │
│  │                                         │                    │
│  │ • bind(A,B) is DIFFERENT from A and B   │                    │
│  │ • unbind(bind(A,B), A) ≈ B              │                    │
│  │ • Creates no explicit "edge"            │                    │
│  │ • The relationship LIVES in the vector  │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  This binding is ADDED to the substrate:                         │
│  substrate += bind(A, B)                                         │
│                                                                  │
│  Now, if you ask for A in the future,                           │
│  the substrate also "resonates" with B                           │
│  because its interference is encoded there.                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**There is no edge table. There is no list of relationships. Relationships are interference patterns within the vector itself.**

---

### Step 4: Retrieval — Resonance (not search)

When you ask something, GLIA doesn't search a table. It encodes your question as a vector and **projects** it against all glyphs simultaneously:

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESONANCE                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Query: "why do tokens expire?"                                 │
│         │                                                        │
│         ▼ encode_text()                                          │
│  Stimulus: [0.03, -0.02, 0.06, ..., 0.01, 0.04, -0.03]        │
│         │                                                        │
│         ▼ compare against ALL glyphs (parallel)                │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                                                       │       │
│  │  cosine(stimulus, glyph_1) = 0.69  ← RESONATES!    │       │
│  │  cosine(stimulus, glyph_2) = 0.13                    │       │
│  │  cosine(stimulus, glyph_3) = 0.12                    │       │
│  │  cosine(stimulus, glyph_4) = 0.04                    │       │
│  │  cosine(stimulus, glyph_5) = 0.02                    │       │
│  │  ...                                                  │       │
│  │  cosine(stimulus, glyph_N) = 0.01                    │       │
│  │                                                       │       │
│  │  All are compared AT THE SAME TIME.                   │       │
│  │  There is no sequential traversal.                    │       │
│  │  There is no "next node".                             │       │
│  │  It is parallel projection.                           │       │
│  │                                                       │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Result: The glyphs that "resonate" (high similarity)          │
│  are those that share a pattern with your question.             │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**The key difference with a graph:** In a graph, if there is no path of edges between A and B, you never connect them. In GLIA, if A and B share a pattern (even if they were never explicitly "connected"), they resonate together.

---

### Step 5: Plasticity — The memory is alive

Glyphs are not static. They have **magnitude** (volume) that changes with use:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLASTICITY                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  REINFORCEMENT (Hebbian): Every time a glyph resonates         │
│  in a query, its magnitude INCREASES.                           │
│                                                                  │
│  Day 1:  jwt_auth  magnitude: 1.0  ████████████                  │
│  Day 5:  jwt_auth  magnitude: 1.2  ██████████████  (used 4x)   │
│  Day 10: jwt_auth  magnitude: 1.4  ████████████████ (used 8x)  │
│                                                                  │
│  Frequent patterns "sound louder" in future                     │
│  queries. They become easier to find.                           │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  DECAY: Glyphs that are NOT used lose magnitude.               │
│                                                                  │
│  Day 1:  old_framework  magnitude: 1.0  ████████████             │
│  Day 30: old_framework  magnitude: 0.7  ████████  (unused)     │
│  Day 90: old_framework  magnitude: 0.3  ████     (still unused)│
│  Day 180: old_framework magnitude: 0.0  (forgotten)            │
│                                                                  │
│  The memory AUTO-CLEANS. Only the relevant survives.            │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  CO-ACTIVATION: If two glyphs resonate together in the same    │
│  query, a binding is created between them in the substrate.     │
│                                                                  │
│  Query activates jwt_auth AND session_bug simultaneously       │
│  → substrate += bind(jwt_auth, session_bug) × 0.02             │
│  → In future queries, asking for one will activate the other    │
│                                                                  │
│  "What resonates together, binds stronger."                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Step 6: The Output — Cognitive Map

GLIA does not return raw text or entire files. It returns a structured **cognitive map**:

```
## GLIA Cognitive Map for: "generate JWT token"

### Resonating Patterns (by strength)
  • [0.69] auth_generate_token: Generate a JWT-like token for the user. (src/auth.py)
  • [0.13] auth_verify_token: Verify and decode a token. (src/auth.py)
  • [0.12] module_auth: Authentication module - JWT token management. (src/auth.py)
  • [0.05] app_login: Authenticate user and return JWT token. (src/app.py)

### Source Files
  → src/auth.py
  → src/app.py
```

The agent receives:
- **Which patterns resonated** (and with what strength)
- **What each one means** (1-line intention)
- **Where to look** if it needs more detail

It does not receive blocks of text to decipher. It receives a navigation map.

---

### Full workflow of a session

```
┌─────────────────────────────────────────────────────────────────┐
│                     WORK SESSION                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. MCP Server starts                                            │
│     ├──▶ Detects changed files (hash comparison)                │
│     ├──▶ AST re-scans modified ones (free)                      │
│     └──▶ Substrate updated with new glyphs                      │
│                                                                  │
│  2. User asks: "why is login failing?"                          │
│     ├──▶ Agent calls glia_recall("login failing")               │
│     ├──▶ Query is encoded as vector                             │
│     ├──▶ Parallel resonance against all glyphs                  │
│     ├──▶ Top-K resonant glyphs reinforced (+magnitude)          │
│     ├──▶ Co-activation among top results                        │
│     └──▶ Cognitive map returned to agent                        │
│                                                                  │
│  3. Agent fixes the bug                                         │
│     ├──▶ Agent calls glia_learn("Login failed because...")      │
│     ├──▶ Gemini Flash distills into concepts                    │
│     ├──▶ Each concept encoded as glyph                          │
│     ├──▶ Relationships encoded as bindings                      │
│     └──▶ Everything superposed into substrate                   │
│                                                                  │
│  4. Dev commits                                                 │
│     ├──▶ Git hook captures message + files                      │
│     └──▶ Registered as historical knowledge                     │
│                                                                  │
│  5. Time passes without using certain concepts                  │
│     ├──▶ Decay reduces magnitude of unused glyphs               │
│     └──▶ Glyphs with 0 magnitude effectively forgotten          │
│                                                                  │
│  ═══════════════════════════════════════════════════════════     │
│  RESULT: Memory GROWS with the relevant                          │
│          and FORGETS the obsolete — automatically                │
│  ═══════════════════════════════════════════════════════════     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Why is this NOT a graph?

| Property | Graph | GLIA |
|---|---|---|
| Structure | Nodes + Explicit edges | Superposed vectors in a continuous space |
| Relationships | Edge table | Interference patterns (bindings) |
| Retrieval | Sequential traversal (BFS/DFS) | Parallel projection (cosine similarity) |
| If you delete 30% | You lose entire paths | Keeps working (holographic property) |
| Analogies | Impossible | Native (vector arithmetic) |
| Storage | Grows with each relationship (O(N²)) | Constant per region (O(D)) |
| Edge table in DB | Yes | **NO** |

If you open GLIA's `memory.db`, you will find `substrate_regions` and `glyphs` tables. **You will not find any edge or relationship table.** Relationships do not exist as records — they exist as mathematical interferences within the vectors.

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

### 🛡️ Methodological Integrity

Our benchmarks are not estimates; they are rigorous tests designed under Information Retrieval standards:
1. **Zero-Shot Evaluation:** GLIA was not pre-trained on the test projects. All evaluations are *zero-shot* using the standard AST scanner.
2. **Industry Metrics:** We use **MRR** (Mean Reciprocal Rank) and **nDCG** instead of subjective metrics, ensuring that the order and precision of the delivered context are optimal for the LLM.
3. **Real Token Calculation:** The 97% savings is not an approximation (characters / 4). It is measured using `tiktoken` (cl100k_base), accurately reflecting the impact on your API bill.
4. **Reproducibility:** All evaluation scripts (`run_benchmark_v2.py`) and test repositories (e-commerce, ML pipeline, frontend) are included in the repository for public verification.

📊 [View full benchmarks](docs/benchmarks/BENCHMARK_SUMMARY.md)

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

GLIA exposes itself as an MCP server compatible with any MCP client.

### Cline (VS Code)

In Cline's MCP settings:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "C:\\path\\to\\your\\project",
        "GEMINI_API_KEY": "your_key",
        "GLIA_MODEL": "gemini-3.1-flash-lite-preview"
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
        "GLIA_WORKSPACE": ".",
        "GEMINI_API_KEY": "your_key",
        "GLIA_MODEL": "gemini-3.1-flash-lite-preview"
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
        "GLIA_WORKSPACE": "/path/to/project",
        "GEMINI_API_KEY": "your_key"
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
        "GLIA_WORKSPACE": ".",
        "GEMINI_API_KEY": "your_key"
      }
    }
  }
}
```

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

## How it works

GLIA uses **Holographic Distributed Memory** based on Vector Symbolic Architectures (VSA):

1. **Encoding**: Text/code → 1024-dimensional vector (deterministic, no AI)
2. **Storage**: Glyphs are superposed in substrate regions (vector addition)
3. **Relationships**: Holographically encoded via circular convolution (no edges)
4. **Retrieval**: Query → vector → cosine similarity against all glyphs (parallel)
5. **Plasticity**: Used patterns are reinforced, unused ones decay

```
Query: "generate JWT token"
         │
         ▼ encode_text()
    [1024-d vector]
         │
         ▼ resonate() — parallel comparison
         │
    ┌────┴────────────────────────────────────────┐
    │  auth_generate_token  (0.69)  ← resonated!  │
    │  auth_verify_token    (0.13)                 │
    │  module_auth          (0.12)                 │
    │  app_login            (0.05)                 │
    └─────────────────────────────────────────────┘
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed diagrams.

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

## Demo (no API key)

```bash
python examples/demo_v2.py
```

Demonstrates: resonance, one-shot learning, graceful degradation, analogical reasoning, conjunctive queries, and storage efficiency.

---

## Requirements

- **Python 3.11+**
- **numpy**
- **Git** (for the automatic hook)
- **Gemini API Key** (optional — only for `glia learn`)

---

## Project Structure

```
glia/
├── src/glia/
│   ├── binding.py           # Circular convolution (bind/unbind)
│   ├── encoder.py           # Deterministic encoding text→vector
│   ├── synonyms.py          # Static programming synonym dictionary
│   ├── substrate.py         # Memory regions with superposition
│   ├── resonance.py         # Retrieval by parallel projection + unbinding
│   ├── plasticity.py        # Hebbian reinforcement + temporal decay
│   ├── cognitive_map.py     # Structured output for LLMs
│   ├── brain.py             # Main orchestrator
│   ├── storage.py           # SQLite persistence (BLOB vectors, no edges)
│   ├── embeddings.py        # Optional embeddings (Gemini, enhanced mode)
│   ├── distiller.py         # LLM distillation (Gemini Flash)
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

---

## Author

**Felipe Farías Alfaro**
- GitHub: [FelipeFariasAlfaro](https://github.com/FelipeFariasAlfaro)
- Web: [felipefariasalfaro.github.io](https://felipefariasalfaro.github.io)

---

## License

[MIT](LICENSE)
