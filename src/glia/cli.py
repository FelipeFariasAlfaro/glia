"""
GLIA CLI - Command line interface for the associative memory system.

Commands:
  glia init          - Initialize GLIA in the current directory
  glia scan          - Scan and learn the entire project
  glia learn <text>  - Teach GLIA something new
  glia recall <query> - Recall associated knowledge
  glia stats         - Show memory statistics
  glia forget        - Apply decay to weak connections
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from .brain import GliaBrain
from .config import get_config


def _get_brain() -> GliaBrain:
    """Get a GliaBrain instance for the current workspace."""
    config = get_config()
    return GliaBrain(
        workspace=config.workspace,
        api_key=config.api_key,
        model=config.model,
        provider=config.provider,
    )


@click.group()
@click.version_option(version="0.1.0-alpha", prog_name="glia")
def main():
    """GLIA - Associative Memory with Spreading Activation for AI Agents."""
    pass


@main.command()
def init():
    """Initialize GLIA in the current directory."""
    brain = _get_brain()
    if brain.is_initialized:
        click.echo("⚡ GLIA already initialized in this directory.")
        return
    brain.init()
    click.echo("🧠 GLIA initialized. Memory graph created in .glia/")
    click.echo("   Start teaching with: glia learn \"<knowledge>\"")


@main.command()
@click.argument("content")
@click.option("--source", "-s", default="", help="Source of the knowledge (file, url, etc.)")
@click.option("--offline", is_flag=True, help="Skip LLM distillation (manual mode)")
def learn(content: str, source: str, offline: bool):
    """Teach GLIA something new. Content is distilled into concepts and connections."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    # Check if content is a file path
    content_path = Path(content)
    if content_path.exists() and content_path.is_file():
        content = content_path.read_text(encoding="utf-8")
        source = source or str(content_path)
        click.echo(f"📄 Reading file: {content_path}")

    click.echo("🔬 Distilling knowledge...")

    try:
        result = brain.learn(content, source=source)
        concepts = result.get("concepts", [])
        relationships = result.get("relationships", [])
        summary = result.get("summary", "")

        click.echo(f"✅ Learned! Extracted {len(concepts)} concepts, {len(relationships)} connections.")
        click.echo(f"   Concepts: {', '.join(concepts)}")
        click.echo(f"   Summary: {summary}")
    except Exception as e:
        click.echo(f"❌ Error during distillation: {e}")
        sys.exit(1)


@main.command()
@click.option("--path", "-p", default="", help="Directory to scan (defaults to current)")
@click.option("--force", is_flag=True, help="Re-scan all files even if unchanged")
def scan(path: str, force: bool):
    """Scan the project and learn from all source files (incremental)."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    from .scanner import Scanner
    scanner = Scanner(brain)

    scan_path = Path(path) if path else None
    click.echo("🔍 Scanning project files...")

    def on_file(filepath: str, status: str):
        if status == "learning":
            click.echo(f"   📄 Learning: {filepath}")
        elif status == "skipped":
            pass  # Silent for skipped files
        elif status.startswith("error"):
            click.echo(f"   ❌ {filepath}: {status}")

    stats = scanner.scan(path=scan_path, on_file=on_file, force=force)

    click.echo(f"\n✅ Scan complete!")
    click.echo(f"   Files learned:   {stats['learned']}")
    click.echo(f"   Files skipped:   {stats['skipped']} (unchanged)")
    click.echo(f"   Errors:          {stats['errors']}")

    brain_stats = brain.stats()
    click.echo(f"\n📊 Memory now has {brain_stats['nodes']} concepts, "
               f"{brain_stats['edges']} connections, {brain_stats['threads']} memories.")


@main.command()
@click.option("--path", "-p", default=".", help="Directory to watch (defaults to current)")
def watch(path: str):
    """Monitor directory and learn from changes in real-time."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    from .watcher import watch_directory
    
    watch_path = Path(path).resolve()
    click.echo(f"👀 GLIA Watcher started. Monitoring: {watch_path}")
    click.echo("   Press Ctrl+C to stop.")

    def on_update(rel_path, result):
        concepts = result.get("concepts", [])
        click.echo(f"\n[Watcher] ✅ Learned from {rel_path}")
        if concepts:
            click.echo(f"          Concepts: {', '.join(concepts[:5])}{'...' if len(concepts) > 5 else ''}")

    try:
        watch_directory(brain, watch_path, on_update=on_update)
    except KeyboardInterrupt:
        click.echo("\n🛑 Watcher stopped.")
    except Exception as e:
        click.echo(f"\n❌ Watcher error: {e}")
        sys.exit(1)


