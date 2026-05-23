"""
GLIA MCP Server v2 - Holographic Distributed Memory via MCP.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .config import get_config

workspace = Path(os.environ.get("GLIA_WORKSPACE", os.getcwd()))
config = get_config(workspace)

from .brain import GliaBrain
from .scanner import Scanner

brain = GliaBrain(
    workspace=config.workspace,
    api_key=config.api_key,
    model=config.model,
    provider=config.provider,
)

if not brain.is_initialized:
    brain.init()

_scanner = Scanner(brain)
_sync_result = _scanner.sync_changes()
if _sync_result["changed"] > 0:
    print(f"[GLIA] Synced {_sync_result['updated']} changed files.", file=sys.stderr)

mcp = FastMCP(
    "GLIA",
    instructions="GLIA is a holographic distributed memory. Use glia_recall to retrieve context via pattern resonance. Use glia_learn to teach new knowledge.",
)


@mcp.tool()
def glia_recall(query: str, top_k: int = 10) -> str:
    """
    Recall associated knowledge from GLIA's memory via spreading activation.

    Given a concept or question, GLIA activates related nodes in its
    knowledge graph and returns the associated context. Use this to get
    project context, understand relationships between components, or
    recall past decisions and bug fixes.

    Args:
        query: The concept, question, or topic to recall (e.g. "auth token", "database config")
        top_k: Maximum number of nodes to activate (default 10)

    Returns:
        Associated context reconstructed from the memory graph.
    """
    result = brain.recall(query, top_k=top_k)
    return result["context"] or "No associations found in memory for this query."


@mcp.tool()
def glia_learn(content: str, source: str = "") -> str:
    """
    Teach GLIA new knowledge. The content is distilled into concepts
    and relationships, then integrated into the associative graph.

    Use this after solving a bug, making an architectural decision,
    or discovering something important about the project.

    Args:
        content: The knowledge to learn (text, code explanation, decision, etc.)
        source: Optional source reference (file path, ticket ID, etc.)

    Returns:
        Summary of what was learned (concepts extracted and connections made).
    """
    try:
        result = brain.learn(content, source=source)
        concepts = result.get("concepts", [])
        return f"Learned! Encoded {len(concepts)} glyphs.\nConcepts: {', '.join(concepts)}\nSummary: {result.get('summary', '')}"
    except Exception as e:
        return f"Error learning: {e}"


@mcp.tool()
def glia_scan(path: str = "") -> str:
    """
    Scan a project directory and learn from all source files.
    Only processes new or modified files (incremental).

    Use this when first onboarding to a project or after major changes.

    Args:
        path: Directory to scan (defaults to workspace root)

    Returns:
        Scan statistics (files learned, skipped, errors).
    """
    scan_path = Path(path) if path else None
    scanner = Scanner(brain)
    stats = scanner.scan(path=scan_path)
    return f"Scan complete!\n  Files learned: {stats['learned']}\n  Files skipped: {stats['skipped']}\n  Errors: {stats['errors']}"


@mcp.tool()
def glia_learn_file(file_path: str) -> str:
    """
    Learn from a specific file. Use this when a file has been modified
    and you want GLIA to update its knowledge about it.

    Args:
        file_path: Path to the file to learn from (relative or absolute)

    Returns:
        Whether the file was learned or skipped.
    """
    filepath = Path(file_path)
    if not filepath.is_absolute():
        filepath = workspace / filepath
    if not filepath.exists():
        return f"File not found: {file_path}"
    scanner = Scanner(brain)
    learned = scanner.scan_file(filepath)
    return f"Learned from {file_path}." if learned else f"File {file_path} unchanged. Skipped."


@mcp.tool()
def glia_stats() -> str:
    """
    Get statistics about GLIA's current memory state.

    Returns:
        Number of concepts (nodes), connections (edges), and memories (threads).
    """
    stats = brain.stats()
    return f"GLIA Memory Stats:\n  Glyphs (patterns): {stats['nodes']}\n  Dimension: {stats['dimension']}\n  Regions: {stats['regions']}\n  Edges: 0 (holographic — no explicit edges)"


@mcp.tool()
def glia_forget(decay_rate: float = 0.01) -> str:
    """
    Apply temporal decay to memory connections.
    Weak/unused connections are pruned (forgotten).
    Stronger, frequently-used connections survive.

    Args:
        decay_rate: How aggressively to decay (0.01 = gentle, 0.1 = aggressive)

    Returns:
        How many connections were pruned.
    """
    result = brain.forget(decay_rate=decay_rate)
    return f"Decay applied:\n  Before: {result['edges_before']}\n  After: {result['edges_after']}\n  Forgotten: {result['pruned']}"


@mcp.tool()
def glia_changes() -> str:
    """
    Detect files that changed since GLIA last scanned them.
    Use this to understand what the user modified manually
    between sessions. Returns the list of changed files.

    If files changed, consider asking the user what they changed
    and why, then use glia_learn to record the intention.

    Returns:
        List of changed files, or a message if nothing changed.
    """
    scanner = Scanner(brain)
    changed = scanner.detect_changes()
    if not changed:
        return "No files changed since last scan. Memory is up to date."
    scanner.sync_changes()
    result = f"Detected {len(changed)} changed files (structure auto-updated):\n"
    for f in changed[:20]:
        result += f"  • {f}\n"
    return result


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
