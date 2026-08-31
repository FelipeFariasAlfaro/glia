"""Incremental, source-reversible project scanner for GLIA."""

from __future__ import annotations

import hashlib
import json
import os
import time
from functools import wraps
from pathlib import Path
from typing import Callable, Optional

from .brain import GliaBrain
from .storage import StorageConflictError

CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".swift",
    ".kt", ".scala", ".ex", ".exs", ".clj", ".zig", ".lua",
    ".sh", ".bash", ".zsh", ".ps1", ".bat",
}
DOC_EXTENSIONS = {".md", ".txt", ".rst", ".adoc", ".org", ".feature"}
CONFIG_EXTENSIONS = {
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".env",
    ".xml", ".conf",
}
ALL_EXTENSIONS = CODE_EXTENSIONS | DOC_EXTENSIONS | CONFIG_EXTENSIONS

IGNORE_DIRS = {
    "node_modules", ".git", ".glia", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".idea", ".vscode", "coverage", ".pytest_cache", ".mypy_cache",
    "vendor", "packages", ".dart_tool", ".pub-cache", "env", ".env",
    ".tox", "eggs", "*.egg-info",
}
MAX_FILE_SIZE = 100_000
SCAN_STATE_FILE = "scan_state.json"
SCAN_RETRIES = 5


def _brain_synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.brain.lock:
            return method(self, *args, **kwargs)
    return wrapped


