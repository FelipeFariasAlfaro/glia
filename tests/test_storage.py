import sqlite3
from pathlib import Path

import numpy as np
import pytest

from glia.brain import GliaBrain
from glia.encoder import encode_identifier, encode_relationship
from glia.storage import SQLiteStorage, StorageConflictError, StorageCorruptionError
from glia.substrate import Substrate


def make_storage(tmp_path: Path) -> SQLiteStorage:
    glia_path = tmp_path / ".glia"
    glia_path.mkdir()
    return SQLiteStorage(glia_path)


def test_snapshot_round_trip_preserves_vectors_metadata_and_revision(tmp_path):
    storage = make_storage(tmp_path)
    substrate = Substrate()
    glyph = substrate.store_glyph(
        "authentication",
        encode_identifier("authentication"),
        content="Authentication decision",
        source="docs/auth.md",
    )
    for _ in range(3):
        substrate.record_activation(glyph)
    substrate.set_glyph_magnitude(glyph, 1.25)
    relationship = encode_relationship("authentication", "session", "uses")
    substrate.store_relationship(
        relationship,
        relationship_id="docs/auth.md:authentication-session",
        source="docs/auth.md",
    )

    revision = storage.save_substrate(substrate, expected_revision=0)
    loaded, loaded_revision = storage.load_substrate_versioned()

    assert revision == loaded_revision == 1
    assert loaded.glyphs["authentication"].content == "Authentication decision"
    assert loaded.glyphs["authentication"].source == "docs/auth.md"
    assert loaded.glyphs["authentication"].activation_count == 3
    assert loaded.glyphs["authentication"].magnitude == pytest.approx(1.25)
    np.testing.assert_allclose(loaded.glyphs["authentication"].vector, glyph.vector)
    np.testing.assert_allclose(
        loaded.relationships["docs/auth.md:authentication-session"].vector,
        relationship,
    )
    assert loaded.relationships["docs/auth.md:authentication-session"].source == "docs/auth.md"
    np.testing.assert_allclose(
        loaded.regions["default"].vector,
        glyph.vector * 1.25 + relationship,
    )


def test_stale_writer_is_rejected_without_losing_committed_memory(tmp_path):
    first = make_storage(tmp_path)
    second = SQLiteStorage(tmp_path / ".glia")
    first_snapshot, first_revision = first.load_substrate_versioned()
    second_snapshot, second_revision = second.load_substrate_versioned()

    first_snapshot.store_glyph("first", encode_identifier("first"))
    first.save_substrate(first_snapshot, expected_revision=first_revision)

    second_snapshot.store_glyph("second", encode_identifier("second"))
    with pytest.raises(StorageConflictError, match="changed in another process"):
        second.save_substrate(second_snapshot, expected_revision=second_revision)

    persisted, revision = first.load_substrate_versioned()
    assert revision == 1
    assert set(persisted.glyphs) == {"first"}


def test_snapshot_removes_records_no_longer_present(tmp_path):
    storage = make_storage(tmp_path)
    substrate = Substrate()
    substrate.store_glyph("temporary", encode_identifier("temporary"))
    revision = storage.save_substrate(substrate, expected_revision=0)

    substrate.glyphs.clear()
    substrate.regions.clear()
    storage.save_substrate(substrate, expected_revision=revision)
    loaded, _ = storage.load_substrate_versioned()

    assert loaded.glyphs == {}
    assert loaded.regions == {}


