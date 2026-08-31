"""Pattern projection and bounded holographic unbinding for GLIA."""

from __future__ import annotations

import re

import numpy as np

from .binding import normalize, unbind
from .encoder import encode_text
from .substrate import GlyphMeta, ResonanceSnapshot, Substrate

MIN_RESONANCE = 0.05


class _ResonanceIndex:
    """Vectorized view of active glyphs, optionally backed by a cached snapshot."""

    def __init__(
        self,
        glyphs: list[GlyphMeta] | None = None,
        snapshot: ResonanceSnapshot | None = None,
    ):
        if snapshot is not None:
            self.glyphs = snapshot.glyphs
            self.vectors = snapshot.vectors
            self.scales = snapshot.scales
            return

        active = tuple(glyph for glyph in (glyphs or []) if glyph.magnitude > 0)
        self.glyphs = active
        if not active:
            self.vectors = np.empty((0, 0), dtype=np.float64)
            self.scales = np.empty(0, dtype=np.float64)
            return
        self.vectors = np.stack([glyph.vector for glyph in active])
        norms = np.linalg.norm(self.vectors, axis=1)
        magnitudes = np.asarray(
            [glyph.magnitude for glyph in active], dtype=np.float64
        )
        self.scales = np.divide(
            magnitudes,
            norms,
            out=np.zeros_like(magnitudes),
            where=norms > 1e-12,
        )

    @classmethod
    def from_substrate(cls, substrate: Substrate) -> "_ResonanceIndex":
        return cls(snapshot=substrate.resonance_snapshot())

    def query(
        self,
        stimulus: np.ndarray,
        top_k: int,
        minimum: float = MIN_RESONANCE,
    ) -> list[tuple[GlyphMeta, float]]:
        if not self.glyphs or top_k <= 0:
            return []
        stimulus = np.asarray(stimulus, dtype=np.float64)
        stimulus_norm = float(np.linalg.norm(stimulus))
        if stimulus_norm <= 1e-12:
            return []
        scores = (self.vectors @ stimulus) * self.scales / stimulus_norm
        candidates = np.flatnonzero(scores > minimum)
        if not candidates.size:
            return []
        ordered = candidates[np.argsort(scores[candidates])[::-1]][:top_k]
        return [(self.glyphs[index], float(scores[index])) for index in ordered]


def resonate(
    stimulus: np.ndarray,
    glyphs: list[GlyphMeta],
    top_k: int = 10,
) -> list[tuple[GlyphMeta, float]]:
    """Project a stimulus against active glyphs using vectorized cosine scoring."""
    return _ResonanceIndex(glyphs=glyphs).query(stimulus, top_k=top_k)


def resonate_multihop(
    stimulus: np.ndarray,
    glyphs: list[GlyphMeta],
    substrate: Substrate | None = None,
    hops: int = 3,
    top_k: int = 10,
    _index: _ResonanceIndex | None = None,
) -> list[tuple[GlyphMeta, float]]:
    """Retrieve direct matches and add bounded unbinding evidence.

    Direct resonance is computed once and remains the ranking anchor. Each
    additional hop may add a small association bonus, but never repeatedly
    re-adds the same direct score. This prevents the query drift present in the
    earlier iterative-superposition implementation.
    """
    if hops < 1 or top_k < 1:
        return []

    if _index is not None:
        index = _index
    elif substrate is not None and len(glyphs) == len(substrate.glyphs) and all(
        substrate.glyphs.get(glyph.id) is glyph for glyph in glyphs
    ):
        index = _ResonanceIndex.from_substrate(substrate)
    else:
        index = _ResonanceIndex(glyphs=glyphs)
    direct = index.query(stimulus, top_k=max(top_k * 3, 15))
    if not direct:
        return []

    scores: dict[str, tuple[GlyphMeta, float]] = {
        glyph.id: (glyph, score) for glyph, score in direct
    }
    frontier = direct[:3]

    if substrate is not None:
        for hop in range(1, hops):
            strength = 0.18 * (0.5 ** (hop - 1))
            discovered: dict[str, tuple[GlyphMeta, float]] = {}
            for glyph, _ in frontier:
                region = substrate.regions.get(glyph.region_id)
                if region is None:
                    continue
                associated = normalize(unbind(region.vector, glyph.vector))
                for candidate, association_score in index.query(associated, top_k=5):
                    if candidate.id == glyph.id:
                        continue
                    bonus = association_score * strength
                    current = scores.get(candidate.id)
                    if current is None:
                        scores[candidate.id] = (candidate, bonus)
                    else:
                        bounded_bonus = min(bonus, max(current[1] * 0.10, 0.01))
                        scores[candidate.id] = (candidate, current[1] + bounded_bonus)
                    previous = discovered.get(candidate.id)
                    if previous is None or bonus > previous[1]:
                        discovered[candidate.id] = (candidate, bonus)
            frontier = sorted(
                discovered.values(), key=lambda item: item[1], reverse=True
            )[:3]
            if not frontier:
                break

    return sorted(scores.values(), key=lambda item: item[1], reverse=True)[:top_k]


