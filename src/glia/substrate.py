"""
GLIA Substrate - The distributed memory space.

The substrate stores glyphs (knowledge patterns) via superposition.
There are no edges. Relationships are encoded holographically.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from .binding import DIMENSION


@dataclass
class GlyphMeta:
    """Metadata for a stored glyph (a knowledge pattern)."""

    id: str
    vector: np.ndarray
    magnitude: float = 1.0
    created_at: float = field(default_factory=time.time)
    last_activated: float = field(default_factory=time.time)
    activation_count: int = 0
    source: str = ""
    content: str = ""
    region_id: str = "default"


@dataclass
class SubstrateRegion:
    """A region that stores superimposed glyphs. Fixed size regardless of count."""

    id: str = "default"
    vector: np.ndarray = field(default_factory=lambda: np.zeros(DIMENSION))
    glyph_count: int = 0
    capacity: int = 500
    created_at: float = field(default_factory=time.time)


class Substrate:
    """The memory substrate — manages regions and glyphs. No edges."""

    def __init__(self, dimension: int = DIMENSION):
        self.dimension = dimension
        self.regions: dict[str, SubstrateRegion] = {}
        self.glyphs: dict[str, GlyphMeta] = {}

    def get_or_create_region(self, region_id: str = "default") -> SubstrateRegion:
        if region_id not in self.regions:
            self.regions[region_id] = SubstrateRegion(id=region_id, vector=np.zeros(self.dimension))
        return self.regions[region_id]

    def store_glyph(self, glyph_id: str, vector: np.ndarray, content: str = "", source: str = "", region_id: str = "default") -> GlyphMeta:
        """Store a glyph via superposition into a region."""
        region = self.get_or_create_region(region_id)

        if glyph_id in self.glyphs:
            meta = self.glyphs[glyph_id]
            region.vector -= meta.vector * meta.magnitude
            meta.vector = vector
            meta.content = content or meta.content
            meta.source = source or meta.source
        else:
            meta = GlyphMeta(id=glyph_id, vector=vector, content=content, source=source, region_id=region_id)
            self.glyphs[glyph_id] = meta
            region.glyph_count += 1

        region.vector += vector * meta.magnitude
        return meta

    def store_relationship(self, relationship_vector: np.ndarray, region_id: str = "default") -> None:
        """Store a relationship as interference in the substrate. No edge table."""
        region = self.get_or_create_region(region_id)
        region.vector += relationship_vector

    def get_all_glyphs(self) -> list[GlyphMeta]:
        return list(self.glyphs.values())

    def stats(self) -> dict:
        return {
            "dimension": self.dimension,
            "regions": len(self.regions),
            "glyphs": len(self.glyphs),
            "total_capacity": sum(r.capacity for r in self.regions.values()),
        }