class Scanner:
    """Scan project files into source-qualified holographic contributions."""

    def __init__(self, brain: GliaBrain):
        self.brain = brain
        self.scan_state_path = brain.glia_path / SCAN_STATE_FILE
        self.scan_state = self._load_state()

    def _relative_path(self, filepath: Path, root: Path | None = None) -> str:
        try:
            return filepath.relative_to(self.brain.workspace).as_posix()
        except ValueError:
            base = root or filepath.parent
            return filepath.relative_to(base).as_posix()

    @_brain_synchronized
    def scan(
        self,
        path: Optional[Path] = None,
        on_file: Optional[Callable[[str, str], None]] = None,
        force: bool = False,
    ) -> dict:
        """Scan a directory, reconcile deletions and retry stale snapshots."""
        from .ast_scanner_v2 import ASTScannerV2
        from .embeddings import GliaEmbedder

        root = path or self.brain.workspace
        self.scan_state = self._load_state()
        current = {
            self._relative_path(filepath, root): filepath
            for filepath in self._collect_files(root)
        }
        reconcile_deletions = root.resolve() == self.brain.workspace.resolve()
        deleted = set(self.scan_state) - set(current) if reconcile_deletions else set()

        candidates: list[tuple[Path, str]] = []
        skipped = 0
        for relative, filepath in current.items():
            file_hash = self._hash_file(filepath)
            if (
                not force
                and relative in self.scan_state
                and self.scan_state[relative]["hash"] == file_hash
            ):
                skipped += 1
                if on_file:
                    on_file(relative, "skipped")
                continue
            candidates.append((filepath, relative))

        if not candidates and not deleted:
            return {
                "scanned": 0, "learned": 0, "removed": 0,
                "skipped": skipped, "errors": 0,
            }

        for attempt in range(SCAN_RETRIES):
            self.brain.load(force=attempt > 0)
            embedder = GliaEmbedder(api_key=self.brain.api_key)
            ast_scanner = ASTScannerV2(
                embedder=embedder if embedder.is_available else None
            )
            eligible_now = {
                self._relative_path(filepath, root)
                for filepath in self._collect_files(root)
            }
            active_deletes = deleted - eligible_now
            pending_state: dict[str, dict] = {}
            learned = 0
            errors = 0

            for relative in active_deletes:
                self.brain.substrate.remove_source(relative)
                if on_file:
                    on_file(relative, "removed")

            for filepath, relative in candidates:
                try:
                    if on_file:
                        on_file(relative, "learning")
                    result = ast_scanner.scan_file(
                        filepath, self.brain.substrate, relative
                    )
                    pending_state[relative] = {
                        "hash": result["hash"],
                        "scanned_at": time.time(),
                    }
                    learned += 1
                except Exception as error:
                    errors += 1
                    if on_file:
                        on_file(relative, f"error: {error}")

            if not pending_state and not active_deletes:
                return {
                    "scanned": len(candidates), "learned": 0, "removed": 0,
                    "skipped": skipped, "errors": errors,
                }

            try:
                self.brain.save(
                    scan_state_updates=pending_state,
                    scan_state_deletes=active_deletes,
                )
            except StorageConflictError:
                if attempt < SCAN_RETRIES - 1:
                    time.sleep(min(0.002 * (2 ** attempt), 0.05))
                    continue
                raise

            self.scan_state.update(pending_state)
            for relative in active_deletes:
                self.scan_state.pop(relative, None)
            return {
                "scanned": len(candidates),
                "learned": learned,
                "removed": len(active_deletes),
                "skipped": skipped,
                "errors": errors,
            }

        raise StorageConflictError("Could not persist full scan after retries")

    @_brain_synchronized
    def scan_file(self, filepath: Path) -> bool:
        """Scan one file or remove its prior contributions if it was deleted."""
        from .ast_scanner_v2 import ASTScannerV2
        from .embeddings import GliaEmbedder

        relative = self._relative_path(filepath)
        self.scan_state = self._load_state()
        if not filepath.exists():
            if relative not in self.scan_state:
                return False
            for attempt in range(SCAN_RETRIES):
                self.brain.load(force=attempt > 0)
                self.brain.substrate.remove_source(relative)
                try:
                    self.brain.save(scan_state_deletes={relative})
                except StorageConflictError:
                    if attempt < SCAN_RETRIES - 1:
                        continue
                    raise
                self.scan_state.pop(relative, None)
                return True
            return False

        file_hash = self._hash_file(filepath)
        if (
            relative in self.scan_state
            and self.scan_state[relative]["hash"] == file_hash
        ):
            return False

        for attempt in range(SCAN_RETRIES):
            try:
                self.brain.load(force=attempt > 0)
                embedder = GliaEmbedder(api_key=self.brain.api_key)
                scanner = ASTScannerV2(
                    embedder=embedder if embedder.is_available else None
                )
                result = scanner.scan_file(
                    filepath, self.brain.substrate, relative
                )
                pending_state = {
                    relative: {
                        "hash": result["hash"],
                        "scanned_at": time.time(),
                    }
                }
                self.brain.save(scan_state_updates=pending_state)
                self.scan_state.update(pending_state)
                return True
            except StorageConflictError:
                if attempt == SCAN_RETRIES - 1:
                    raise
                time.sleep(min(0.002 * (2 ** attempt), 0.05))
            except (OSError, UnicodeError):
                self.brain.load(force=True)
                return False
        return False

    def detect_changes(self) -> list[str]:
        """Return new, modified, deleted or newly ignored source paths."""
        self.scan_state = self._load_state()
        current = {
            self._relative_path(filepath): filepath
            for filepath in self._collect_files(self.brain.workspace)
        }
        changed = {
            relative
            for relative, filepath in current.items()
            if relative not in self.scan_state
            or self.scan_state[relative]["hash"] != self._hash_file(filepath)
        }
        changed.update(set(self.scan_state) - set(current))
        return sorted(changed)

    @_brain_synchronized
    def sync_changes(self) -> dict:
        """Atomically rescan modifications and remove deleted sources."""
        from .ast_scanner_v2 import ASTScannerV2
        from .embeddings import GliaEmbedder

        changed = self.detect_changes()
        if not changed:
            return {"changed": 0, "updated": 0, "removed": 0, "files": []}

        for attempt in range(SCAN_RETRIES):
            self.brain.load(force=attempt > 0)
            embedder = GliaEmbedder(api_key=self.brain.api_key)
            scanner = ASTScannerV2(
                embedder=embedder if embedder.is_available else None
            )
            eligible_now = {
                self._relative_path(filepath)
                for filepath in self._collect_files(self.brain.workspace)
            }
            pending_state: dict[str, dict] = {}
            pending_deletes: set[str] = set()
            updated = 0

            for relative in changed:
                filepath = self.brain.workspace / relative
                if relative not in eligible_now:
                    self.brain.substrate.remove_source(relative)
                    pending_deletes.add(relative)
                    continue
                try:
                    result = scanner.scan_file(
                        filepath, self.brain.substrate, relative
                    )
                    pending_state[relative] = {
                        "hash": result["hash"],
                        "scanned_at": time.time(),
                    }
                    updated += 1
                except Exception:
                    # ASTScannerV2 restores the current source; reload on any
                    # unexpected failure so earlier files cannot leak into a
                    # later, unrelated commit.
                    self.brain.load(force=True)
                    raise

            if not pending_state and not pending_deletes:
                return {
                    "changed": len(changed), "updated": 0,
                    "removed": 0, "files": changed,
                }

            try:
                self.brain.save(
                    scan_state_updates=pending_state,
                    scan_state_deletes=pending_deletes,
                )
            except StorageConflictError:
                if attempt < SCAN_RETRIES - 1:
                    time.sleep(min(0.002 * (2 ** attempt), 0.05))
                    continue
                raise

            self.scan_state.update(pending_state)
            for relative in pending_deletes:
                self.scan_state.pop(relative, None)
            return {
                "changed": len(changed),
                "updated": updated,
                "removed": len(pending_deletes),
                "files": changed,
            }

        raise StorageConflictError("Could not persist scanner changes after retries")

    def _collect_files(self, root: Path) -> list[Path]:
        files = []
        gitignore_patterns = self._load_gitignore(root)
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [
                directory
                for directory in dirnames
                if directory not in IGNORE_DIRS and not directory.startswith(".")
            ]
            for filename in filenames:
                filepath = Path(dirpath) / filename
                if filepath.suffix.lower() not in ALL_EXTENSIONS:
                    continue
                try:
                    if filepath.stat().st_size > MAX_FILE_SIZE:
                        continue
                except OSError:
                    continue
                relative = filepath.relative_to(root).as_posix()
                if self._is_gitignored(relative, gitignore_patterns):
                    continue
                files.append(filepath)
        return sorted(files)

    def _load_gitignore(self, root: Path) -> list[str]:
        gitignore = root / ".gitignore"
        if not gitignore.exists():
            return []
        return [
            line
            for raw_line in gitignore.read_text(
                encoding="utf-8", errors="ignore"
            ).splitlines()
            if (line := raw_line.strip()) and not line.startswith("#")
        ]

    def _is_gitignored(self, filepath: str, patterns: list[str]) -> bool:
        return any(pattern.rstrip("/") in filepath for pattern in patterns)

    def _hash_file(self, filepath: Path) -> str:
        try:
            return hashlib.sha256(filepath.read_bytes()).hexdigest()
        except OSError:
            return ""

    def _load_state(self) -> dict:
        """Load SQLite scan state, importing the legacy JSON file once."""
        self.brain.glia_path.mkdir(parents=True, exist_ok=True)
        state = self.brain.load_scan_state()
        if state or not self.scan_state_path.exists():
            return state
        try:
            legacy = json.loads(
                self.scan_state_path.read_text(encoding="utf-8")
            )
        except (json.JSONDecodeError, OSError):
            return state
        if legacy:
            self.brain.save_scan_state(legacy)
            return self.brain.load_scan_state()
        return state

    def _save_state(self) -> None:
        self.brain.save_scan_state(self.scan_state)
