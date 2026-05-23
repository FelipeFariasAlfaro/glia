"""
GLIA Scanner - Scans a project directory and teaches GLIA about all files.

Respects .gitignore patterns and common ignore rules.
Processes files incrementally (skips already-learned files).
"""

from __future__ import annotations

import os
import hashlib
import json
import time
from pathlib import Path
from typing import Optional, Callable

from .brain import GliaBrain

# File extensions to scan by category
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".ex", ".exs", ".clj", ".zig", ".lua",
    ".sh", ".bash", ".zsh", ".ps1", ".bat",
}

DOC_EXTENSIONS = {
    ".md", ".txt", ".rst", ".adoc", ".org",
}

CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".xml", ".conf",
}

ALL_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS | CONFIG_EXTENSIONS

# Directories to always skip
IGNORE_DIRS = {
    "node_modules", ".git", ".glia", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".idea", ".vscode", "coverage", ".pytest_cache", ".mypy_cache",
    "vendor", "packages", ".dart_tool", ".pub-cache",
    "env", ".env", ".tox", "eggs", "*.egg-info",
}

# Max file size to process (100KB)
MAX_FILE_SIZE = 100_000

SCAN_STATE_FILE = "scan_state.json"


class Scanner:
    """Scans a project and teaches GLIA about its files."""

    def __init__(self, brain: GliaBrain):
        self.brain = brain
        self.scan_state_path = brain.glia_path / SCAN_STATE_FILE
        self.scan_state = self._load_state()

    def scan(
        self,
        path: Optional[Path] = None,
        on_file: Optional[Callable[[str, str], None]] = None,
        force: bool = False,
    ) -> dict:
        """
        Scan a directory and learn from all relevant files.
        Uses AST parsing (FREE, no AI) by default.

        Args:
            path: Directory to scan (defaults to workspace root)
            on_file: Callback(filepath, status) for progress reporting
            force: Re-scan even if file hasn't changed

        Returns:
            Stats about what was scanned.
        """
        from .ast_scanner_v2 import ASTScannerV2
        from .embeddings import GliaEmbedder

        path = path or self.brain.workspace
        stats = {"scanned": 0, "learned": 0, "skipped": 0, "errors": 0}

        # Ensure brain is loaded
        self.brain.load()

        # Use embeddings if API key is available (enhanced mode)
        embedder = GliaEmbedder(api_key=self.brain.api_key)
        ast_scanner = ASTScannerV2(embedder=embedder if embedder.is_available else None)
        files = self._collect_files(path)

        for filepath in files:
            relative = str(filepath.relative_to(path))
            file_hash = self._hash_file(filepath)

            # Skip if already learned and unchanged
            if not force and relative in self.scan_state:
                if self.scan_state[relative]["hash"] == file_hash:
                    stats["skipped"] += 1
                    if on_file:
                        on_file(relative, "skipped")
                    continue

            stats["scanned"] += 1

            try:
                if on_file:
                    on_file(relative, "learning")

                # Use AST scanner v2 (FREE, no AI tokens)
                ast_scanner.scan_file(filepath, self.brain.substrate, relative)

                # Update scan state
                self.scan_state[relative] = {
                    "hash": file_hash,
                    "scanned_at": time.time(),
                }
                stats["learned"] += 1

            except Exception as e:
                stats["errors"] += 1
                if on_file:
                    on_file(relative, f"error: {e}")

        # Save the substrate after scanning all files
        self.brain.save()
        self._save_state()
        return stats

    def scan_file(self, filepath: Path) -> bool:
        """Scan a single file (used for incremental learning on save)."""
        from .ast_scanner import ASTScanner

        if not filepath.exists():
            return False

        try:
            relative = str(filepath.relative_to(self.brain.workspace))
        except ValueError:
            relative = filepath.name

        file_hash = self._hash_file(filepath)

        # Skip if unchanged
        if relative in self.scan_state:
            if self.scan_state[relative]["hash"] == file_hash:
                return False

        try:
            self.brain.load()
            ast_scanner = ASTScanner()
            ast_scanner.scan_file(filepath, self.brain.graph, self.brain.store, relative)

            self.scan_state[relative] = {
                "hash": file_hash,
                "scanned_at": time.time(),
            }
            self.brain.save()
            self._save_state()
            return True

        except Exception:
            return False

    def detect_changes(self) -> list[str]:
        """
        Detect files that changed since last scan.
        Returns list of changed file paths (relative).
        Used to notify the agent about manual changes.
        """
        changed = []
        files = self._collect_files(self.brain.workspace)

        for filepath in files:
            try:
                relative = str(filepath.relative_to(self.brain.workspace))
            except ValueError:
                continue

            file_hash = self._hash_file(filepath)

            if relative in self.scan_state:
                if self.scan_state[relative]["hash"] != file_hash:
                    changed.append(relative)
            else:
                changed.append(relative)

        return changed

    def sync_changes(self) -> dict:
        """
        Detect and re-scan changed files automatically.
        Called when MCP server starts or agent connects.
        Returns stats about what was updated.
        """
        from .ast_scanner import ASTScanner

        changed = self.detect_changes()
        if not changed:
            return {"changed": 0, "updated": 0, "files": []}

        self.brain.load()
        ast_scanner = ASTScanner()
        updated = 0

        for relative in changed:
            filepath = self.brain.workspace / relative
            if filepath.exists():
                try:
                    ast_scanner.scan_file(filepath, self.brain.graph, self.brain.store, relative)
                    self.scan_state[relative] = {
                        "hash": self._hash_file(filepath),
                        "scanned_at": time.time(),
                    }
                    updated += 1
                except Exception:
                    pass

        if updated > 0:
            self.brain.save()
            self._save_state()

        return {"changed": len(changed), "updated": updated, "files": changed}

    def _collect_files(self, root: Path) -> list[Path]:
        """Collect all scannable files respecting ignore rules."""
        files = []
        gitignore_patterns = self._load_gitignore(root)

        for dirpath, dirnames, filenames in os.walk(root):
            # Filter out ignored directories
            dirnames[:] = [
                d for d in dirnames
                if d not in IGNORE_DIRS and not d.startswith(".")
            ]

            for filename in filenames:
                filepath = Path(dirpath) / filename
                ext = filepath.suffix.lower()

                # Check extension
                if ext not in ALL_EXTENSIONS:
                    continue

                # Check file size
                try:
                    if filepath.stat().st_size > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue

                # Check gitignore patterns (basic)
                relative = str(filepath.relative_to(root)).replace("\\", "/")
                if self._is_gitignored(relative, gitignore_patterns):
                    continue

                files.append(filepath)

        return sorted(files)

    def _load_gitignore(self, root: Path) -> list[str]:
        """Load .gitignore patterns (basic implementation)."""
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        patterns = []
        for line in gitignore.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                patterns.append(line)
        return patterns

    def _is_gitignored(self, filepath: str, patterns: list[str]) -> bool:
        """Basic gitignore matching (simplified)."""
        for pattern in patterns:
            pattern_clean = pattern.rstrip("/")
            if pattern_clean in filepath:
                return True
        return False

    def _hash_file(self, filepath: Path) -> str:
        """Get a hash of file content for change detection."""
        try:
            content = filepath.read_bytes()
            return hashlib.md5(content).hexdigest()
        except OSError:
            return ""

    def _load_state(self) -> dict:
        """Load scan state from disk."""
        if self.scan_state_path.exists():
            try:
                return json.loads(self.scan_state_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _save_state(self) -> None:
        """Save scan state to disk."""
        self.scan_state_path.parent.mkdir(parents=True, exist_ok=True)
        self.scan_state_path.write_text(
            json.dumps(self.scan_state, indent=2),
            encoding="utf-8",
        )
