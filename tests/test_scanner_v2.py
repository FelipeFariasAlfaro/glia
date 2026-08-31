import numpy as np
import pytest

from glia.ast_scanner_v2 import ASTScannerV2
from glia.brain import GliaBrain
from glia.scanner import Scanner


def test_incremental_scan_file_uses_holographic_substrate(tmp_path):
    source = tmp_path / "auth_service.py"
    source.write_text(
        'class AuthService:\n    """Authenticates users."""\n\n    def login(self):\n        return True\n',
        encoding="utf-8",
    )
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)

    assert scanner.scan_file(source) is True
    assert scanner.scan_file(source) is False

    brain.load(force=True)
    glyph_ids = set(brain.substrate.glyphs)
    assert any("AuthService" in glyph_id for glyph_id in glyph_ids)
    assert any("login" in glyph_id for glyph_id in glyph_ids)


def test_sync_changes_updates_new_files_without_legacy_graph_attributes(tmp_path):
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    source = tmp_path / "payments.py"
    source.write_text("def charge_payment():\n    return 'ok'\n", encoding="utf-8")
    scanner = Scanner(brain)

    result = scanner.sync_changes()

    assert result["changed"] >= 1
    assert result["updated"] >= 1
    brain.load(force=True)
    assert any("charge_payment" in glyph_id for glyph_id in brain.substrate.glyphs)


