"""
GLIA Embeddings - Optional enhanced encoding using real embedding models.

When an API key is available, GLIA can use Gemini (or other providers)
to generate real semantic embeddings instead of hash projection.

This is OPTIONAL. Without it, GLIA uses the local encoder (free, offline).
With it, GLIA gets near-RAG precision + all the unique GLIA capabilities.

Usage:
    embedder = GliaEmbedder(api_key="...", provider="gemini")
    vector = embedder.embed("authentication module for JWT tokens")
"""

from __future__ import annotations

import os
import time
import hashlib
from typing import Optional

import numpy as np

from .binding import DIMENSION, normalize


class GliaEmbedder:
    """
    Optional embedding provider for enhanced precision.
    Falls back to local encoding if no API key is available.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        provider: str = "gemini",
        model: str = "gemini-embedding-001",
        dimension: int = DIMENSION,
    ):
        self.api_key = api_key
        self.provider = provider
        self.model = model
        self.dimension = dimension
        self._client = None
        self._cache: dict[str, np.ndarray] = {}

    @property
    def is_available(self) -> bool:
        """Check if enhanced embeddings are available."""
        return self.api_key is not None and len(self.api_key) > 0

    def embed(self, text: str) -> Optional[np.ndarray]:
        """
        Embed text using the configured provider.
        Returns None if not available (caller should fall back to local).
        """
        if not self.is_available:
            return None

        # Check cache
        cache_key = hashlib.md5(text[:500].encode()).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            vector = self._embed_gemini(text)
            if vector is not None:
                # Resize to GLIA dimension if needed
                if len(vector) != self.dimension:
                    vector = self._resize_vector(vector, self.dimension)
                self._cache[cache_key] = vector
                return vector
        except Exception:
            pass

        return None

    def embed_batch(self, texts: list[str]) -> list[Optional[np.ndarray]]:
        """Embed multiple texts in batch (more efficient)."""
        if not self.is_available:
            return [None] * len(texts)

        results = []
        # Process in batches of 20
        for i in range(0, len(texts), 20):
            batch = texts[i:i + 20]
            batch_results = self._embed_gemini_batch(batch)
            results.extend(batch_results)
            if i + 20 < len(texts):
                time.sleep(0.3)  # Rate limiting

        return results

    def _embed_gemini(self, text: str) -> Optional[np.ndarray]:
        """Embed using Gemini API."""
        client = self._get_client()
        if client is None:
            return None

        result = client.models.embed_content(
            model=self.model,
            contents=[text[:2000],],  # Limit input size
        )
        if result.embeddings:
            return np.array(result.embeddings[0].values, dtype=np.float64)
        return None

    def _embed_gemini_batch(self, texts: list[str]) -> list[Optional[np.ndarray]]:
        """Batch embed using Gemini API."""
        client = self._get_client()
        if client is None:
            return [None] * len(texts)

        try:
            truncated = [t[:2000] for t in texts]
            result = client.models.embed_content(
                model=self.model,
                contents=truncated,
            )
            vectors = []
            for emb in result.embeddings:
                v = np.array(emb.values, dtype=np.float64)
                if len(v) != self.dimension:
                    v = self._resize_vector(v, self.dimension)
                vectors.append(v)
            return vectors
        except Exception:
            return [None] * len(texts)

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                return None
        return self._client

    def _resize_vector(self, vector: np.ndarray, target_dim: int) -> np.ndarray:
        """Resize vector to target dimension (pad or truncate)."""
        if len(vector) == target_dim:
            return vector
        elif len(vector) > target_dim:
            return normalize(vector[:target_dim])
        else:
            padded = np.zeros(target_dim)
            padded[:len(vector)] = vector
            return normalize(padded)
