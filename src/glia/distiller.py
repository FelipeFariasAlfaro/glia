"""
GLIA Distiller v2 - Converts raw information into glyphs for the substrate.
"""

from __future__ import annotations

import json
import hashlib
from typing import Optional

try:
    from google import genai
except ImportError:
    genai = None

from .substrate import Substrate
from .encoder import encode_text, encode_relationship

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
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.1-flash-lite-preview"):
        self.model_name = model
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            if genai is None:
                raise ImportError("google-genai is required")
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def distill(self, content: str, substrate: Substrate, source: str = "") -> dict:
        known = list(substrate.glyphs.keys())[:150]
        known_str = ", ".join(known) if known else "(empty)"

        prompt = DISTILL_PROMPT.format(known_nodes=known_str, content=content[:6000], source=source or "unknown")
        client = self._get_client()
        response = client.models.generate_content(model=self.model_name, contents=prompt)
        result = self._parse_response(response.text)

        concepts = []
        relationships = []

        for unit in result.get("units", []):
            concept = unit.get("concept", "")
            intention = unit.get("intention", "")
            if not concept:
                continue

            vector = encode_text(f"{concept} {intention}")
            substrate.store_glyph(glyph_id=concept, vector=vector, content=intention, source=source)
            concepts.append(concept)

            for rel in unit.get("relationships", []):
                target = rel.get("target", "")
                if target:
                    rel_vector = encode_relationship(concept, target, "related")
                    substrate.store_relationship(rel_vector)
                    relationships.append({"source": concept, "target": target, "weight": rel.get("weight", 0.5)})

        return {"concepts": concepts, "relationships": relationships, "summary": f"Extracted {len(concepts)} glyphs from {source}", "units": result.get("units", [])}

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
