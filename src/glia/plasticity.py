"""Hebbian reinforcement and temporal decay for GLIA's HDM substrate."""

from __future__ import annotations

import hashlib
import math
import time

import numpy as np

from .binding import bind
from .substrate import GlyphMeta, RelationshipMeta, Substrate


def reinforce(glyph: GlyphMeta, substrate: Substrate, amount: float = 0.05) -> None:
    """Strengthen a retrieved pattern and keep its region contribution in sync."""
    magnitude = min(2.0, glyph.magnitude + amount)
    substrate.set_glyph_magnitude(glyph, magnitude)
    substrate.record_activation(glyph)


def decay_all(
    glyphs: list[GlyphMeta],
    substrate: Substrate,
    rate: float = 0.01,
    now: float | None = None,
) -> int:
    """Apply temporal decay and return the number of newly forgotten glyphs."""
    current_time = time.time() if now is None else now
    forgotten = 0
    for glyph in glyphs:
        was_active = glyph.magnitude > 0
        hours_since = max(0.0, (current_time - glyph.last_activated) / 3600)
        decay_amount = rate * math.log1p(hours_since)
        magnitude = max(0.0, glyph.magnitude - decay_amount)
        substrate.set_glyph_magnitude(glyph, magnitude)
        if was_active and magnitude <= 0:
            forgotten += 1
    return forgotten


def co_activate(
    substrate: Substrate,
    glyph_a: GlyphMeta,
    glyph_b: GlyphMeta,
    strength: float = 0.1,
    max_norm: float = 1.0,
) -> RelationshipMeta:
    """Store bounded, identifiable Hebbian interference for a glyph pair.

    Repeated co-activation accumulates but saturates, avoiding both anonymous
    region drift and unbounded growth. It remains a holographic contribution,
    not an explicit semantic edge.
    """
    if glyph_a.region_id != glyph_b.region_id:
        raise ValueError("Co-activated glyphs must belong to the same region")
    if strength < 0 or max_norm <= 0:
        raise ValueError("strength must be non-negative and max_norm positive")

    pair = "|".join(sorted((glyph_a.id, glyph_b.id)))
    digest = hashlib.sha256(
        f"{glyph_a.region_id}|{pair}".encode("utf-8")
    ).hexdigest()[:24]
    relationship_id = f"plasticity:{digest}"
    association = bind(glyph_a.vector, glyph_b.vector) * strength
    existing = substrate.relationships.get(relationship_id)
    combined = association if existing is None else existing.vector + association
    norm = float(np.linalg.norm(combined))
    if norm > max_norm:
        combined = combined * (max_norm / norm)

    return substrate.store_relationship(
        combined,
        region_id=glyph_a.region_id,
        relationship_id=relationship_id,
        source="plasticity:recall",
    )
