# Changelog

All notable changes to GLIA are documented in this file.

The next release is `0.4.0`. The `0.2.0a0` entry is retained as historical prerelease context.

## [0.4.0] - Unreleased

### Changed

- Promoted the public package metadata, runtime version, CLI version, and release documentation to the final `0.4.0` version.
- Prepared the distribution for a tag-only GitHub Actions release. The workflow validates the `v0.4.0` tag against `pyproject.toml`, builds source and wheel distributions, validates them with Twine, and publishes through PyPI Trusted Publishing.
- Preserved SQLite schema version `3` and all durable-storage contracts: this is a package release, not a database migration.

### Validation

- The release artifact will be built from the exact commit tagged `v0.4.0` and checked before publication.

## [0.2.0a0] - 2026-08-23

### Added

- Deterministic HDM core with reversible, identifiable relationship contributions.
- SQLite optimistic revision control for concurrent writers.
- Exact source reconciliation for incremental scanning, including deleted and newly ignored files.
- Stable read-only recall by default, plus explicit `adapt` and `explore` modes.
- Bounded and saturating Hebbian co-activation contributions.
- SQLite health checks, deep integrity checks, and atomic backups with unique names.
- CLI support for `recall --adapt`, `recall --explore`, `doctor`, and backups.
- Versioned relevance judgments in `benchmarks/qrels_phase2.json`.
- A reproducible local benchmark comparing GLIA, direct HDM, Okapi BM25, and SQLite FTS5.
- Dirty tracking for regions, glyphs, and relationship contributions.
- Immutable, cached resonance snapshots with warm-query reuse.
- Bounded retry for transient SQLite `BUSY` and `LOCKED` contention.
- Validation that managed glyphs, relationships, and regions cannot be mutated through normal public field assignment.

### Changed

- Replaced full-row persistence on every mutation with incremental upserts for dirty rows while retaining exact membership reconciliation for deletes.
- Validated holographic superposition before every persistent commit. Region vectors must equal weighted glyph contributions plus reversible relationships.
- Cleared dirty state only after a successful SQLite commit; failed or stale commits retain pending changes.
- Made glyph, relationship, and region vectors immutable byte-backed NumPy views to prevent in-place state corruption.
- Reworked plasticity to use substrate mutation APIs for magnitude and activation changes.
- Extended scanner rollback to restore tracking and invalidate cached resonance state after a failed file scan.
- Reused one vectorized index for stable and multihop resonance work within a query.
- Improved TypeScript/React extraction context and source-qualified scanner identities.
- Updated public documentation to describe HDM accurately and remove outdated graph and storage claims.

### Fixed

- Prevented stale writers from silently losing newer committed memory.
- Prevented repeated recall from persisting plasticity unless `adapt=True` is requested.
- Prevented anonymous and unbounded plasticity interference.
- Prevented removed source files from leaving glyph, relationship, or scan-state residue.
- Detected corrupted vector dimensions, non-finite values, invalid region references, inconsistent glyph counts, and invalid regional superposition.
- Preserved scanner atomicity when one file fails during a multi-file synchronization.
- Restored dirty tracking after a failed per-file scanner operation.
- Preserved dirty state when a version conflict rejects a save.
- Recovered from temporary SQLite write locks with bounded backoff.
- Prevented a non-canonical `GlyphMeta` object with a matching ID from altering a region.
- Prevented stale resonance cache reuse after supported mutations.

### Validation

- Test suite: 46 passing tests.
- Additional checks: `compileall`, `pip check`, `glia doctor --deep`, CLI help, and isolated MCP startup.
- Non-blocking environment warning: `google-genai` emits a Python 3.14 deprecation warning for `_UnionGenericAlias`.

### Benchmark snapshot

The final phase-3 local scalability run at 5,000 glyphs reported:

| Metric | Result |
|---|---:|
| Initial full save | 180.08 ms |
| Validated incremental save of one glyph | 26.26 ms |
| Incrementally upserted rows | 1 region and 1 glyph |
| Cold query | 32.13 ms |
| Warm cached query | 6.10 ms |
| Stable recall | 7.10 ms |
| Adaptive recall | 65.13 ms |
| SQLite database, WAL, and SHM footprint | 86,047 KiB |

Retrieval quality from the versioned benchmark:

| Fixture | GLIA stable MRR | BM25 MRR | FTS5 MRR |
|---|---:|---:|---:|
| Backend | 0.837 | 0.869 | 0.819 |
| ML | 0.802 | 0.837 | 0.829 |
| TypeScript/React | 0.776 | 0.819 | 0.819 |

BM25 and FTS5 remain lexical baselines. GLIA is maintained as a distinct HDM architecture focused on persistent resonance, reversible binding, source-aware scanning, and bounded plasticity.
