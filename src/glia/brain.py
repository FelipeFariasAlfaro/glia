"""GLIA Brain v2 — Holographic Distributed Memory orchestrator.

Knowledge is stored as distributed patterns in a high-dimensional vector
space. Retrieval works by resonance, not by graph traversal.
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
import uuid
from functools import wraps
from pathlib import Path
from typing import Callable, Optional, TypeVar

from .binding import DIMENSION
from .cognitive_map import build_cognitive_map
from .encoder import encode_identifier, encode_relationship
from .plasticity import co_activate, decay_all, reinforce
from .resonance import resolve_query
from .storage import SQLiteStorage, StorageConflictError
from .substrate import Substrate

GLIA_DIR = ".glia"
CONFIG_FILE = "config.json"
MUTATION_RETRIES = 8

ResultT = TypeVar("ResultT")


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


class GliaBrain:
    """Thread-safe orchestrator for GLIA's holographic memory."""

    def __init__(
        self,
        workspace: Optional[Path] = None,
        api_key: Optional[str] = None,
        model: str = "gemini-3.1-flash-lite-preview",
    ):
        self.workspace = workspace or Path.cwd()
        self.glia_path = self.workspace / GLIA_DIR
        self.substrate = Substrate(dimension=DIMENSION)
        self._storage: Optional[SQLiteStorage] = None
        self._loaded = False
        self._revision: Optional[int] = None
        self._lock = threading.RLock()
        self.api_key = api_key
        self.model = model

    def __enter__(self) -> "GliaBrain":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @property
    def is_initialized(self) -> bool:
        return self.glia_path.exists()

    @property
    def lock(self):
        """Reentrant lock used by compound scanner and memory operations."""
        return self._lock

    @_synchronized
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

    @_synchronized
    def close(self) -> None:
        if self._storage is not None:
            self._storage.close()
            self._storage = None
        self._loaded = False
        self._revision = None

    @_synchronized
    def load(self, force: bool = False) -> None:
        if self._loaded and not force:
            return
        if self._storage is None:
            self._storage = SQLiteStorage(self.glia_path)
        self.substrate, self._revision = self._storage.load_substrate_versioned()
        self._loaded = True

    @_synchronized
    def save(
        self,
        scan_state_updates: dict | None = None,
        scan_state_deletes: set[str] | None = None,
    ) -> None:
        self.glia_path.mkdir(parents=True, exist_ok=True)
        if not self._loaded:
            self.load()
        assert self._storage is not None
        assert self._revision is not None
        self._revision = self._storage.save_substrate(
            self.substrate,
            expected_revision=self._revision,
            scan_state_updates=scan_state_updates,
            scan_state_deletes=scan_state_deletes,
        )

    def _commit_mutation(
        self,
        mutation: Callable[[Substrate], ResultT],
        attempts: int = MUTATION_RETRIES,
    ) -> ResultT:
        """Reload, reapply and retry a complete mutation after stale revisions.

        Any failed mutation is discarded by reloading the last committed snapshot,
        so callers never retain a partially applied in-memory state.
        """
        if attempts < 1:
            raise ValueError("attempts must be at least 1")

        last_conflict: StorageConflictError | None = None
        for attempt in range(attempts):
            self.load(force=attempt > 0)
            try:
                result = mutation(self.substrate)
                self.save()
                return result
            except StorageConflictError as error:
                last_conflict = error
                self.load(force=True)
                if attempt == attempts - 1:
                    raise
                time.sleep(min(0.002 * (2 ** attempt), 0.05))
            except Exception:
                self.load(force=True)
                raise

        assert last_conflict is not None
        raise last_conflict

    @_synchronized
    def load_scan_state(self) -> dict:
        self.load()
        assert self._storage is not None
        return self._storage.load_scan_state()

    @_synchronized
    def save_scan_state(self, state: dict) -> None:
        self.load()
        assert self._storage is not None
        self._storage.save_scan_state(state)

    @_synchronized
    def learn(self, content: str, source: str = "") -> dict:
        from .distiller import Distiller

        distiller = Distiller(api_key=self.api_key, model=self.model)
        self.load()
        extracted = distiller.extract(content, self.substrate, source)
        return self._commit_mutation(
            lambda substrate: distiller.apply(extracted, substrate, source)
        )

    @_synchronized
    def learn_offline(
        self,
        content: str,
        concepts: list[str],
        relationships: list[dict],
        summary: str,
        source: str = "",
    ) -> dict:
        def apply(substrate: Substrate) -> dict:
            for concept in concepts:
                substrate.store_glyph(
                    glyph_id=concept,
                    vector=encode_identifier(concept),
                    content=summary,
                    source=source,
                )
            for relationship in relationships:
                source_id = relationship.get("source", "")
                target_id = relationship.get("target", "")
                if not source_id or not target_id:
                    continue
                identity = "|".join((source, source_id, target_id, "related"))
                relationship_id = (
                    "learn:" + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
                )
                substrate.store_relationship(
                    encode_relationship(source_id, target_id, "related"),
                    relationship_id=relationship_id,
                    source=source,
                )
            return {
                "concepts": concepts,
                "relationships": relationships,
                "summary": summary,
            }

        return self._commit_mutation(apply)

    def _resolve_recall(
        self,
        substrate: Substrate,
        query_text: str,
        top_k: int,
        adapt: bool,
        explore: bool,
    ) -> dict:
        from .embeddings import GliaEmbedder

        embedder = GliaEmbedder(api_key=self.api_key)
        results = resolve_query(
            query_text,
            substrate,
            top_k=top_k,
            embedder=embedder if embedder.is_available else None,
            explore=explore,
        )

        if adapt:
            for glyph, _ in results:
                reinforce(glyph, amount=0.02, substrate=substrate)
            by_region: dict[str, list] = {}
            for glyph, _ in results[:3]:
                by_region.setdefault(glyph.region_id, []).append(glyph)
            for region_glyphs in by_region.values():
                for first, second in zip(region_glyphs, region_glyphs[1:]):
                    co_activate(substrate, first, second, strength=0.02)

        sources = sorted({glyph.source for glyph, _ in results if glyph.source})
        context = build_cognitive_map(
            query=query_text,
            results=results,
            sources=sources,
        )
        return {
            "activated_nodes": [(glyph.id, score) for glyph, score in results],
            "threads": [
                {
                    "id": glyph.id,
                    "content": glyph.content,
                    "score": score,
                    "source": glyph.source,
                }
                for glyph, score in results
            ],
            "context": context,
            "adapted": adapt,
            "explored": explore,
        }

    @_synchronized
    def recall(
        self,
        query: str | list[str],
        top_k: int = 10,
        adapt: bool = False,
        explore: bool = False,
    ) -> dict:
        """Retrieve by resonance; optionally explore and persist plasticity."""
        if top_k < 1:
            raise ValueError("top_k must be at least 1")
        query_text = " ".join(query) if isinstance(query, list) else query
        if adapt:
            return self._commit_mutation(
                lambda substrate: self._resolve_recall(
                    substrate, query_text, top_k, adapt=True, explore=explore
                )
            )

        self.load()
        return self._resolve_recall(
            self.substrate,
            query_text,
            top_k,
            adapt=False,
            explore=explore,
        )

    @_synchronized
    def forget(self, decay_rate: float = 0.01) -> dict:
        if decay_rate < 0:
            raise ValueError("decay_rate must be non-negative")

        def apply(substrate: Substrate) -> dict:
            glyphs = substrate.get_all_glyphs()
            before_count = sum(glyph.magnitude > 0 for glyph in glyphs)
            forgotten = decay_all(
                glyphs,
                rate=decay_rate,
                substrate=substrate,
            )
            return {
                "edges_before": before_count,
                "edges_after": before_count - forgotten,
                "pruned": forgotten,
            }

        return self._commit_mutation(apply)

    @_synchronized
    def health(self, deep: bool = False) -> dict:
        self.load()
        assert self._storage is not None
        return self._storage.health_check(deep=deep)

    @_synchronized
    def backup(self, destination: Path | None = None) -> Path:
        self.load()
        assert self._storage is not None
        if destination is None:
            stamp = time.strftime("%Y%m%d-%H%M%S")
            stamp = f"{stamp}-{uuid.uuid4().hex}"
            destination = self.glia_path / "backups" / f"memory-{stamp}.db"
        return self._storage.backup(destination)

    @_synchronized
    def stats(self) -> dict:
        self.load()
        substrate_stats = self.substrate.stats()
        return {
            "nodes": substrate_stats["glyphs"],
            "edges": 0,
            "avg_connections": 0,
            "threads": substrate_stats["glyphs"],
            "relationships": substrate_stats["relationships"],
            "dimension": substrate_stats["dimension"],
            "regions": substrate_stats["regions"],
            "revision": self._revision,
        }
