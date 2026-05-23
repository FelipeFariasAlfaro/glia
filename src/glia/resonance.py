"""
GLIA Resonance Engine - Retrieval by pattern projection + holographic unbinding.

Multi-hop works by:
1. Initial resonance (find directly matching patterns)
2. Holographic unbinding (discover implicit associations from substrate)
3. Iterative expansion (use discovered associations as new stimuli)
4. Word-overlap fallback (catch remaining matches)

This is what RAG CANNOT do: discover relationships that were encoded
holographically in the substrate via binding, even when the concepts
don't share any vocabulary.
"""

from __future__ import annotations

import re

import numpy as np

from .binding import cosine_similarity, normalize, unbind, bind, DIMENSION
from .substrate import Substrate, GlyphMeta
from .encoder import encode_text

MIN_RESONANCE = 0.05


def resonate(stimulus: np.ndarray, glyphs: list[GlyphMeta], top_k: int = 10) -> list[tuple[GlyphMeta, float]]:
    """Project stimulus and find resonating patterns (parallel)."""
    scores = []
    for glyph in glyphs:
        if glyph.magnitude <= 0:
            continue
        sim = cosine_similarity(stimulus, glyph.vector)
        score = sim * glyph.magnitude
        if score > MIN_RESONANCE:
            scores.append((glyph, score))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def resonate_multihop(
    stimulus: np.ndarray,
    glyphs: list[GlyphMeta],
    substrate: Substrate | None = None,
    hops: int = 3,
    top_k: int = 10,
) -> list[tuple[GlyphMeta, float]]:
    """
    Multi-hop resonance with holographic unbinding.

    Hop 1: Direct resonance (like RAG)
    Hop 2: Unbind top results from substrate to discover implicit associations
    Hop 3: Use discovered associations as new stimuli

    The unbinding step is what makes this fundamentally different from RAG.
    It discovers relationships that were encoded holographically — even when
    the concepts don't share vocabulary.
    """
    all_results: dict[str, tuple[GlyphMeta, float]] = {}
    current_stimulus = stimulus

    for hop in range(hops):
        # Standard resonance pass
        results = resonate(current_stimulus, glyphs, top_k=top_k)
        decay = 0.7 ** hop  # Less aggressive decay for more hops
        for glyph, score in results:
            existing_score = all_results.get(glyph.id, (None, 0.0))[1]
            new_score = existing_score + score * decay
            all_results[glyph.id] = (glyph, new_score)

        if not results:
            break

        # --- HOLOGRAPHIC UNBINDING (the multi-hop secret) ---
        # Try to discover implicit associations by unbinding top results
        # from the substrate region vector
        if substrate and hop < hops - 1:
            region = substrate.get_or_create_region("default")
            for glyph, _ in results[:3]:
                # Unbind this glyph from the substrate to see what's associated
                # If bind(A, B) was stored in substrate, unbind(substrate, A) ≈ B
                associated = unbind(region.vector, glyph.vector)
                associated_normalized = normalize(associated)

                # Find what this "ghost" vector resonates with
                ghost_results = resonate(associated_normalized, glyphs, top_k=5)
                for ghost_glyph, ghost_score in ghost_results:
                    if ghost_glyph.id != glyph.id:
                        # Discovered association! Add with reduced weight
                        existing = all_results.get(ghost_glyph.id, (None, 0.0))[1]
                        bonus = ghost_score * 0.3 * decay
                        all_results[ghost_glyph.id] = (ghost_glyph, existing + bonus)

        # Build next stimulus from top results (superposition)
        top_vectors = [g.vector for g, _ in results[:5]]
        if top_vectors:
            current_stimulus = normalize(np.sum(top_vectors, axis=0))

    final = sorted(all_results.values(), key=lambda x: x[1], reverse=True)
    return final[:top_k]


def resonate_conjunctive(stimuli: list[np.ndarray], glyphs: list[GlyphMeta], top_k: int = 10) -> list[tuple[GlyphMeta, float]]:
    """Find patterns related to ALL stimuli simultaneously."""
    if not stimuli:
        return []
    combined = normalize(np.sum(stimuli, axis=0))
    return resonate(combined, glyphs, top_k=top_k)


def resolve_query(
    query: str,
    substrate: Substrate,
    top_k: int = 10,
    hops: int = 3,
    embedder=None,
) -> list[tuple[GlyphMeta, float]]:
    """Full pipeline: text → encode → resonate (with unbinding) → results."""
    glyphs = substrate.get_all_glyphs()
    if not glyphs:
        return []

    # Try enhanced embedding for query
    stimulus = None
    if embedder and embedder.is_available:
        stimulus = embedder.embed(query)

    # Fallback to local encoding
    if stimulus is None:
        stimulus = encode_text(query)

    # Multi-hop resonance WITH holographic unbinding
    results = resonate_multihop(
        stimulus, glyphs, substrate=substrate, hops=hops, top_k=top_k
    )

    # Word-overlap fallback for remaining matches
    query_words = set(re.split(r'[^a-z0-9]+', query.lower()))
    query_words = {w for w in query_words if len(w) >= 2}

    existing_ids = {g.id for g, _ in results}
    word_matches = []

    for glyph in glyphs:
        if glyph.id in existing_ids:
            continue
        glyph_text = f"{glyph.id} {glyph.content}".lower()
        glyph_words = set(re.split(r'[^a-z0-9]+', glyph_text))

        overlap = len(query_words & glyph_words)
        if overlap > 0:
            score = (overlap / max(len(query_words), 1)) * 0.3 * glyph.magnitude
            word_matches.append((glyph, score))

    word_matches.sort(key=lambda x: x[1], reverse=True)

    combined = list(results)
    for glyph, score in word_matches[:top_k]:
        if glyph.id not in existing_ids:
            combined.append((glyph, score))
            existing_ids.add(glyph.id)

    combined.sort(key=lambda x: x[1], reverse=True)
    return combined[:top_k]
