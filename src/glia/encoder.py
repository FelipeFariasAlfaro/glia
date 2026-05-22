"""
GLIA Encoder - Converts text and code identifiers into glyph vectors.

Encoding is DETERMINISTIC — same input always produces same vector.
No AI model calls needed. Pure hashing + random projection.

Improvements over naive bag-of-words:
- Synonym expansion (auth ≈ authentication ≈ login)
- Stemming (generating → generat, authentication → authent)
- Bigrams for phrase-level meaning
- Character trigrams for fuzzy matching
"""

from __future__ import annotations

import hashlib
import re

import numpy as np

from .binding import DIMENSION, bind, normalize, random_vector
from .synonyms import expand_synonyms


def encode_text(text: str, dimension: int = DIMENSION) -> np.ndarray:
    """
    Deterministic encoding of text into a high-dimensional vector.

    Strategy:
    1. Tokenize into words
    2. Expand with synonyms (auth → auth, authentication, login, signin...)
    3. Stem words (authentication → authent)
    4. Each word/stem gets a deterministic random vector (bag-of-words)
    5. Generate bigrams for phrase-level meaning
    6. Character trigrams for fuzzy matching
    7. Normalize to unit length
    """
    tokens = _tokenize(text)
    if not tokens:
        seed = _text_to_seed(text)
        return random_vector(dimension, seed)

    engram = np.zeros(dimension)

    # Expand tokens with synonyms
    expanded = expand_synonyms(tokens)

    # Unigrams (bag of words with synonym expansion)
    seen_seeds = set()
    for token in expanded:
        # Use both the token and its stem
        for variant in [token, _stem(token)]:
            seed = _text_to_seed(variant)
            if seed not in seen_seeds:
                seen_seeds.add(seed)
                word_vector = random_vector(dimension, seed)
                # Original tokens get full weight, synonyms get 0.5
                weight = 1.0 if variant in tokens or token in tokens else 0.5
                engram += word_vector * weight

    # Bigrams from original tokens (not expanded — too noisy)
    for i in range(len(tokens) - 1):
        bigram = f"{tokens[i]}_{tokens[i+1]}"
        seed = _text_to_seed(bigram)
        engram += random_vector(dimension, seed) * 0.5

    # Character trigrams for fuzzy matching
    text_lower = "".join(tokens)
    for i in range(len(text_lower) - 2):
        trigram = text_lower[i:i+3]
        if trigram.isalpha():
            seed = _text_to_seed(f"_tri_{trigram}")
            engram += random_vector(dimension, seed) * 0.08

    return normalize(engram)


def encode_identifier(name: str, context: str = "", dimension: int = DIMENSION) -> np.ndarray:
    """
    Deterministic encoding of a code identifier.
    Splits camelCase and snake_case into words and encodes as text.
    """
    words = _split_identifier(name)
    if context:
        context_words = _split_identifier(context)
        words = context_words + words
    text = " ".join(words)
    return encode_text(text, dimension)


def encode_relationship(source: str, target: str, rel_type: str, dimension: int = DIMENSION) -> np.ndarray:
    """Encode a structural relationship using the binding operator."""
    source_vec = encode_text(source, dimension)
    target_vec = encode_text(target, dimension)
    role_vec = encode_text(rel_type, dimension)
    return bind(bind(source_vec, role_vec), target_vec)


def _stem(word: str) -> str:
    """
    Simple suffix-stripping stemmer.
    Reduces words to approximate roots without external libraries.
    """
    if len(word) <= 4:
        return word

    # Common suffixes to strip
    suffixes = [
        "ation", "tion", "sion", "ment", "ness", "ence", "ance",
        "able", "ible", "ful", "less", "ous", "ive", "ing",
        "ated", "ized", "ised", "ting", "ted", "ied", "ies",
        "ers", "est", "ity", "ism", "ist", "ent", "ant",
        "ion", "ory", "ary", "ery", "ure", "age",
        "ly", "ed", "er", "es", "al", "ic",
    ]

    for suffix in suffixes:
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[:-len(suffix)]

    return word


def _split_identifier(name: str) -> list[str]:
    """Split camelCase and snake_case into words."""
    parts = name.replace("-", "_").split("_")
    words = []
    for part in parts:
        sub = re.sub(r'([A-Z])', r' \1', part).split()
        words.extend(w.lower() for w in sub if len(w) >= 2)
    return words


def _tokenize(text: str) -> list[str]:
    """Tokenize: split on non-alphanumeric, lowercase, filter short."""
    tokens = re.split(r'[^a-zA-Z0-9]+', text.lower())
    return [t for t in tokens if len(t) >= 2]


def _text_to_seed(text: str) -> int:
    """Convert text to a deterministic integer seed via SHA-256."""
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return int(h[:16], 16)