@main.command()
@click.argument("query")
@click.option("--top-k", "-k", default=10, help="Max nodes to activate")
@click.option("--raw", is_flag=True, help="Show raw activation data")
def recall(query: str, top_k: int, raw: bool):
    """Recall associated knowledge via spreading activation."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    result = brain.recall(query, top_k=top_k)

    activated = result["activated_nodes"]
    if not activated:
        click.echo(f"🔍 No associations found for '{query}'.")
        click.echo("   Try teaching GLIA first with: glia learn \"<knowledge>\"")
        return

    click.echo(f"🧠 Spreading activation from '{query}':")
    click.echo(f"   Activated {len(activated)} nodes:\n")

    for node_id, activation in activated:
        bar = "█" * int(activation * 20)
        click.echo(f"   {node_id:30s} {bar} ({activation:.3f})")

    if raw:
        click.echo(f"\n--- Raw context for LLM ---")
        click.echo(result["context"])
    else:
        threads = result.get("threads", [])
        if threads:
            click.echo(f"\n📝 Associated memories ({len(threads)}):")
            for t in threads[:5]:
                click.echo(f"\n   [{t['id']}] (relevance: {t['score']:.2f})")
                # Show first 150 chars of content
                preview = t["content"][:150].replace("\n", " ")
                click.echo(f"   {preview}...")


@main.command()
def stats():
    """Show memory statistics."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    s = brain.stats()
    click.echo("🧠 GLIA Memory Stats:")
    click.echo(f"   Nodes (concepts):     {s['nodes']}")
    click.echo(f"   Edges (connections):   {s['edges']}")
    click.echo(f"   Avg connections/node:  {s['avg_connections']:.1f}")
    click.echo(f"   Threads (memories):    {s['threads']}")


@main.command()
@click.option("--rate", "-r", default=0.01, help="Decay rate (higher = more aggressive)")
def forget(rate: float):
    """Apply temporal decay. Weak/unused connections are pruned."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    result = brain.forget(decay_rate=rate)
    click.echo(f"🧹 Decay applied (rate={rate}):")
    click.echo(f"   Edges before: {result['edges_before']}")
    click.echo(f"   Edges after:  {result['edges_after']}")
    click.echo(f"   Pruned:       {result['pruned']} dead synapses")


@main.command()
@click.argument("query")
def context(query: str):
    """Get raw context string ready to inject into an LLM prompt."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized.", err=True)
        sys.exit(1)

    result = brain.recall(query, top_k=10)
    # Output only the context (for piping into other tools)
    click.echo(result["context"])


@main.command()
def serve():
    """Start the GLIA MCP server (for IDE/CLI integration)."""
    click.echo("🧠 Starting GLIA MCP server...")
    click.echo(f"   Workspace: {Path.cwd()}")
    click.echo("   Transport: stdio")
    click.echo("   Ready for connections from Gemini CLI, Claude, VS Code, etc.")
    from .mcp_server import main as mcp_main
    mcp_main()


@main.command()
def hook():
    """Install git hook for automatic learning from commits."""
    git_dir = Path.cwd() / ".git"
    if not git_dir.exists():
        click.echo("❌ Not a git repository. Run 'git init' first.")
        sys.exit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    hook_source = Path(__file__).parent / "hooks" / "post-commit"
    hook_dest = hooks_dir / "post-commit"

    if hook_dest.exists():
        click.echo("⚠️  post-commit hook already exists. Skipping.")
        return

    hook_content = hook_source.read_text(encoding="utf-8")
    hook_dest.write_text(hook_content, encoding="utf-8")

    click.echo("✅ Git hook installed: .git/hooks/post-commit")
    click.echo("   GLIA will now learn from every commit automatically.")


@main.command()
def changes():
    """Detect files that changed since last scan."""
    brain = _get_brain()
    if not brain.is_initialized:
        click.echo("❌ GLIA not initialized. Run 'glia init' first.")
        sys.exit(1)

    from .scanner import Scanner
    scanner = Scanner(brain)
    changed = scanner.detect_changes()

    if not changed:
        click.echo("✅ No changes detected. Memory is up to date.")
        return

    click.echo(f"📝 {len(changed)} files changed since last scan:")
    for f in changed[:20]:
        click.echo(f"   • {f}")

    click.echo(f"\nRun 'glia scan' to update the structure, or 'glia learn' to record why.")


if __name__ == "__main__":
    main()