def resonate_conjunctive(
    stimuli: list[np.ndarray],
    glyphs: list[GlyphMeta],
    top_k: int = 10,
) -> list[tuple[GlyphMeta, float]]:
    """Find patterns related to all stimuli simultaneously."""
    if not stimuli:
        return []
    return resonate(normalize(np.sum(stimuli, axis=0)), glyphs, top_k=top_k)


def _words(text: str) -> set[str]:
    return {
        word
        for word in re.split(r"[^a-z0-9]+", text.lower())
        if len(word) >= 2
    }


def _diverse_results(
    results: list[tuple[GlyphMeta, float]],
    top_k: int,
) -> list[tuple[GlyphMeta, float]]:
    """Prefer distinct sources while retaining source-less manual memories."""
    diverse: list[tuple[GlyphMeta, float]] = []
    seen: set[str] = set()
    for glyph, score in results:
        key = glyph.source or glyph.id
        if key in seen:
            continue
        seen.add(key)
        diverse.append((glyph, score))
        if len(diverse) >= top_k:
            break
    return diverse


def resolve_query(
    query: str,
    substrate: Substrate,
    top_k: int = 10,
    hops: int = 3,
    embedder=None,
    explore: bool = False,
) -> list[tuple[GlyphMeta, float]]:
    """Resolve text through stable HDM retrieval or explicit exploration."""
    if not substrate.glyphs or top_k < 1:
        return []

    stimulus = None
    if embedder and embedder.is_available:
        stimulus = embedder.embed(query)
    if stimulus is None:
        stimulus = encode_text(query)

    index = _ResonanceIndex.from_substrate(substrate)
    glyphs = list(index.glyphs)
    candidate_count = max(top_k * 4, 20)
    direct = index.query(stimulus, top_k=candidate_count)
    direct_diverse = _diverse_results(direct, top_k)
    if len(direct_diverse) >= top_k and not explore:
        return direct_diverse
    holographic = (
        resonate_multihop(
            stimulus,
            glyphs,
            substrate=substrate,
            hops=hops,
            top_k=candidate_count,
            _index=index,
        )
        if explore
        else []
    )

    lexical: list[tuple[GlyphMeta, float]] = []
    query_words = _words(query)
    if query_words:
        for glyph in glyphs:
            glyph_words = _words(f"{glyph.id} {glyph.content} {glyph.source}")
            overlap = len(query_words & glyph_words)
            if overlap:
                lexical.append(
                    (glyph, overlap / len(query_words) * min(glyph.magnitude, 2.0))
                )
        lexical.sort(key=lambda item: item[1], reverse=True)

    if explore:
        keep = max(1, int(top_k * 0.8))
        combined = list(direct_diverse[:keep])
        direct_ids = {glyph.id for glyph, _ in direct}
        novel_associations = [
            item for item in holographic if item[0].id not in direct_ids
        ]
        candidate_groups = (novel_associations, holographic, lexical, direct)
    else:
        combined = list(direct_diverse)
        candidate_groups = (holographic, lexical, direct)

    seen = {glyph.source or glyph.id for glyph, _ in combined}
    for candidates in candidate_groups:
        for glyph, score in candidates:
            key = glyph.source or glyph.id
            if key in seen:
                continue
            combined.append((glyph, score))
            seen.add(key)
            if len(combined) >= top_k:
                return combined
    return combined
