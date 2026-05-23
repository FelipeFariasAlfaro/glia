"""
GLIA Plasticity Engine - Hebbian reinforcement and temporal decay.
No edges created — associations encoded as interference patterns.
"""

from __future__ import annotations

import math
import time

import numpy as np

from .binding import bind
from .substrate import Substrate, GlyphMeta


def reinforce(glyph: GlyphMeta, amount: float = 0.05) -> None:
    """Strengthen a pattern that was successfully retrieved."""
    glyph.magnitude = min(2.0, glyph.magnitude + amount)
    glyph.last_activated = time.time()
    glyph.activation_count += 1


def decay_all(glyphs: list[GlyphMeta], rate: float = 0.01) -> int:
    """Apply temporal decay. Returns count of forgotten glyphs."""
    now = time.time()
    forgotten = 0
    for glyph in glyphs:
        hours_since = (now - glyph.last_activated) / 3600
        decay_amount = rate * math.log1p(hours_since)
        glyph.magnitude = max(0.0, glyph.magnitude - decay_amount)
        if glyph.magnitude <= 0:
            forgotten += 1
    return forgotten


def co_activate(substrate: Substrate, glyph_a: GlyphMeta, glyph_b: GlyphMeta, strength: float = 0.1) -> None:
    """Fire together, wire together. Adds binding to substrate (no edge)."""
    association = bind(glyph_a.vector, glyph_b.vector) * strength
    region = substrate.get_or_create_region(glyph_a.region_id)
    region.vector += association
