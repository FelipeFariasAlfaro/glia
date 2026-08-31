"""Convert raw information into deterministic holographic contributions."""

from __future__ import annotations

import hashlib
import json
from typing import Optional

try:
    from google import genai
except ImportError:
    genai = None

from .encoder import encode_relationship, encode_text
from .substrate import Substrate

DISTILL_PROMPT = """You are GLIA, a neural memory indexer. Analyze the following content and extract semantic units.

For EACH semantic unit, extract:
1. A concept ID (snake_case, 2-4 words, specific)
2. A one-sentence description of its INTENTION (max 30 words)
3. Related concepts (from this content or known concepts)

Previously known concepts: {known_nodes}

Content from: {source}
---
{content}
---

Respond ONLY with valid JSON:
{{
  "units": [
    {{
      "concept": "concept_id",
      "intention": "One sentence: what this unit DOES or MEANS",
      "relationships": [
        {{"target": "other_concept", "weight": 0.8}}
      ]
    }}
  ]
}}"""


class Distiller:
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-3.1-flash-lite-preview",
    ):
        self.model_name = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            if genai is None:
                raise ImportError("google-genai is required")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def extract(self, content: str, substrate: Substrate, source: str = "") -> dict:
        """Call the external model once and return validated, unapplied units."""
        known = list(substrate.glyphs.keys())[:150]
        prompt = DISTILL_PROMPT.format(
            known_nodes=", ".join(known) if known else "(empty)",
            content=content[:6000],
            source=source or "unknown",
        )
        response = self._get_client().models.generate_content(
            model=self.model_name,
            contents=prompt,
        )
        return self._parse_response(response.text)

    def apply(self, result: dict, substrate: Substrate, source: str = "") -> dict:
        """Deterministically apply previously extracted units to a substrate."""
        concepts = []
        relationships = []
        for unit in result.get("units", []):
            concept = unit.get("concept", "")
            intention = unit.get("intention", "")
            if not concept:
                continue
            substrate.store_glyph(
                glyph_id=concept,
                vector=encode_text(f"{concept} {intention}"),
                content=intention,
                source=source,
            )
            concepts.append(concept)

            for relationship in unit.get("relationships", []):
                target = relationship.get("target", "")
                if not target:
                    continue
                identity = "|".join((source, concept, target, "related"))
                relationship_id = (
                    "distill:"
                    + hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
                )
                substrate.store_relationship(
                    encode_relationship(concept, target, "related"),
                    relationship_id=relationship_id,
                    source=source,
                )
                relationships.append(
                    {
                        "source": concept,
                        "target": target,
                        "weight": relationship.get("weight", 0.5),
                    }
                )

        return {
            "concepts": concepts,
            "relationships": relationships,
            "summary": f"Extracted {len(concepts)} glyphs from {source}",
            "units": result.get("units", []),
        }

    def distill(self, content: str, substrate: Substrate, source: str = "") -> dict:
        """Backward-compatible one-shot extraction and application."""
        return self.apply(
            self.extract(content, substrate, source),
            substrate,
            source,
        )

    def _parse_response(self, text: str) -> dict:
        cleaned = text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("{")
            end = cleaned.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(cleaned[start:end])
                except json.JSONDecodeError:
                    pass
            return {"units": []}
