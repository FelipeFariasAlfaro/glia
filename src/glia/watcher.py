"""
GLIA Watcher - Automatically teaches GLIA about file changes.

This module provides functionality to monitor a directory and automatically
update GLIA's memory when files are modified.
"""

import time
import logging
from pathlib import Path
from typing import Optional, Callable

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .brain import GliaBrain

logger = logging.getLogger("glia.watcher")

class GLIAUpdateHandler(FileSystemEventHandler):
    """Handles file system events and updates GLIA."""
    
    def __init__(
        self, 
        brain: GliaBrain, 
        workspace: Path, 
        on_update: Optional[Callable[[str, dict], None]] = None,
        debounce_seconds: float = 2.0
    ):
        self.brain = brain
        self.workspace = workspace
        self.on_update = on_update
        self.debounce_seconds = debounce_seconds
        self.last_learned = {}

    def process_file(self, event):
        # Skip directories
        if event.is_directory:
            return

        filepath = Path(event.src_path)
        
        # Basic filtering: ignore hidden files and common noise
        if filepath.name.startswith(".") or "__pycache__" in str(filepath):
            return

        # We primarily care about source files (extensible later)
        if filepath.suffix not in [".py", ".md", ".txt", ".js", ".ts", ".go", ".rs"]:
            return

        # Make path relative to workspace
        try:
            rel_path = filepath.relative_to(self.workspace)
        except ValueError:
            return # File not in workspace

        # Debounce logic
        current_time = time.time()
        if str(rel_path) in self.last_learned:
            if current_time - self.last_learned[str(rel_path)] < self.debounce_seconds:
                return
        
        self.last_learned[str(rel_path)] = current_time

        try:
            if filepath.exists():
                content = filepath.read_text(encoding="utf-8")
                
                # Teach GLIA
                result = self.brain.learn(content, source=str(rel_path))
                
                if self.on_update:
                    self.on_update(str(rel_path), result)
                
        except Exception as e:
            logger.error(f"Error processing {rel_path}: {e}")

    def on_modified(self, event):
        self.process_file(event)

    def on_created(self, event):
        self.process_file(event)


def watch_directory(
    brain: GliaBrain, 
    path: Path, 
    on_update: Optional[Callable[[str, dict], None]] = None
):
    """
    Start watching a directory for changes.
    This function blocks until interrupted.
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
