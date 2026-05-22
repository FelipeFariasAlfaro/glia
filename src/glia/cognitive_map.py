"""
GLIA Cognitive Map - Structured output for LLM consumption.
"""

from __future__ import annotations

from .substrate import GlyphMeta


def build_cognitive_map(query: str, results: list[tuple[GlyphMeta, float]], associations: list[dict] | None = None, sources: list[str] | None = None) -> str:
    parts = []
    parts.append(f"## GLIA Cognitive Map for: \"{query}\"")
    parts.append("")

    if results:
        parts.append("### Resonating Patterns (by strength)")
        for glyph, score in results[:10]:
            source_tag = f" ({glyph.source})" if glyph.source else ""
            parts.append(f"  • [{score:.2f}] {glyph.id}: {glyph.content[:120]}{source_tag}")
        parts.append("")

    if associations:
        parts.append("### Discovered Associations")
        for assoc in associations[:8]:
            parts.append(f"  {assoc.get('from', '?')} ↔ {assoc.get('to', '?')} (strength: {assoc.get('strength', 0):.2f})")
        parts.append("")

    if sources:
        parts.append("### Source Files")
        for src in sources[:8]:
            parts.append(f"  → {src}")
        parts.append("")

    if results:
        high_activation = [g for g, s in results if g.activation_count > 3]
        if high_activation:
            parts.append("### Memory Insights")
            for g in high_activation[:3]:
                parts.append(f"  • '{g.id}' activated {g.activation_count}x — frequently relevant")
            parts.append("")

    if not results:
        parts.append("No resonating patterns found for this query.")

    return "\n".join(parts)
