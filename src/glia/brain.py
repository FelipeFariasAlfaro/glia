"""
GLIA Brain v2 - Holographic Distributed Memory orchestrator.

This is NOT a graph. Knowledge is stored as distributed patterns
in a high-dimensional vector space. Retrieval works by resonance
(pattern projection), not by edge traversal.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .substrate import Substrate, GlyphMeta
from .encoder import encode_text, encode_identifier, encode_relationship
from .resonance import resolve_query, resonate, resonate_multihop
from .plasticity import reinforce, decay_all, co_activate
from .cognitive_map import build_cognitive_map
from .storage import SQLiteStorage
from .binding import DIMENSION, cosine_similarity, normalize

import numpy as np

GLIA_DIR = ".glia"
CONFIG_FILE = "config.json"


class GliaBrain:
    """
    The GLIA v2 engine — Holographic Distributed Memory.

    No graphs. No edges. Knowledge as distributed patterns.
    Retrieval by resonance. Plasticity by reinforcement and decay.
    """

    def __init__(
        self,
        workspace: Optional[Path] = None,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        provider: str = "gemini",
    ):
        self.workspace = workspace or Path.cwd()
        self.glia_path = self.workspace / GLIA_DIR
        self.substrate = Substrate(dimension=DIMENSION)
        self._storage: Optional[SQLiteStorage] = None
        self._loaded = False
        self.api_key = api_key
        self.model = model
        self.provider = provider

    @property
    def is_initialized(self) -> bool:
        return self.glia_path.exists()

    def init(self) -> None:
        self.glia_path.mkdir(parents=True, exist_ok=True)
        config = {
            "version": "2.0.0",
            "dimension": DIMENSION,
            "decay_rate": 0.01,
            "min_resonance": 0.05,
        }
        config_path = self.glia_path / CONFIG_FILE
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self.save()

    def load(self) -> None:
        if self._loaded:
            return
        self._storage = SQLiteStorage(self.glia_path)
        self.substrate = self._storage.load_substrate()
        self._loaded = True

    def save(self) -> None:
        self.glia_path.mkdir(parents=True, exist_ok=True)
        if self._storage is None:
            self._storage = SQLiteStorage(self.glia_path)
        self._storage.save_substrate(self.substrate)

    def learn(self, content: str, source: str = "") -> dict:
        self.load()
        from .distiller import Distiller
        distiller = Distiller(api_key=self.api_key, model=self.model, provider=self.provider)
        result = distiller.distill(content, self.substrate, source)
        self.save()
        return result

    def learn_offline(
        self,
        content: str,
        concepts: list[str],
        relationships: list[dict],
        summary: str,
        source: str = "",
    ) -> dict:
        self.load()
        for concept in concepts:
            vector = encode_identifier(concept)
            self.substrate.store_glyph(
                glyph_id=concept, vector=vector, content=summary, source=source,
            )
        for rel in relationships:
            src = rel.get("source", "")
            tgt = rel.get("target", "")
            if src and tgt:
                rel_vector = encode_relationship(src, tgt, "related")
                self.substrate.store_relationship(rel_vector)
        self.save()
        return {"concepts": concepts, "relationships": relationships, "summary": summary}

    def recall(self, query: str | list[str], top_k: int = 10) -> dict:
        self.load()
        if isinstance(query, list):
            query_text = " ".join(query)
        else:
            query_text = query

        # Use embeddings for query if available
        from .embeddings import GliaEmbedder
        embedder = GliaEmbedder(api_key=self.api_key)

        results = resolve_query(
            query_text, self.substrate, top_k=top_k,
            embedder=embedder if embedder.is_available else None,
        )

        for glyph, score in results:
            reinforce(glyph, amount=0.02)

        if len(results) >= 2:
            top_glyphs = [g for g, _ in results[:3]]
            for i in range(len(top_glyphs) - 1):
                co_activate(self.substrate, top_glyphs[i], top_glyphs[i + 1], strength=0.02)

        sources = list(set(g.source for g, _ in results if g.source))
        context = build_cognitive_map(query=query_text, results=results, sources=sources)

        self.save()
        return {
            "activated_nodes": [(g.id, s) for g, s in results],
            "threads": [
                {"id": g.id, "content": g.content, "score": s, "source": g.source}
                for g, s in results
            ],
            "context": context,
        }

    def forget(self, decay_rate: float = 0.01) -> dict:
        self.load()
        glyphs = self.substrate.get_all_glyphs()
        before_count = len([g for g in glyphs if g.magnitude > 0])
        forgotten = decay_all(glyphs, rate=decay_rate)
        after_count = before_count - forgotten
        self.save()
        return {"edges_before": before_count, "edges_after": after_count, "pruned": forgotten}

    def stats(self) -> dict:
        self.load()
        s = self.substrate.stats()
        return {
            "nodes": s["glyphs"],
            "edges": 0,
            "avg_connections": 0,
            "threads": s["glyphs"],
            "dimension": s["dimension"],
            "regions": s["regions"],
        }
