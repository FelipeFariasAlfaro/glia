"""
GLIA Storage v2 - SQLite persistence. No edges table.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from functools import wraps
from pathlib import Path
from typing import Optional

import numpy as np

from .binding import DIMENSION
from .substrate import Substrate, SubstrateRegion, GlyphMeta, RelationshipMeta

DB_FILE = "memory.db"
CURRENT_SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS storage_metadata (
    key TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);

INSERT OR IGNORE INTO storage_metadata (key, value) VALUES ('revision', 0);

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

CREATE TABLE IF NOT EXISTS relationship_contributions (
    id TEXT PRIMARY KEY,
    vector BLOB NOT NULL,
    source TEXT DEFAULT '',
    region_id TEXT DEFAULT 'default'
);

CREATE TABLE IF NOT EXISTS scan_state (
    file_path TEXT PRIMARY KEY,
    file_hash TEXT NOT NULL,
    last_scanned REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_glyphs_region ON glyphs(region_id);
CREATE INDEX IF NOT EXISTS idx_glyphs_magnitude ON glyphs(magnitude);
CREATE INDEX IF NOT EXISTS idx_relationships_source ON relationship_contributions(source);
CREATE INDEX IF NOT EXISTS idx_relationships_region ON relationship_contributions(region_id);
"""


