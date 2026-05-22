"""
GLIA Storage v2 - SQLite persistence. No edges table.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Optional

import numpy as np

from .binding import DIMENSION
from .substrate import Substrate, SubstrateRegion, GlyphMeta

DB_FILE = "memory.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS substrate_regions (
    id TEXT PRIMARY KEY,
    vector BLOB NOT NULL,
    glyph_count INTEGER DEFAULT 0,
    capacity INTEGER DEFAULT 500,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS glyphs (
    id TEXT PRIMARY KEY,
    vector BLOB NOT NULL,
    magnitude REAL DEFAULT 1.0,
    created_at REAL NOT NULL,
    last_activated REAL NOT NULL,
    activation_count INTEGER DEFAULT 0,
    source TEXT DEFAULT '',
    content TEXT DEFAULT '',
    region_id TEXT DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS scan_state (
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    last_scanned REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_glyphs_region ON glyphs(region_id);
CREATE INDEX IF NOT EXISTS idx_glyphs_magnitude ON glyphs(magnitude);
"""


class SQLiteStorage:
    def __init__(self, glia_path: Path):
        self.db_path = glia_path / DB_FILE
        self._conn: Optional[sqlite3.Connection] = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.executescript(SCHEMA)
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def save_substrate(self, substrate: Substrate) -> None:
        c = self.conn
        c.execute("BEGIN")
        try:
            for region_id, region in substrate.regions.items():
                c.execute(
                    """INSERT OR REPLACE INTO substrate_regions (id, vector, glyph_count, capacity, created_at) VALUES (?, ?, ?, ?, ?)""",
                    (region_id, region.vector.tobytes(), region.glyph_count, region.capacity, region.created_at),
                )
            for glyph_id, glyph in substrate.glyphs.items():
                c.execute(
                    """INSERT OR REPLACE INTO glyphs (id, vector, magnitude, created_at, last_activated, activation_count, source, content, region_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (glyph_id, glyph.vector.tobytes(), glyph.magnitude, glyph.created_at, glyph.last_activated, glyph.activation_count, glyph.source, glyph.content, glyph.region_id),
                )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def load_substrate(self, dimension: int = DIMENSION) -> Substrate:
        substrate = Substrate(dimension=dimension)
        c = self.conn

        for row in c.execute("SELECT * FROM substrate_regions"):
            vector = np.frombuffer(row["vector"], dtype=np.float64).copy()
            region = SubstrateRegion(id=row["id"], vector=vector, glyph_count=row["glyph_count"], capacity=row["capacity"], created_at=row["created_at"])
            substrate.regions[row["id"]] = region

        for row in c.execute("SELECT * FROM glyphs"):
            vector = np.frombuffer(row["vector"], dtype=np.float64).copy()
            glyph = GlyphMeta(id=row["id"], vector=vector, magnitude=row["magnitude"], created_at=row["created_at"], last_activated=row["last_activated"], activation_count=row["activation_count"], source=row["source"], content=row["content"], region_id=row["region_id"])
            substrate.glyphs[row["id"]] = glyph

        return substrate

    def save_scan_state(self, state: dict) -> None:
        c = self.conn
        c.execute("BEGIN")
        try:
            for path, info in state.items():
                c.execute("INSERT OR REPLACE INTO scan_state (file_path, file_hash, last_scanned) VALUES (?, ?, ?)", (path, info["hash"], info.get("scanned_at", time.time())))
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def load_scan_state(self) -> dict:
        state = {}
        for row in self.conn.execute("SELECT * FROM scan_state"):
            state[row["file_path"]] = {"hash": row["file_hash"], "scanned_at": row["last_scanned"]}
        return state

    def stats(self) -> dict:
        c = self.conn
        regions = c.execute("SELECT COUNT(*) FROM substrate_regions").fetchone()[0]
        glyphs = c.execute("SELECT COUNT(*) FROM glyphs").fetchone()[0]
        return {"regions": regions, "glyphs": glyphs, "dimension": DIMENSION}
