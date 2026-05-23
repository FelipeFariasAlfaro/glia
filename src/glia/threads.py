"""
GLIA Threads - The content layer.

Threads store the actual text/content that nodes point to.
A node in the graph is a pure pointer; a thread is the "memory" it references.

The separation is key: the graph navigates by topology (spreading activation),
and only AFTER determining what's relevant does the system read the actual content.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class Thread:
    """A unit of stored knowledge — the actual content a node points to."""

    id: str
    content: str
    source: str = ""  # Where this knowledge came from (file, conversation, etc.)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    node_refs: list[str] = field(default_factory=list)  # Which graph nodes point here

    def update(self, content: str) -> None:
        """Update the thread content."""
        self.content = content
        self.updated_at = time.time()


class ThreadStore:
    """
    Storage for threads (the content layer).
    Kept separate from the graph so navigation is pure topology.
    """

    def __init__(self) -> None:
        self.threads: dict[str, Thread] = {}

    def add(
        self,
        thread_id: str,
        content: str,
        source: str = "",
        node_refs: Optional[list[str]] = None,
    ) -> Thread:
        """Store a new thread or update existing one."""
        if thread_id in self.threads:
            self.threads[thread_id].update(content)
            if node_refs:
                existing_refs = set(self.threads[thread_id].node_refs)
                existing_refs.update(node_refs)
                self.threads[thread_id].node_refs = list(existing_refs)
            return self.threads[thread_id]

        thread = Thread(
            id=thread_id,
            content=content,
            source=source,
            node_refs=node_refs or [],
        )
        self.threads[thread_id] = thread
        return thread

    def get(self, thread_id: str) -> Optional[Thread]:
        """Retrieve a thread by ID."""
        return self.threads.get(thread_id)

    def get_by_nodes(self, node_ids: list[str]) -> list[Thread]:
        """Get all threads referenced by a set of activated nodes."""
        results = []
        for thread in self.threads.values():
            if any(ref in node_ids for ref in thread.node_refs):
                results.append(thread)
        return results

    def search_text(self, query: str) -> list[Thread]:
        """Simple text search across threads (fallback when graph has no match)."""
        query_lower = query.lower()
        return [
            t for t in self.threads.values()
            if query_lower in t.content.lower()
        ]

    # --- Persistence ---

    def save(self, path: Path) -> None:
        """Serialize threads to JSON."""
        data = {}
        for tid, thread in self.threads.items():
            data[tid] = {
                "content": thread.content,
                "source": thread.source,
                "created_at": thread.created_at,
                "updated_at": thread.updated_at,
                "node_refs": thread.node_refs,
            }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "ThreadStore":
        """Deserialize threads from JSON."""
        store = cls()
        if not path.exists():
            return store
        data = json.loads(path.read_text(encoding="utf-8"))
        for tid, tdata in data.items():
            thread = Thread(
                id=tid,
                content=tdata["content"],
                source=tdata.get("source", ""),
                created_at=tdata.get("created_at", time.time()),
                updated_at=tdata.get("updated_at", time.time()),
                node_refs=tdata.get("node_refs", []),
            )
            store.threads[tid] = thread
        return store
