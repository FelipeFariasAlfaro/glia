"""
GLIA Substrate - The distributed memory space.

The substrate stores glyphs (knowledge patterns) via superposition.
There are no edges. Relationships are encoded holographically.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field

import numpy as np

from .binding import DIMENSION


def _immutable_vector(value: np.ndarray) -> np.ndarray:
    """Return a float64 ndarray backed by immutable bytes, not owned memory."""
    array = np.asarray(value, dtype=np.float64)
    return np.frombuffer(array.tobytes(), dtype=np.float64).reshape(array.shape)


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

    _managed: bool = field(default=False, init=False, repr=False, compare=False)

    def __setattr__(self, name: str, value) -> None:
        """Prevent bypassing the substrate's superposition invariants."""
        if (
            name
            in {
                "id",
                "vector",
                "magnitude",
                "created_at",
                "last_activated",
                "activation_count",
                "source",
                "content",
                "region_id",
            }
            and getattr(self, "_managed", False)
        ):
            raise AttributeError(
                "Managed glyph metadata is immutable; use Substrate mutation APIs"
            )
        if name == "vector":
            value = _immutable_vector(value)
        super().__setattr__(name, value)


@dataclass
class RelationshipMeta:
    """A reversible contribution to a holographic region, not an explicit edge."""

    id: str
    vector: np.ndarray
    source: str = ""
    region_id: str = "default"

    _managed: bool = field(default=False, init=False, repr=False, compare=False)

    def __setattr__(self, name: str, value) -> None:
        if (
            name in {"id", "vector", "source", "region_id"}
            and getattr(self, "_managed", False)
        ):
            raise AttributeError(
                "Managed relationship metadata is immutable; use Substrate mutation APIs"
            )
        if name == "vector":
            value = _immutable_vector(value)
        super().__setattr__(name, value)


@dataclass
class SubstrateRegion:
    """A region that stores superimposed glyphs. Fixed size regardless of count."""

    id: str = "default"
    vector: np.ndarray = field(default_factory=lambda: np.zeros(DIMENSION))
    glyph_count: int = 0
    capacity: int = 500
    created_at: float = field(default_factory=time.time)
    _managed: bool = field(default=False, init=False, repr=False, compare=False)

    def __setattr__(self, name: str, value) -> None:
        if (
            name in {"id", "vector", "glyph_count", "capacity", "created_at"}
            and getattr(self, "_managed", False)
        ):
            raise AttributeError(
                "Managed region metadata is immutable; use Substrate mutation APIs"
            )
        if name == "vector":
            value = _immutable_vector(value)
        super().__setattr__(name, value)


@dataclass(frozen=True)
class MutationState:
    """Immutable checkpoint of pending persistence work."""

    regions: frozenset[str]
    glyphs: frozenset[str]
    relationships: frozenset[str]
    mutation_version: int


@dataclass(frozen=True)
class ResonanceSnapshot:
    """Immutable vectorized view used by repeated resonance queries."""

    mutation_version: int
    state_token: tuple[tuple[str, int, float], ...]
    glyphs: tuple[GlyphMeta, ...]
    vectors: np.ndarray
    scales: np.ndarray


