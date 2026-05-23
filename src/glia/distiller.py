"""
GLIA Distiller v3 - Multi-provider support (Gemini, OpenAI, Anthropic).

Converts raw information into glyphs for the substrate using LLM distillation.
"""

from __future__ import annotations

import json
from typing import Optional

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
    """Multi-provider distiller for GLIA knowledge extraction."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        provider: str = "gemini",
    ):
        self.model_name = model
        self.api_key = api_key
        self.provider = provider
        self._client = None

    def _get_gemini_client(self):
        """Initialize Google Gemini client."""
        try:
            from google import genai
        except ImportError:
            raise ImportError(
                "google-genai is required for Gemini provider. "
                "Install with: pip install google-genai"
            )
        if not self.api_key:
            return genai.Client(vertexai=True, location="us-central1")
        return genai.Client(api_key=self.api_key)

    def _get_openai_client(self):
        """Initialize OpenAI client."""
        try:
            from openai import OpenAI
        except ImportError:
            raise ImportError(
                "openai is required for OpenAI provider. "
                "Install with: pip install openai"
            )
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI provider.")
        return OpenAI(api_key=self.api_key)

    def _get_anthropic_client(self):
        """Initialize Anthropic client."""
        try:
            import anthropic
        except ImportError:
            raise ImportError(
                "anthropic is required for Anthropic provider. "
                "Install with: pip install anthropic"
            )
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY is required for Anthropic provider.")
        return anthropic.Anthropic(api_key=self.api_key)

    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM provider and return the response text."""
        if self.provider == "gemini":
            client = self._get_gemini_client()
            response = client.models.generate_content(
                model=self.model_name, contents=prompt
            )
            return response.text

        elif self.provider == "openai":
            client = self._get_openai_client()
            response = client.chat.completions.create(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
            )
            return response.choices[0].message.content

        elif self.provider == "anthropic":
            client = self._get_anthropic_client()
            response = client.messages.create(
                model=self.model_name,
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            return response.content[0].text

        else:
            raise ValueError(
                f"Unknown provider: '{self.provider}'. "
                f"Supported: gemini, openai, anthropic"
            )

    def distill(self, content: str, substrate: Substrate, source: str = "") -> dict:
        """Distill content into glyphs using the configured LLM provider."""
        known = list(substrate.glyphs.keys())[:150]
        known_str = ", ".join(known) if known else "(empty)"

        prompt = DISTILL_PROMPT.format(
            known_nodes=known_str, content=content[:6000], source=source or "unknown"
        )

        response_text = self._call_llm(prompt)
        result = self._parse_response(response_text)

        concepts = []
        relationships = []

        for unit in result.get("units", []):
            concept = unit.get("concept", "")
            intention = unit.get("intention", "")
            if not concept:
                continue

            vector = encode_text(f"{concept} {intention}")
            substrate.store_glyph(
                glyph_id=concept, vector=vector, content=intention, source=source
            )
            concepts.append(concept)

            for rel in unit.get("relationships", []):
                target = rel.get("target", "")
                if target:
                    rel_vector = encode_relationship(concept, target, "related")
                    substrate.store_relationship(rel_vector)
                    relationships.append({
                        "source": concept,
                        "target": target,
                        "weight": rel.get("weight", 0.5),
                    })

        return {
            "concepts": concepts,
            "relationships": relationships,
            "summary": f"Extracted {len(concepts)} glyphs from {source}",
            "units": result.get("units", []),
        }

    def _parse_response(self, text: str) -> dict:
        """Parse JSON response from LLM, handling markdown code blocks."""
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
