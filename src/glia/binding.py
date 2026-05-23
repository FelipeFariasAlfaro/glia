"""
GLIA Binding Operations - Circular convolution for holographic encoding.

The binding operator is the mathematical heart of GLIA v2.
It combines two vectors into a composite that:
- Is dissimilar to both inputs
- Can be approximately inverted (unbind)
- Distributes over addition

This enables encoding relationships WITHOUT explicit edges.
"""

from __future__ import annotations

import numpy as np

DIMENSION = 1024


def bind(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """
    Circular convolution — the holographic binding operator.

    Properties:
    - bind(a, b) is dissimilar to both a and b
    - bind is commutative: bind(a,b) ≈ bind(b,a)
    - Has an approximate inverse: unbind(bind(a,b), a) ≈ b
    - Distributes over addition: bind(a, b+c) = bind(a,b) + bind(a,c)
    """
    return np.real(np.fft.ifft(np.fft.fft(a) * np.fft.fft(b)))


def unbind(composite: np.ndarray, key: np.ndarray) -> np.ndarray:
    """
    Approximate inverse of bind using correlation (inverse convolution).
    unbind(bind(a, b), a) ≈ b
    """
    key_inv = involution(key)
    return bind(composite, key_inv)


def involution(v: np.ndarray) -> np.ndarray:
    """Compute the involution of a vector (for circular correlation)."""
    return np.roll(np.flip(v), 1)


def normalize(v: np.ndarray) -> np.ndarray:
    """Normalize vector to unit length."""
    norm = np.linalg.norm(v)
    if norm < 1e-10:
        return v
    return v / norm


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def random_vector(dimension: int = DIMENSION, seed: int | None = None) -> np.ndarray:
    """Generate a random unit vector (deterministic if seed provided)."""
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(dimension)
    return normalize(v)