def test_corrupt_vector_dimension_is_reported_explicitly(tmp_path):
    storage = make_storage(tmp_path)
    storage.conn.execute(
        """INSERT INTO substrate_regions
           (id, vector, glyph_count, capacity, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("broken", np.zeros(8, dtype=np.float64).tobytes(), 0, 500, 0.0),
    )
    storage.conn.commit()

    with pytest.raises(StorageCorruptionError, match="expected 1024"):
        storage.load_substrate()


def test_glia_brain_retries_stale_snapshot_and_merges_commits(tmp_path):
    first = GliaBrain(workspace=tmp_path)
    first.init()
    second = GliaBrain(workspace=tmp_path)
    second.load()

    first.learn_offline(
        content="",
        concepts=["first decision"],
        relationships=[],
        summary="The first writer committed this decision.",
    )
    second.learn_offline(
        content="",
        concepts=["second decision"],
        relationships=[],
        summary="The stale writer must reload and merge its decision.",
    )

    second.load(force=True)
    assert {"first decision", "second decision"}.issubset(second.substrate.glyphs)


def test_legacy_database_migration_preserves_anonymous_interference(tmp_path):
    glia_path = tmp_path / ".glia"
    glia_path.mkdir()
    db_path = glia_path / "memory.db"
    vector = encode_identifier("legacy")
    association = encode_relationship("legacy", "target", "related")
    persisted_region = vector + association

    connection = sqlite3.connect(db_path)
    connection.executescript(
        """
        CREATE TABLE storage_metadata (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
        INSERT INTO storage_metadata (key, value) VALUES ('revision', 4);
        CREATE TABLE substrate_regions (
            id TEXT PRIMARY KEY, vector BLOB NOT NULL, glyph_count INTEGER,
            capacity INTEGER, created_at REAL
        );
        CREATE TABLE glyphs (
            id TEXT PRIMARY KEY, vector BLOB NOT NULL, magnitude REAL,
            created_at REAL, last_activated REAL, activation_count INTEGER,
            source TEXT, content TEXT, region_id TEXT
        );
        """
    )
    connection.execute(
        "INSERT INTO substrate_regions VALUES (?, ?, ?, ?, ?)",
        ("default", persisted_region.tobytes(), 1, 500, 0.0),
    )
    # Legacy plasticity raised magnitude without updating the region vector.
    connection.execute(
        "INSERT INTO glyphs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        ("legacy", vector.tobytes(), 1.5, 0.0, 0.0, 1, "", "", "default"),
    )
    connection.commit()
    connection.close()

    storage = SQLiteStorage(glia_path)
    substrate, revision = storage.load_substrate_versioned()

    assert revision == 5
    assert "legacy-residual:default" in substrate.relationships
    reconstructed = (
        substrate.glyphs["legacy"].vector * substrate.glyphs["legacy"].magnitude
        + substrate.relationships["legacy-residual:default"].vector
    )
    np.testing.assert_allclose(reconstructed, persisted_region, atol=1e-12)
    np.testing.assert_allclose(substrate.regions["default"].vector, persisted_region)


def test_glia_brain_can_be_used_from_a_worker_thread(tmp_path):
    """MCP may create the brain in one thread and execute a tool in another."""
    from concurrent.futures import ThreadPoolExecutor

    brain = GliaBrain(workspace=tmp_path)
    brain.init()

    def learn_and_read_stats():
        brain.learn_offline(
            content="",
            concepts=["thread-safe memory"],
            relationships=[],
            summary="The shared GLIA brain supports serialized cross-thread access.",
            source="mcp worker",
        )
        return brain.stats()

    with ThreadPoolExecutor(max_workers=1) as executor:
        stats = executor.submit(learn_and_read_stats).result()

    assert stats["nodes"] == 1
    assert "thread-safe memory" in brain.substrate.glyphs


def test_concurrent_brains_retry_and_preserve_every_commit(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    initial = GliaBrain(workspace=tmp_path)
    initial.init()
    writers = 4
    barrier = Barrier(writers)

    def write(index: int):
        brain = GliaBrain(workspace=tmp_path)
        brain.load()
        barrier.wait()
        brain.learn_offline(
            content="",
            concepts=[f"concurrent decision {index}"],
            relationships=[],
            summary=f"Decision committed by writer {index}.",
            source=f"writer-{index}",
        )
        brain.close()

    with ThreadPoolExecutor(max_workers=writers) as executor:
        list(executor.map(write, range(writers)))

    persisted = GliaBrain(workspace=tmp_path)
    persisted.load()
    assert {
        f"concurrent decision {index}" for index in range(writers)
    }.issubset(persisted.substrate.glyphs)


def test_recall_is_read_only_unless_adaptation_is_explicit(tmp_path):
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    brain.learn_offline(
        content="",
        concepts=["authentication session", "session token"],
        relationships=[],
        summary="Authentication sessions use session tokens.",
        source="auth decision",
    )
    revision_before = brain.stats()["revision"]
    activations_before = {
        glyph.id: glyph.activation_count for glyph in brain.substrate.glyphs.values()
    }

    recalled = brain.recall("authentication session token", top_k=2)

    assert recalled["adapted"] is False
    assert brain.stats()["revision"] == revision_before
    assert {
        glyph.id: glyph.activation_count for glyph in brain.substrate.glyphs.values()
    } == activations_before

    adapted = brain.recall("authentication session token", top_k=2, adapt=True)

    assert adapted["adapted"] is True
    assert brain.stats()["revision"] == revision_before + 1
    assert any(
        glyph.activation_count > activations_before[glyph.id]
        for glyph in brain.substrate.glyphs.values()
    )


def test_inconsistent_region_superposition_is_reported(tmp_path):
    storage = make_storage(tmp_path)
    substrate = Substrate()
    substrate.store_glyph("consistent", encode_identifier("consistent"))
    storage.save_substrate(substrate, expected_revision=0)
    storage.conn.execute(
        "UPDATE substrate_regions SET vector = ? WHERE id = 'default'",
        (np.zeros(substrate.dimension, dtype=np.float64).tobytes(),),
    )
    storage.conn.commit()

    with pytest.raises(StorageCorruptionError, match="inconsistent"):
        storage.load_substrate()


def test_health_check_and_backup_produce_readable_snapshot(tmp_path):
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    brain.learn_offline(
        content="",
        concepts=["durable backup"],
        relationships=[],
        summary="Backups contain a consistent committed snapshot.",
    )

    health = brain.health(deep=True)
    backup_path = brain.backup(tmp_path / "backups" / "memory.db")

    assert health["status"] == "ok"
    assert health["details"] == ["ok"]
    assert backup_path.exists()
    connection = sqlite3.connect(backup_path)
    try:
        count = connection.execute("SELECT COUNT(*) FROM glyphs").fetchone()[0]
        check = connection.execute("PRAGMA quick_check").fetchone()[0]
    finally:
        connection.close()
    assert count == 1
    assert check == "ok"


def test_adaptive_recall_handles_results_from_multiple_regions(tmp_path):
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    brain.load()
    brain.substrate.store_glyph(
        "region one memory",
        encode_identifier("shared regional memory"),
        region_id="region-one",
    )
    brain.substrate.store_glyph(
        "region two memory",
        encode_identifier("shared regional memory"),
        region_id="region-two",
    )
    brain.save()
    revision = brain.stats()["revision"]

    result = brain.recall("shared regional memory", top_k=2, adapt=True)

    assert result["adapted"] is True
    assert brain.stats()["revision"] == revision + 1
    assert all(glyph.activation_count == 1 for glyph in brain.substrate.glyphs.values())


def test_learn_extracts_once_when_commit_requires_retry(tmp_path, monkeypatch):
    from glia.distiller import Distiller

    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    brain.load()
    calls = 0

    def extract_once(self, content, substrate, source=""):
        nonlocal calls
        calls += 1
        concurrent = GliaBrain(workspace=tmp_path)
        concurrent.learn_offline(
            content="",
            concepts=["concurrent knowledge"],
            relationships=[],
            summary="Committed while distillation was in flight.",
        )
        return {
            "units": [
                {
                    "concept": "distilled knowledge",
                    "intention": "Applied deterministically after a retry.",
                    "relationships": [],
                }
            ]
        }

    monkeypatch.setattr(Distiller, "extract", extract_once)
    brain.learn("knowledge", source="test")

    assert calls == 1
    brain.load(force=True)
    assert {"concurrent knowledge", "distilled knowledge"}.issubset(
        brain.substrate.glyphs
    )


def test_automatic_backup_names_are_unique(tmp_path):
    brain = GliaBrain(workspace=tmp_path)
    brain.init()

    first = brain.backup()
    second = brain.backup()

    assert first != second
    assert first.exists()
    assert second.exists()


def test_incremental_save_writes_only_dirty_rows_and_load_is_clean(tmp_path):
    storage = make_storage(tmp_path)
    substrate = Substrate()
    for index in range(25):
        substrate.store_glyph(
            f"concept-{index}",
            encode_identifier(f"concept-{index}"),
        )

    revision = storage.save_substrate(substrate, expected_revision=0)
    assert storage.last_save_stats["glyphs_upserted"] == 25
    assert substrate.dirty_snapshot().glyphs == frozenset()

    loaded, loaded_revision = storage.load_substrate_versioned()
    assert loaded_revision == revision
    assert loaded.dirty_snapshot().glyphs == frozenset()
    with pytest.raises(AttributeError, match="Substrate mutation APIs"):
        loaded.glyphs["concept-7"].magnitude = 1.25
    loaded.set_glyph_magnitude(loaded.glyphs["concept-7"], 1.25)
    storage.save_substrate(loaded, expected_revision=loaded_revision)

    assert storage.last_save_stats == {
        "regions_upserted": 1,
        "glyphs_upserted": 1,
        "relationships_upserted": 0,
        "regions_deleted": 0,
        "glyphs_deleted": 0,
        "relationships_deleted": 0,
    }


def test_conflict_does_not_clear_pending_deltas(tmp_path):
    first = make_storage(tmp_path)
    second = SQLiteStorage(tmp_path / ".glia")
    first_snapshot, first_revision = first.load_substrate_versioned()
    stale_snapshot, stale_revision = second.load_substrate_versioned()

    first_snapshot.store_glyph("winner", encode_identifier("winner"))
    first.save_substrate(first_snapshot, expected_revision=first_revision)
    stale_snapshot.store_glyph("still-dirty", encode_identifier("still-dirty"))
    pending = stale_snapshot.dirty_snapshot()

    with pytest.raises(StorageConflictError):
        second.save_substrate(stale_snapshot, expected_revision=stale_revision)

    assert stale_snapshot.dirty_snapshot() == pending
    assert "still-dirty" in stale_snapshot.dirty_snapshot().glyphs


def test_transient_sqlite_busy_is_retried(tmp_path):
    from threading import Event, Thread
    import time

    storage = make_storage(tmp_path)
    storage.conn.execute("PRAGMA busy_timeout=1")
    substrate, revision = storage.load_substrate_versioned()
    substrate.store_glyph("after-lock", encode_identifier("after-lock"))
    locked = Event()
    release = Event()

    def hold_write_lock():
        connection = sqlite3.connect(storage.db_path, timeout=0.001)
        connection.execute("PRAGMA busy_timeout=1")
        connection.execute("BEGIN IMMEDIATE")
        locked.set()
        release.wait(timeout=1)
        connection.execute("COMMIT")
        connection.close()

    holder = Thread(target=hold_write_lock)
    holder.start()
    assert locked.wait(timeout=1)

    def release_shortly():
        time.sleep(0.03)
        release.set()

    releaser = Thread(target=release_shortly)
    releaser.start()
    committed = storage.save_substrate(substrate, expected_revision=revision)
    holder.join(timeout=1)
    releaser.join(timeout=1)

    assert committed == revision + 1
    assert storage.load_substrate().glyphs["after-lock"].id == "after-lock"