def _synchronized(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._lock:
            return method(self, *args, **kwargs)
    return wrapped


class StorageConflictError(RuntimeError):
    """Raised when a stale in-memory substrate attempts to overwrite newer data."""


class StorageCorruptionError(RuntimeError):
    """Raised when persisted vectors do not match the configured dimension."""


class SQLiteStorage:
    def __init__(self, glia_path: Path):
        self.db_path = glia_path / DB_FILE
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()

    @property
    @_synchronized
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=5.0,
                check_same_thread=False,
            )
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=FULL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._conn.executescript(SCHEMA)
            self._migrate_schema(self._conn)
        return self._conn

    @staticmethod
    def _migrate_schema(c: sqlite3.Connection) -> None:
        """Upgrade existing v2 databases without discarding anonymous interference."""
        c.execute("BEGIN IMMEDIATE")
        try:
            row = c.execute(
                "SELECT value FROM storage_metadata WHERE key = 'schema_version'"
            ).fetchone()
            version = int(row[0]) if row is not None else 2
            if version >= CURRENT_SCHEMA_VERSION:
                c.execute("COMMIT")
                return

            region_rows = list(c.execute("SELECT id, vector FROM substrate_regions"))
            migrated_residual = False
            for region_row in region_rows:
                persisted = np.frombuffer(region_row["vector"], dtype=np.float64).copy()
                known = np.zeros_like(persisted)
                valid = True
                for glyph_row in c.execute(
                    "SELECT vector, magnitude FROM glyphs WHERE region_id = ?",
                    (region_row["id"],),
                ):
                    vector = np.frombuffer(glyph_row["vector"], dtype=np.float64)
                    if vector.shape != persisted.shape:
                        valid = False
                        break
                    known += vector * float(glyph_row["magnitude"])
                if not valid:
                    continue
                for relationship_row in c.execute(
                    "SELECT vector FROM relationship_contributions WHERE region_id = ?",
                    (region_row["id"],),
                ):
                    vector = np.frombuffer(relationship_row["vector"], dtype=np.float64)
                    if vector.shape != persisted.shape:
                        valid = False
                        break
                    known += vector
                if not valid:
                    continue

                residual = persisted - known
                if np.linalg.norm(residual) > 1e-10:
                    c.execute(
                        """INSERT OR REPLACE INTO relationship_contributions
                           (id, vector, source, region_id) VALUES (?, ?, ?, ?)""",
                        (
                            f"legacy-residual:{region_row['id']}",
                            residual.astype(np.float64).tobytes(),
                            "",
                            region_row["id"],
                        ),
                    )
                    migrated_residual = True

            c.execute(
                "INSERT OR REPLACE INTO storage_metadata (key, value) VALUES ('schema_version', ?)",
                (CURRENT_SCHEMA_VERSION,),
            )
            if region_rows or migrated_residual:
                c.execute(
                    "UPDATE storage_metadata SET value = value + 1 WHERE key = 'revision'"
                )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

    def __enter__(self) -> "SQLiteStorage":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        self.close()

    @_synchronized
    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    @_synchronized
    def get_revision(self) -> int:
        row = self.conn.execute(
            "SELECT value FROM storage_metadata WHERE key = 'revision'"
        ).fetchone()
        return int(row[0]) if row is not None else 0

    @staticmethod
    def _vector_bytes(vector: np.ndarray, dimension: int, label: str) -> bytes:
        value = np.asarray(vector, dtype=np.float64)
        if value.shape != (dimension,):
            raise ValueError(
                f"{label} must have shape ({dimension},), got {value.shape}"
            )
        if not np.all(np.isfinite(value)):
            raise ValueError(f"{label} contains non-finite values")
        return value.tobytes()

    @staticmethod
    def _decode_vector(blob: bytes, dimension: int, label: str) -> np.ndarray:
        vector = np.frombuffer(blob, dtype=np.float64).copy()
        if vector.shape != (dimension,):
            raise StorageCorruptionError(
                f"{label} has {vector.size} dimensions; expected {dimension}"
            )
        if not np.all(np.isfinite(vector)):
            raise StorageCorruptionError(f"{label} contains non-finite values")
        return vector

    @staticmethod
    def _is_busy(error: sqlite3.OperationalError) -> bool:
        code = getattr(error, "sqlite_errorcode", None)
        if code in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
            return True
        message = str(error).lower()
        return "locked" in message or "busy" in message

    @classmethod
    def _begin_immediate(
        cls,
        c: sqlite3.Connection,
        attempts: int = 8,
    ) -> None:
        """Acquire a write transaction with bounded contention backoff."""
        for attempt in range(attempts):
            try:
                c.execute("BEGIN IMMEDIATE")
                return
            except sqlite3.OperationalError as error:
                if not cls._is_busy(error) or attempt == attempts - 1:
                    raise
                time.sleep(min(0.002 * (2 ** attempt), 0.05))

    @staticmethod
    def _existing_ids(c: sqlite3.Connection, table: str) -> set[str]:
        return {row[0] for row in c.execute(f"SELECT id FROM {table}")}

    @staticmethod
    def _delete_ids(c: sqlite3.Connection, table: str, ids: set[str]) -> int:
        if ids:
            c.executemany(
                f"DELETE FROM {table} WHERE id = ?",
                ((value,) for value in ids),
            )
        return len(ids)

    @_synchronized
    def save_substrate(
        self,
        substrate: Substrate,
        expected_revision: int | None = None,
        scan_state_updates: dict | None = None,
        scan_state_deletes: set[str] | None = None,
    ) -> int:
        """Persist exact membership while writing only changed payload rows."""
        self._validate_substrate(substrate)
        tracking = substrate.dirty_snapshot()
        current_region_ids = set(substrate.regions)
        current_glyph_ids = set(substrate.glyphs)
        current_relationship_ids = set(substrate.relationships)

        c = self.conn
        self._begin_immediate(c)
        try:
            row = c.execute(
                "SELECT value FROM storage_metadata WHERE key = 'revision'"
            ).fetchone()
            current_revision = int(row[0]) if row is not None else 0
            if expected_revision is not None and current_revision != expected_revision:
                raise StorageConflictError(
                    "GLIA memory changed in another process "
                    f"(expected revision {expected_revision}, found {current_revision}). "
                    "Reload before saving to avoid losing updates."
                )

            existing_region_ids = self._existing_ids(c, "substrate_regions")
            existing_glyph_ids = self._existing_ids(c, "glyphs")
            existing_relationship_ids = self._existing_ids(
                c, "relationship_contributions"
            )

            deleted_regions = existing_region_ids - current_region_ids
            deleted_glyphs = existing_glyph_ids - current_glyph_ids
            deleted_relationships = (
                existing_relationship_ids - current_relationship_ids
            )
            self._delete_ids(c, "substrate_regions", deleted_regions)
            self._delete_ids(c, "glyphs", deleted_glyphs)
            self._delete_ids(
                c, "relationship_contributions", deleted_relationships
            )

            region_ids = (
                set(tracking.regions) | (current_region_ids - existing_region_ids)
            ) & current_region_ids
            glyph_ids = (
                set(tracking.glyphs) | (current_glyph_ids - existing_glyph_ids)
            ) & current_glyph_ids
            relationship_ids = (
                set(tracking.relationships)
                | (current_relationship_ids - existing_relationship_ids)
            ) & current_relationship_ids

            region_rows = []
            for region_id in region_ids:
                region = substrate.regions[region_id]
                region_rows.append(
                    (
                        region_id,
                        self._vector_bytes(
                            region.vector,
                            substrate.dimension,
                            f"region {region_id!r}",
                        ),
                        region.glyph_count,
                        region.capacity,
                        region.created_at,
                    )
                )
            glyph_rows = []
            for glyph_id in glyph_ids:
                glyph = substrate.glyphs[glyph_id]
                glyph_rows.append(
                    (
                        glyph_id,
                        self._vector_bytes(
                            glyph.vector,
                            substrate.dimension,
                            f"glyph {glyph_id!r}",
                        ),
                        glyph.magnitude,
                        glyph.created_at,
                        glyph.last_activated,
                        glyph.activation_count,
                        glyph.source,
                        glyph.content,
                        glyph.region_id,
                    )
                )
            relationship_rows = []
            for relationship_id in relationship_ids:
                relationship = substrate.relationships[relationship_id]
                relationship_rows.append(
                    (
                        relationship_id,
                        self._vector_bytes(
                            relationship.vector,
                            substrate.dimension,
                            f"relationship {relationship_id!r}",
                        ),
                        relationship.source,
                        relationship.region_id,
                    )
                )

            c.executemany(
                """INSERT OR REPLACE INTO substrate_regions
                   (id, vector, glyph_count, capacity, created_at)
                   VALUES (?, ?, ?, ?, ?)""",
                region_rows,
            )
            c.executemany(
                """INSERT OR REPLACE INTO glyphs
                   (id, vector, magnitude, created_at, last_activated,
                    activation_count, source, content, region_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                glyph_rows,
            )
            c.executemany(
                """INSERT OR REPLACE INTO relationship_contributions
                   (id, vector, source, region_id) VALUES (?, ?, ?, ?)""",
                relationship_rows,
            )
            if scan_state_deletes:
                c.executemany(
                    "DELETE FROM scan_state WHERE file_path = ?",
                    ((path,) for path in scan_state_deletes),
                )
            if scan_state_updates:
                c.executemany(
                    """INSERT OR REPLACE INTO scan_state
                       (file_path, file_hash, last_scanned) VALUES (?, ?, ?)""",
                    [
                        (
                            path,
                            info["hash"],
                            info.get("scanned_at", time.time()),
                        )
                        for path, info in scan_state_updates.items()
                    ],
                )
            new_revision = current_revision + 1
            c.execute(
                "UPDATE storage_metadata SET value = ? WHERE key = 'revision'",
                (new_revision,),
            )
            c.execute("COMMIT")
        except Exception:
            if c.in_transaction:
                c.execute("ROLLBACK")
            raise

        substrate.mark_clean(expected_version=tracking.mutation_version)
        self.last_save_stats = {
            "regions_upserted": len(region_rows),
            "glyphs_upserted": len(glyph_rows),
            "relationships_upserted": len(relationship_rows),
            "regions_deleted": len(deleted_regions),
            "glyphs_deleted": len(deleted_glyphs),
            "relationships_deleted": len(deleted_relationships),
        }
        return new_revision

    @staticmethod
    def _validate_substrate(substrate: Substrate) -> None:
        """Verify references, counters and holographic superposition invariants."""
        expected = {
            region_id: np.zeros(substrate.dimension, dtype=np.float64)
            for region_id in substrate.regions
        }
        counts = {region_id: 0 for region_id in substrate.regions}

        for glyph in substrate.glyphs.values():
            if glyph.region_id not in expected:
                raise StorageCorruptionError(
                    f"glyph {glyph.id!r} references missing region {glyph.region_id!r}"
                )
            if not np.isfinite(glyph.magnitude) or glyph.magnitude < 0:
                raise StorageCorruptionError(
                    f"glyph {glyph.id!r} has invalid magnitude {glyph.magnitude!r}"
                )
            expected[glyph.region_id] += glyph.vector * glyph.magnitude
            counts[glyph.region_id] += 1

        for relationship in substrate.relationships.values():
            if relationship.region_id not in expected:
                raise StorageCorruptionError(
                    f"relationship {relationship.id!r} references missing region "
                    f"{relationship.region_id!r}"
                )
            expected[relationship.region_id] += relationship.vector

        for region_id, region in substrate.regions.items():
            if region.glyph_count != counts[region_id]:
                raise StorageCorruptionError(
                    f"region {region_id!r} reports {region.glyph_count} glyphs; "
                    f"reconstructed {counts[region_id]}"
                )
            if not np.allclose(
                region.vector,
                expected[region_id],
                rtol=1e-9,
                atol=1e-9,
            ):
                error = float(np.linalg.norm(region.vector - expected[region_id]))
                raise StorageCorruptionError(
                    f"region {region_id!r} is inconsistent with its contributions "
                    f"(L2 error {error:.3e})"
                )

    @_synchronized
    def load_substrate_versioned(
        self,
        dimension: int = DIMENSION,
    ) -> tuple[Substrate, int]:
        """Load substrate and revision from one consistent SQLite snapshot."""
        substrate = Substrate(dimension=dimension)
        c = self.conn
        c.execute("BEGIN")
        try:
            revision = self.get_revision()
            region_rows = list(c.execute("SELECT * FROM substrate_regions"))
            glyph_rows = list(c.execute("SELECT * FROM glyphs"))
            relationship_rows = list(
                c.execute("SELECT * FROM relationship_contributions")
            )
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise

        for row in region_rows:
            vector = self._decode_vector(
                row["vector"], dimension, f"region {row['id']!r}"
            )
            region = SubstrateRegion(
                id=row["id"], vector=vector, glyph_count=row["glyph_count"],
                capacity=row["capacity"], created_at=row["created_at"],
            )
            substrate.regions[row["id"]] = region

        for row in glyph_rows:
            vector = self._decode_vector(
                row["vector"], dimension, f"glyph {row['id']!r}"
            )
            glyph = GlyphMeta(
                id=row["id"], vector=vector, magnitude=row["magnitude"],
                created_at=row["created_at"],
                last_activated=row["last_activated"],
                activation_count=row["activation_count"], source=row["source"],
                content=row["content"], region_id=row["region_id"],
            )
            substrate.glyphs[row["id"]] = glyph

        for row in relationship_rows:
            vector = self._decode_vector(
                row["vector"], dimension, f"relationship {row['id']!r}"
            )
            relationship = RelationshipMeta(
                id=row["id"],
                vector=vector,
                source=row["source"],
                region_id=row["region_id"],
            )
            substrate.relationships[row["id"]] = relationship

        self._validate_substrate(substrate)
        substrate.mark_clean()
        return substrate, revision

    @_synchronized
    def load_substrate(self, dimension: int = DIMENSION) -> Substrate:
        substrate, _ = self.load_substrate_versioned(dimension=dimension)
        return substrate

    @_synchronized
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

    @_synchronized
    def load_scan_state(self) -> dict:
        state = {}
        for row in self.conn.execute("SELECT * FROM scan_state"):
            state[row["file_path"]] = {"hash": row["file_hash"], "scanned_at": row["last_scanned"]}
        return state

    @_synchronized
    def health_check(self, deep: bool = False) -> dict:
        """Run SQLite checks and report durable storage metadata."""
        pragma = "integrity_check" if deep else "quick_check"
        rows = [row[0] for row in self.conn.execute(f"PRAGMA {pragma}")]
        status = "ok" if rows == ["ok"] else "corrupt"
        wal_path = self.db_path.with_name(f"{self.db_path.name}-wal")
        return {
            "status": status,
            "check": pragma,
            "details": rows,
            "revision": self.get_revision(),
            "database_bytes": self.db_path.stat().st_size if self.db_path.exists() else 0,
            "wal_bytes": wal_path.stat().st_size if wal_path.exists() else 0,
        }

    @_synchronized
    def backup(self, destination: Path) -> Path:
        """Create a consistent SQLite backup and atomically publish it."""
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(
            f".{destination.name}.{os.getpid()}.{threading.get_ident()}.tmp"
        )
        if temporary.exists():
            temporary.unlink()
        target = sqlite3.connect(str(temporary))
        try:
            self.conn.backup(target)
            target.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        finally:
            target.close()
        os.replace(temporary, destination)
        return destination

    @_synchronized
    def stats(self) -> dict:
        c = self.conn
        regions = c.execute("SELECT COUNT(*) FROM substrate_regions").fetchone()[0]
        glyphs = c.execute("SELECT COUNT(*) FROM glyphs").fetchone()[0]
        return {"regions": regions, "glyphs": glyphs, "dimension": DIMENSION}
