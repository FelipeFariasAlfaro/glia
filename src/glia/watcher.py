"""
GLIA Watcher - Automatically re-scans files when they change.

Monitors a directory using filesystem events and updates GLIA's memory
via AST scanning (FREE, no AI tokens). This keeps the memory in sync
with your code in real-time.
"""

import time
import logging
from pathlib import Path
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .brain import GliaBrain
from .scanner import ALL_EXTENSIONS, IGNORE_DIRS

logger = logging.getLogger("glia.watcher")


class GLIAUpdateHandler(FileSystemEventHandler):
    """Handles file system events and updates GLIA via AST scan (free)."""

    def __init__(
        self,
        brain: GliaBrain,
        workspace: Path,
        on_update: Optional[Callable[[str, dict], None]] = None,
        debounce_seconds: float = 2.0,
    ):
        self.brain = brain
        self.workspace = workspace
        self.on_update = on_update
        self.debounce_seconds = debounce_seconds
        self._last_processed: dict[str, float] = {}

    def _should_process(self, filepath: Path) -> bool:
        """Check if this file should be processed."""
        # Skip directories
        if filepath.is_dir():
            return False

        # Skip hidden files
        if filepath.name.startswith("."):
            return False

        # Skip ignored directories
        for part in filepath.parts:
            if part in IGNORE_DIRS:
                return False

        # Only process known extensions
        if filepath.suffix.lower() not in ALL_EXTENSIONS:
            return False

        return True

    def _debounce(self, rel_path: str) -> bool:
        """Returns True if we should skip (too soon since last process)."""
        now = time.time()
        if rel_path in self._last_processed:
            if now - self._last_processed[rel_path] < self.debounce_seconds:
                return True
        self._last_processed[rel_path] = now
        return False

    def _process(self, event):
        """Process a file change event using AST scan (free)."""
        if event.is_directory:
            return

        filepath = Path(event.src_path)

        if not self._should_process(filepath):
            return

        try:
            rel_path = str(filepath.relative_to(self.workspace))
        except ValueError:
            return

        if self._debounce(rel_path):
            return

        try:
            from .ast_scanner_v2 import ASTScannerV2

            self.brain.load()
            scanner = ASTScannerV2()
            scanner.scan_file(filepath, self.brain.substrate, rel_path)
            self.brain.save()

            result = {"concepts": [rel_path], "source": rel_path}
            if self.on_update:
                self.on_update(rel_path, result)

        except Exception as e:
            logger.error(f"Error processing {rel_path}: {e}")

    def on_modified(self, event):
        self._process(event)

    def on_created(self, event):
        self._process(event)


def watch_directory(
    brain: GliaBrain,
    path: Path,
    on_update: Optional[Callable[[str, dict], None]] = None,
):
    """
    Start watching a directory for changes.
    Updates GLIA memory via AST scan (free, no AI tokens).
    This function blocks until interrupted (Ctrl+C).
    """
    if not path.exists():
        raise FileNotFoundError(f"Directory {path} does not exist.")

    event_handler = GLIAUpdateHandler(brain, brain.workspace, on_update=on_update)
    observer = Observer()
    observer.schedule(event_handler, str(path), recursive=True)

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
