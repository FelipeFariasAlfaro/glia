"""
GLIA Configuration - Multi-provider support and glia.env loading.

Configuration is loaded from (in order of priority):
1. Environment variables (already set)
2. glia.env file in the workspace
3. .env file in the workspace (legacy fallback)

Supported providers: gemini, openai, anthropic
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from dotenv import load_dotenv


# Supported providers and their default models
PROVIDER_DEFAULTS = {
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
    "anthropic": "claude-sonnet-4-20250514",
}


@dataclass
class GliaConfig:
    """GLIA configuration loaded from glia.env or environment."""
    provider: str
    model: str
    api_key: Optional[str]
    workspace: Path

    @property
    def is_gemini(self) -> bool:
        return self.provider == "gemini"

    @property
    def is_openai(self) -> bool:
        return self.provider == "openai"

    @property
    def is_anthropic(self) -> bool:
        return self.provider == "anthropic"


def load_glia_env(workspace: Optional[Path] = None) -> None:
    """
    Load GLIA configuration from glia.env (preferred) or .env (fallback).
    
    Search order:
    1. glia.env in workspace
    2. .env in workspace (legacy)
    """
    ws = workspace or Path.cwd()
    
    glia_env = ws / "glia.env"
    legacy_env = ws / ".env"
    
    if glia_env.exists():
        load_dotenv(glia_env, override=True)
    elif legacy_env.exists():
        load_dotenv(legacy_env, override=True)


def _detect_provider() -> str:
    """Detect the provider from GLIA_PROVIDER env var or from available keys."""
    explicit = os.environ.get("GLIA_PROVIDER", "").lower().strip()
    if explicit in PROVIDER_DEFAULTS:
        return explicit
    
    # Auto-detect from available API keys
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY"):
        return "gemini"
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic"
    
    # Default to gemini (works with gcloud auth without key)
    return "gemini"


def _get_api_key(provider: str) -> Optional[str]:
    """Get the API key for the given provider."""
    if provider == "gemini":
        return os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    elif provider == "openai":
        return os.environ.get("OPENAI_API_KEY")
    elif provider == "anthropic":
        return os.environ.get("ANTHROPIC_API_KEY")
    return None


def get_config(workspace: Optional[Path] = None) -> GliaConfig:
    """
    Load and return the full GLIA configuration.
    
    Call this once at startup in CLI or MCP server.
    """
    ws = workspace or Path.cwd()
    load_glia_env(ws)
    
    provider = _detect_provider()
    
    # Model: explicit env var > provider default
    model = os.environ.get("GLIA_MODEL") or PROVIDER_DEFAULTS[provider]
    
    api_key = _get_api_key(provider)
    
    return GliaConfig(
        provider=provider,
        model=model,
        api_key=api_key,
        workspace=ws,
    )