def test_rescan_replaces_removed_symbols_and_relationships(tmp_path):
    source = tmp_path / "service.py"
    source.write_text("import os\n\ndef old_handler():\n    return os.getcwd()\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)

    assert scanner.scan_file(source) is True
    first_relationship_count = len(brain.substrate.relationships)
    assert any("old_handler" in glyph_id for glyph_id in brain.substrate.glyphs)

    source.write_text("import os\n\ndef new_handler():\n    return os.getcwd()\n", encoding="utf-8")
    assert scanner.scan_file(source) is True

    assert not any("old_handler" in glyph_id for glyph_id in brain.substrate.glyphs)
    assert any("new_handler" in glyph_id for glyph_id in brain.substrate.glyphs)
    assert len(brain.substrate.relationships) == first_relationship_count


def test_same_basename_in_different_directories_has_distinct_glyph_ids(tmp_path):
    first_file = tmp_path / "api" / "service.py"
    second_file = tmp_path / "worker" / "service.py"
    first_file.parent.mkdir()
    second_file.parent.mkdir()
    first_file.write_text("def run_api():\n    return True\n", encoding="utf-8")
    second_file.write_text("def run_worker():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)

    assert scanner.scan_file(first_file) is True
    assert scanner.scan_file(second_file) is True

    api_ids = {glyph.id for glyph in brain.substrate.glyphs.values() if glyph.source == "api/service.py"}
    worker_ids = {glyph.id for glyph in brain.substrate.glyphs.values() if glyph.source == "worker/service.py"}
    assert api_ids
    assert worker_ids
    assert api_ids.isdisjoint(worker_ids)
    assert any("run_api" in glyph_id for glyph_id in api_ids)
    assert any("run_worker" in glyph_id for glyph_id in worker_ids)


def test_incremental_scan_retries_after_concurrent_commit(tmp_path):
    initial = GliaBrain(workspace=tmp_path)
    initial.init()
    stale_brain = GliaBrain(workspace=tmp_path)
    stale_brain.load()
    scanner = Scanner(stale_brain)

    concurrent = GliaBrain(workspace=tmp_path)
    concurrent.load()
    concurrent.learn_offline(
        content="",
        concepts=["concurrent decision"],
        relationships=[],
        summary="Committed by another process.",
    )

    source = tmp_path / "retry.py"
    source.write_text("def retried_change():\n    return True\n", encoding="utf-8")
    assert scanner.scan_file(source) is True

    stale_brain.load(force=True)
    assert "concurrent decision" in stale_brain.substrate.glyphs
    assert any("retried_change" in glyph_id for glyph_id in stale_brain.substrate.glyphs)
    assert "retry.py" in scanner.scan_state


def test_failed_rescan_restores_previous_source_contributions(tmp_path):
    source = tmp_path / "atomic.py"
    source.write_text("def stable_symbol():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)
    assert scanner.scan_file(source) is True

    before_ids = set(brain.substrate.glyphs)
    before_region = brain.substrate.regions["default"].vector.copy()
    source.write_text("def replacement_symbol():\n    return True\n", encoding="utf-8")

    class BrokenEmbedder:
        is_available = True

        def embed(self, _text):
            raise RuntimeError("embedding unavailable")

    with pytest.raises(RuntimeError, match="embedding unavailable"):
        ASTScannerV2(embedder=BrokenEmbedder()).scan_file(
            source,
            brain.substrate,
            "atomic.py",
        )

    assert set(brain.substrate.glyphs) == before_ids
    assert not any("replacement_symbol" in glyph_id for glyph_id in brain.substrate.glyphs)
    np.testing.assert_allclose(brain.substrate.regions["default"].vector, before_region)


def test_scan_state_merges_concurrent_scanners_in_sqlite(tmp_path):
    initial = GliaBrain(workspace=tmp_path)
    initial.init()
    first_brain = GliaBrain(workspace=tmp_path)
    second_brain = GliaBrain(workspace=tmp_path)
    first_scanner = Scanner(first_brain)
    second_scanner = Scanner(second_brain)
    first_file = tmp_path / "first.py"
    second_file = tmp_path / "second.py"
    first_file.write_text("def first():\n    return 1\n", encoding="utf-8")
    second_file.write_text("def second():\n    return 2\n", encoding="utf-8")

    assert first_scanner.scan_file(first_file) is True
    assert second_scanner.scan_file(second_file) is True

    fresh_scanner = Scanner(GliaBrain(workspace=tmp_path))
    assert {"first.py", "second.py"}.issubset(fresh_scanner.scan_state)
    assert fresh_scanner.detect_changes() == []


def test_full_scan_retries_after_concurrent_commit(tmp_path):
    initial = GliaBrain(workspace=tmp_path)
    initial.init()
    stale_brain = GliaBrain(workspace=tmp_path)
    scanner = Scanner(stale_brain)

    concurrent = GliaBrain(workspace=tmp_path)
    concurrent.load()
    concurrent.learn_offline(
        content="",
        concepts=["parallel memory"],
        relationships=[],
        summary="Must survive a full scan retry.",
    )
    source = tmp_path / "full_scan.py"
    source.write_text("def full_scan_symbol():\n    return True\n", encoding="utf-8")

    result = scanner.scan()

    assert result["learned"] == 1
    stale_brain.load(force=True)
    assert "parallel memory" in stale_brain.substrate.glyphs
    assert any("full_scan_symbol" in glyph_id for glyph_id in stale_brain.substrate.glyphs)
    assert "full_scan.py" in stale_brain.load_scan_state()


def test_sync_removes_deleted_source_and_scan_state_atomically(tmp_path):
    source = tmp_path / "obsolete.py"
    source.write_text("def obsolete_symbol():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)
    assert scanner.scan_file(source) is True
    assert any(
        glyph.source == "obsolete.py" for glyph in brain.substrate.glyphs.values()
    )

    source.unlink()
    assert scanner.detect_changes() == ["obsolete.py"]
    result = scanner.sync_changes()

    assert result["removed"] == 1
    brain.load(force=True)
    assert not any(
        glyph.source == "obsolete.py" for glyph in brain.substrate.glyphs.values()
    )
    assert "obsolete.py" not in brain.load_scan_state()


def test_scan_state_hash_matches_bytes_that_were_parsed(tmp_path, monkeypatch):
    source = tmp_path / "racing.py"
    source.write_text("def original():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)
    original_scan = ASTScannerV2.scan_file

    def scan_then_change(self, filepath, substrate, relative_path=""):
        result = original_scan(self, filepath, substrate, relative_path)
        filepath.write_text("def changed_after_parse():\n    return True\n", encoding="utf-8")
        return result

    monkeypatch.setattr(ASTScannerV2, "scan_file", scan_then_change)
    assert scanner.scan_file(source) is True

    assert scanner.detect_changes() == ["racing.py"]


def test_sync_removes_file_that_becomes_ignored(tmp_path):
    source = tmp_path / "secret.py"
    source.write_text("def secret_symbol():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)
    assert scanner.scan_file(source) is True

    (tmp_path / ".gitignore").write_text("secret.py\n", encoding="utf-8")
    assert scanner.detect_changes() == ["secret.py"]
    result = scanner.sync_changes()

    assert result["removed"] == 1
    brain.load(force=True)
    assert not any(glyph.source == "secret.py" for glyph in brain.substrate.glyphs.values())
    assert "secret.py" not in brain.load_scan_state()


def test_failed_multi_file_sync_discards_all_uncommitted_changes(tmp_path, monkeypatch):
    first = tmp_path / "a.py"
    second = tmp_path / "b.py"
    first.write_text("def old_a():\n    return True\n", encoding="utf-8")
    second.write_text("def old_b():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)
    scanner.scan()

    first.write_text("def new_a():\n    return True\n", encoding="utf-8")
    second.write_text("def new_b():\n    return True\n", encoding="utf-8")
    original_scan = ASTScannerV2.scan_file

    def fail_after_second_parse(self, filepath, substrate, relative_path=""):
        result = original_scan(self, filepath, substrate, relative_path)
        if filepath.name == "b.py":
            raise RuntimeError("second file failed")
        return result

    monkeypatch.setattr(ASTScannerV2, "scan_file", fail_after_second_parse)
    with pytest.raises(RuntimeError, match="second file failed"):
        scanner.sync_changes()

    assert any("old_a" in glyph.id for glyph in brain.substrate.glyphs.values())
    assert any("old_b" in glyph.id for glyph in brain.substrate.glyphs.values())
    assert not any("new_a" in glyph.id for glyph in brain.substrate.glyphs.values())
    assert not any("new_b" in glyph.id for glyph in brain.substrate.glyphs.values())


def test_typescript_scanner_preserves_typed_arrow_context(tmp_path):
    source = tmp_path / "FeaturePanel.tsx"
    source.write_text(
        "// Renders advanced order filters when the v2 API flag is enabled\n"
        "interface FeaturePanelProps { enabled: boolean }\n"
        "export const FeaturePanel: React.FC<FeaturePanelProps> = ({ enabled }) => {\n"
        "  return enabled ? <div>advanced order filters</div> : null\n"
        "}\n",
        encoding="utf-8",
    )
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)

    assert scanner.scan_file(source) is True

    glyphs = [
        glyph for glyph in brain.substrate.glyphs.values()
        if glyph.source == "FeaturePanel.tsx"
    ]
    assert any("FeaturePanel" in glyph.id for glyph in glyphs)
    assert any("FeaturePanelProps" in glyph.id for glyph in glyphs)
    assert any("advanced order filters" in glyph.content for glyph in glyphs)


def test_failed_rescan_restores_dirty_tracking_generation(tmp_path):
    source = tmp_path / "tracked.py"
    source.write_text("def stable():\n    return True\n", encoding="utf-8")
    brain = GliaBrain(workspace=tmp_path)
    brain.init()
    scanner = Scanner(brain)
    assert scanner.scan_file(source) is True
    before = brain.substrate.tracking_checkpoint()
    before_snapshot = brain.substrate.resonance_snapshot()
    source.write_text("def replacement():\n    return True\n", encoding="utf-8")

    class BrokenEmbedder:
        is_available = True

        def embed(self, _text):
            raise RuntimeError("forced scanner failure")

    with pytest.raises(RuntimeError, match="forced scanner failure"):
        ASTScannerV2(embedder=BrokenEmbedder()).scan_file(
            source, brain.substrate, "tracked.py"
        )

    assert brain.substrate.dirty_snapshot() == before
    restored_snapshot = brain.substrate.resonance_snapshot()
    assert restored_snapshot.mutation_version == before_snapshot.mutation_version
    assert {glyph.id for glyph in restored_snapshot.glyphs} == {
        glyph.id for glyph in before_snapshot.glyphs
    }