class Substrate:
    """The memory substrate — manages regions and glyphs. No edges."""

    def __init__(self, dimension: int = DIMENSION):
        self.dimension = dimension
        self.regions: dict[str, SubstrateRegion] = {}
        self.glyphs: dict[str, GlyphMeta] = {}
        self.relationships: dict[str, RelationshipMeta] = {}
        self._dirty_regions: set[str] = set()
        self._dirty_glyphs: set[str] = set()
        self._dirty_relationships: set[str] = set()
        self._mutation_version = 0
        self._resonance_cache: ResonanceSnapshot | None = None

    @property
    def mutation_version(self) -> int:
        return self._mutation_version

    def dirty_snapshot(self) -> MutationState:
        """Capture pending deltas without exposing mutable tracking sets."""
        return MutationState(
            regions=frozenset(self._dirty_regions),
            glyphs=frozenset(self._dirty_glyphs),
            relationships=frozenset(self._dirty_relationships),
            mutation_version=self._mutation_version,
        )

    def tracking_checkpoint(self) -> MutationState:
        """Capture tracking state for an in-memory operation that may roll back."""
        return self.dirty_snapshot()

    def restore_tracking(self, checkpoint: MutationState) -> None:
        """Restore pending deltas and invalidate cached views after rollback."""
        self._dirty_regions = set(checkpoint.regions)
        self._dirty_glyphs = set(checkpoint.glyphs)
        self._dirty_relationships = set(checkpoint.relationships)
        self._mutation_version = checkpoint.mutation_version
        self._resonance_cache = None

    def mark_clean(self, expected_version: int | None = None) -> bool:
        """Clear committed deltas only if no later mutation occurred."""
        if expected_version is not None and expected_version != self._mutation_version:
            return False
        for region in self.regions.values():
            object.__setattr__(region, "_managed", True)
        for glyph in self.glyphs.values():
            object.__setattr__(glyph, "_managed", True)
        for relationship in self.relationships.values():
            object.__setattr__(relationship, "_managed", True)
        self._dirty_regions.clear()
        self._dirty_glyphs.clear()
        self._dirty_relationships.clear()
        return True

    def _record_mutation(
        self,
        *,
        regions: tuple[str, ...] = (),
        glyphs: tuple[str, ...] = (),
        relationships: tuple[str, ...] = (),
    ) -> None:
        self._dirty_regions.update(regions)
        self._dirty_glyphs.update(glyphs)
        self._dirty_relationships.update(relationships)
        self._mutation_version += 1
        self._resonance_cache = None

    def resonance_snapshot(self) -> ResonanceSnapshot:
        """Return a cached, read-only matrix for the current observable state."""
        state_token = tuple(
            (glyph.id, id(glyph.vector), float(glyph.magnitude))
            for glyph in self.glyphs.values()
        )
        cached = self._resonance_cache
        if (
            cached is not None
            and cached.mutation_version == self._mutation_version
            and cached.state_token == state_token
        ):
            return cached

        glyphs = tuple(glyph for glyph in self.glyphs.values() if glyph.magnitude > 0)
        if glyphs:
            vectors = np.stack([glyph.vector for glyph in glyphs]).astype(
                np.float64, copy=False
            )
            norms = np.linalg.norm(vectors, axis=1)
            magnitudes = np.asarray(
                [glyph.magnitude for glyph in glyphs], dtype=np.float64
            )
            scales = np.divide(
                magnitudes,
                norms,
                out=np.zeros_like(magnitudes),
                where=norms > 1e-12,
            )
        else:
            vectors = np.empty((0, self.dimension), dtype=np.float64)
            scales = np.empty(0, dtype=np.float64)

        vectors.setflags(write=False)
        scales.setflags(write=False)
        snapshot = ResonanceSnapshot(
            mutation_version=self._mutation_version,
            state_token=state_token,
            glyphs=glyphs,
            vectors=vectors,
            scales=scales,
        )
        self._resonance_cache = snapshot
        return snapshot

    def get_or_create_region(self, region_id: str = "default") -> SubstrateRegion:
        if region_id not in self.regions:
            self.regions[region_id] = SubstrateRegion(
                id=region_id,
                vector=np.zeros(self.dimension),
            )
            object.__setattr__(self.regions[region_id], "_managed", True)
            self._record_mutation(regions=(region_id,))
        return self.regions[region_id]

    @staticmethod
    def _add_to_region(region: SubstrateRegion, contribution: np.ndarray) -> None:
        object.__setattr__(
            region,
            "vector",
            _immutable_vector(region.vector + contribution),
        )

    def _validate_vector(self, vector: np.ndarray) -> np.ndarray:
        """Return an owned float64 vector with the substrate dimension."""
        value = np.asarray(vector, dtype=np.float64)
        if value.shape != (self.dimension,):
            raise ValueError(
                f"Expected vector with shape ({self.dimension},), got {value.shape}"
            )
        return _immutable_vector(value)

    def store_glyph(
        self,
        glyph_id: str,
        vector: np.ndarray,
        content: str = "",
        source: str = "",
        region_id: str = "default",
    ) -> GlyphMeta:
        """Store or replace a glyph while keeping region superposition consistent."""
        vector = self._validate_vector(vector)
        target_region = self.get_or_create_region(region_id)
        dirty_regions = {target_region.id}

        if glyph_id in self.glyphs:
            meta = self.glyphs[glyph_id]
            previous_region = self.get_or_create_region(meta.region_id)
            self._add_to_region(
                previous_region,
                -meta.vector * meta.magnitude,
            )
            dirty_regions.add(previous_region.id)
            if previous_region.id != target_region.id:
                object.__setattr__(
                    previous_region,
                    "glyph_count",
                    max(0, previous_region.glyph_count - 1),
                )
                object.__setattr__(
                    target_region,
                    "glyph_count",
                    target_region.glyph_count + 1,
                )
            object.__setattr__(meta, "region_id", target_region.id)
            object.__setattr__(meta, "vector", vector)
            object.__setattr__(meta, "content", content or meta.content)
            object.__setattr__(meta, "source", source or meta.source)
        else:
            meta = GlyphMeta(
                id=glyph_id,
                vector=vector,
                content=content,
                source=source,
                region_id=target_region.id,
            )
            self.glyphs[glyph_id] = meta
            object.__setattr__(
                target_region,
                "glyph_count",
                target_region.glyph_count + 1,
            )

        self._add_to_region(target_region, meta.vector * meta.magnitude)
        object.__setattr__(meta, "_managed", True)
        self._record_mutation(
            regions=tuple(dirty_regions),
            glyphs=(glyph_id,),
        )
        return meta

    def set_glyph_magnitude(self, glyph: GlyphMeta, magnitude: float) -> None:
        """Update a glyph strength and its weighted contribution atomically in memory."""
        canonical = self.glyphs.get(glyph.id)
        if canonical is not glyph:
            raise KeyError(f"Glyph {glyph.id!r} does not belong to this substrate")
        new_magnitude = max(0.0, float(magnitude))
        delta = new_magnitude - glyph.magnitude
        dirty_regions: tuple[str, ...] = ()
        if delta:
            region = self.get_or_create_region(glyph.region_id)
            self._add_to_region(region, glyph.vector * delta)
            object.__setattr__(glyph, "magnitude", new_magnitude)
            dirty_regions = (region.id,)
        self._record_mutation(regions=dirty_regions, glyphs=(glyph.id,))

    def record_activation(self, glyph: GlyphMeta, when: float | None = None) -> None:
        """Persist one activation without exposing mutable glyph metadata."""
        canonical = self.glyphs.get(glyph.id)
        if canonical is not glyph:
            raise KeyError(f"Glyph {glyph.id!r} does not belong to this substrate")
        object.__setattr__(glyph, "last_activated", time.time() if when is None else when)
        object.__setattr__(glyph, "activation_count", glyph.activation_count + 1)
        self._record_mutation(glyphs=(glyph.id,))

    def store_relationship(
        self,
        relationship_vector: np.ndarray,
        region_id: str = "default",
        relationship_id: str | None = None,
        source: str = "",
    ) -> RelationshipMeta:
        """Store an identifiable, reversible holographic contribution."""
        vector = self._validate_vector(relationship_vector)
        if relationship_id is None:
            digest = hashlib.sha256()
            digest.update(source.encode("utf-8"))
            digest.update(region_id.encode("utf-8"))
            digest.update(vector.tobytes())
            relationship_id = f"relationship:{digest.hexdigest()[:24]}"

        target_region = self.get_or_create_region(region_id)
        dirty_regions = {target_region.id}
        existing = self.relationships.get(relationship_id)
        if existing is not None:
            previous_region = self.get_or_create_region(existing.region_id)
            self._add_to_region(previous_region, -existing.vector)
            dirty_regions.add(previous_region.id)
            object.__setattr__(existing, "vector", vector)
            object.__setattr__(existing, "source", source or existing.source)
            object.__setattr__(existing, "region_id", target_region.id)
            relationship = existing
        else:
            relationship = RelationshipMeta(
                id=relationship_id,
                vector=vector,
                source=source,
                region_id=target_region.id,
            )
            self.relationships[relationship_id] = relationship

        self._add_to_region(target_region, relationship.vector)
        object.__setattr__(relationship, "_managed", True)
        self._record_mutation(
            regions=tuple(dirty_regions),
            relationships=(relationship_id,),
        )
        return relationship

    def remove_source(self, source: str) -> dict[str, int]:
        """Remove every glyph and relationship contributed by one source file."""
        dirty_regions: set[str] = set()
        dirty_glyphs: list[str] = []
        for glyph_id, glyph in list(self.glyphs.items()):
            if glyph.source != source:
                continue
            region = self.get_or_create_region(glyph.region_id)
            self._add_to_region(region, -glyph.vector * glyph.magnitude)
            object.__setattr__(
                region,
                "glyph_count",
                max(0, region.glyph_count - 1),
            )
            dirty_regions.add(region.id)
            dirty_glyphs.append(glyph_id)
            del self.glyphs[glyph_id]

        dirty_relationships: list[str] = []
        for relationship_id, relationship in list(self.relationships.items()):
            if relationship.source != source:
                continue
            region = self.get_or_create_region(relationship.region_id)
            self._add_to_region(region, -relationship.vector)
            dirty_regions.add(region.id)
            dirty_relationships.append(relationship_id)
            del self.relationships[relationship_id]

        if dirty_glyphs or dirty_relationships:
            self._record_mutation(
                regions=tuple(dirty_regions),
                glyphs=tuple(dirty_glyphs),
                relationships=tuple(dirty_relationships),
            )
        return {
            "glyphs": len(dirty_glyphs),
            "relationships": len(dirty_relationships),
        }

    def get_all_glyphs(self) -> list[GlyphMeta]:
        return list(self.glyphs.values())

    def stats(self) -> dict:
        return {
            "dimension": self.dimension,
            "regions": len(self.regions),
            "glyphs": len(self.glyphs),
            "relationships": len(self.relationships),
            "total_capacity": sum(r.capacity for r in self.regions.values()),
        }
