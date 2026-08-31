"""Reproducible local benchmark for GLIA phase 2.

Compares retrieval quality against dependency-free lexical baselines and
measures persistence/query scaling. The benchmark never modifies fixtures.

Usage:
    python benchmarks/benchmark_phase2.py
    python benchmarks/benchmark_phase2.py --projects benchmark_project
    python benchmarks/benchmark_phase2.py --sizes 100 500 1000
"""

from __future__ import annotations

import argparse
import json
import math
import re
import shutil
import sqlite3
import statistics
import sys
import tempfile
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
QRELS_PATH = Path(__file__).resolve().parent / "qrels_phase2.json"
CURATED_QRELS = json.loads(QRELS_PATH.read_text(encoding="utf-8"))
sys.path.insert(0, str(ROOT / "src"))

from glia.brain import GliaBrain
from glia.encoder import encode_text
from glia.resonance import resonate, resolve_query
from glia.scanner import Scanner

SCANNED_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".md", ".txt"}
TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    return [token for token in TOKEN_RE.findall(text.lower()) if len(token) >= 2]


@dataclass(frozen=True)
class Document:
    id: str
    source: str
    text: str


class BM25Index:
    """Small, correct Okapi BM25 baseline with corpus-derived IDF."""

    def __init__(self, documents: list[Document], k1: float = 1.5, b: float = 0.75):
        self.documents = documents
        self.k1 = k1
        self.b = b
        self.tokens = [tokenize(document.text) for document in documents]
        self.term_frequencies = [Counter(tokens) for tokens in self.tokens]
        self.avg_length = (
            sum(len(tokens) for tokens in self.tokens) / max(len(self.tokens), 1)
        )
        self.document_frequency: Counter[str] = Counter()
        for tokens in self.tokens:
            self.document_frequency.update(set(tokens))

    def query(self, text: str, top_k: int = 10) -> list[Document]:
        query_tokens = set(tokenize(text))
        count = len(self.documents)
        scored: list[tuple[float, Document]] = []
        for document, frequencies, tokens in zip(
            self.documents, self.term_frequencies, self.tokens
        ):
            score = 0.0
            length = len(tokens)
            for token in query_tokens:
                frequency = frequencies[token]
                if not frequency:
                    continue
                document_frequency = self.document_frequency[token]
                inverse_frequency = math.log(
                    1.0 + (count - document_frequency + 0.5) / (document_frequency + 0.5)
                )
                denominator = frequency + self.k1 * (
                    1.0 - self.b + self.b * length / max(self.avg_length, 1.0)
                )
                score += inverse_frequency * frequency * (self.k1 + 1.0) / denominator
            if score > 0:
                scored.append((score, document))
        scored.sort(key=lambda item: item[0], reverse=True)
        return unique_sources([document for _, document in scored], top_k)


class FTS5Index:
    """SQLite FTS5 baseline using the SQLite bundled with the runtime."""

    def __init__(self, documents: list[Document]):
        self.connection = sqlite3.connect(":memory:")
        try:
            self.connection.execute(
                "CREATE VIRTUAL TABLE documents USING fts5(id UNINDEXED, source UNINDEXED, text)"
            )
        except sqlite3.OperationalError as error:
            self.connection.close()
            raise RuntimeError("SQLite runtime does not provide FTS5") from error
        self.connection.executemany(
            "INSERT INTO documents (id, source, text) VALUES (?, ?, ?)",
            [(document.id, document.source, document.text) for document in documents],
        )

    def query(self, text: str, top_k: int = 10) -> list[Document]:
        tokens = list(dict.fromkeys(tokenize(text)))
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens)
        rows = self.connection.execute(
            "SELECT id, source, text FROM documents "
            "WHERE documents MATCH ? ORDER BY bm25(documents) LIMIT ?",
            (expression, max(top_k * 5, top_k)),
        )
        return unique_sources(
            [Document(id=row[0], source=row[1], text=row[2]) for row in rows],
            top_k,
        )

    def close(self) -> None:
        self.connection.close()


def unique_sources(documents: list[Document], top_k: int) -> list[Document]:
    unique: list[Document] = []
    seen: set[str] = set()
    for document in documents:
        key = document.source or document.id
        if key in seen:
            continue
        seen.add(key)
        unique.append(document)
        if len(unique) >= top_k:
            break
    return unique


def collect_documents(project: Path, chunk_size: int = 700) -> list[Document]:
    documents: list[Document] = []
    for filepath in sorted(project.rglob("*")):
        if not filepath.is_file() or filepath.suffix.lower() not in SCANNED_SUFFIXES:
            continue
        if ".glia" in filepath.parts or filepath.name == "knowledge.json":
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        source = filepath.relative_to(project).as_posix()
        for offset in range(0, max(len(content), 1), chunk_size):
            chunk = content[offset:offset + chunk_size]
            if not chunk.strip():
                continue
            documents.append(
                Document(
                    id=f"{source}:{offset}",
                    source=source,
                    text=f"{source}\n{chunk}",
                )
            )
    return documents


def expected_for(question: dict) -> tuple[set[str], set[str]]:
    concepts = {str(value).lower() for value in question.get("expected_concepts", [])}
    files = {
        Path(value).as_posix().lower()
        for key in ("source_files", "files_needed")
        for value in question.get(key, [])
    }
    return concepts, files


def source_qrels(
    project_name: str,
    question: str,
    files: set[str],
) -> set[str]:
    """Load method-independent, versioned relevance judgments by source."""
    values = files or set(CURATED_QRELS.get(project_name, {}).get(question, []))
    if not values:
        raise ValueError(
            f"No source qrels for {project_name!r}: {question!r}. "
            "Add reviewed judgments to the fixture or qrels_phase2.json."
        )
    return {source.lower().replace("\\", "/") for source in values}


def is_relevant(document: Document, qrels: set[str]) -> bool:
    return document.source.lower().replace("\\", "/") in qrels


def glyph_documents(results) -> list[Document]:
    return unique_sources(
        [
            Document(id=glyph.id, source=glyph.source, text=glyph.content)
            for glyph, _ in results
        ],
        top_k=10,
    )


def reciprocal_rank(relevance: list[bool]) -> float:
    for index, relevant in enumerate(relevance, start=1):
        if relevant:
            return 1.0 / index
    return 0.0


def ndcg(relevance: list[bool], total_relevant: int, k: int = 10) -> float:
    gain = sum(
        (1.0 if relevant else 0.0) / math.log2(index + 2)
        for index, relevant in enumerate(relevance[:k])
    )
    ideal = sum(
        1.0 / math.log2(index + 2)
        for index in range(min(max(total_relevant, 1), k))
    )
    return gain / ideal if ideal else 0.0


def percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    index = min(len(ordered) - 1, math.ceil(len(ordered) * fraction) - 1)
    return ordered[index]


def summarize_method(rows: list[dict]) -> dict:
    return {
        "mrr": statistics.fmean(row["rr"] for row in rows),
        "ndcg@10": statistics.fmean(row["ndcg"] for row in rows),
        "precision@1": statistics.fmean(row["p1"] for row in rows),
        "latency_p50_ms": percentile([row["latency_ms"] for row in rows], 0.50),
        "latency_p95_ms": percentile([row["latency_ms"] for row in rows], 0.95),
    }


def retrieval_benchmark(project_name: str, top_k: int = 10) -> dict:
    fixture = ROOT / project_name
    ground_truth = json.loads((fixture / "knowledge.json").read_text(encoding="utf-8"))
    questions = ground_truth.get("multi_hop_questions", ground_truth.get("questions", []))

    with tempfile.TemporaryDirectory(prefix="glia-benchmark-") as temporary:
        workspace = Path(temporary) / project_name
        shutil.copytree(fixture, workspace, ignore=shutil.ignore_patterns(".glia", "__pycache__"))
        brain = GliaBrain(workspace=workspace, api_key=None)
        brain.init()
        scan_start = time.perf_counter()
        Scanner(brain).scan()
        scan_ms = (time.perf_counter() - scan_start) * 1000

        chunks = collect_documents(workspace)
        bm25 = BM25Index(chunks)
        try:
            fts5: FTS5Index | None = FTS5Index(chunks)
        except RuntimeError:
            fts5 = None

        method_rows: dict[str, list[dict]] = {
            "glia_stable": [],
            "glia_multihop": [],
            "hdm_direct": [],
            "bm25": [],
        }
        if fts5 is not None:
            method_rows["fts5"] = []

        glyphs = brain.substrate.get_all_glyphs()
        for question in questions:
            query = question["question"]
            _concepts, files = expected_for(question)
            qrels = source_qrels(project_name, query, files)
            total_relevant = max(len(qrels), 1)

            started = time.perf_counter()
            documents = glyph_documents(
                resolve_query(
                    query,
                    brain.substrate,
                    top_k=top_k,
                    embedder=None,
                    explore=False,
                )
            )
            elapsed = (time.perf_counter() - started) * 1000
            record_result(
                method_rows["glia_stable"],
                documents,
                qrels,
                total_relevant,
                elapsed,
            )

            started = time.perf_counter()
            documents = glyph_documents(
                resolve_query(
                    query,
                    brain.substrate,
                    top_k=top_k,
                    embedder=None,
                    explore=True,
                )
            )
            elapsed = (time.perf_counter() - started) * 1000
            record_result(
                method_rows["glia_multihop"],
                documents,
                qrels,
                total_relevant,
                elapsed,
            )

            started = time.perf_counter()
            documents = glyph_documents(
                resonate(encode_text(query), glyphs, top_k=max(top_k * 5, top_k))
            )
            elapsed = (time.perf_counter() - started) * 1000
            record_result(method_rows["hdm_direct"], documents, qrels, total_relevant, elapsed)

            started = time.perf_counter()
            documents = bm25.query(query, top_k=top_k)
            elapsed = (time.perf_counter() - started) * 1000
            record_result(method_rows["bm25"], documents, qrels, total_relevant, elapsed)

            if fts5 is not None:
                started = time.perf_counter()
                documents = fts5.query(query, top_k=top_k)
                elapsed = (time.perf_counter() - started) * 1000
                record_result(method_rows["fts5"], documents, qrels, total_relevant, elapsed)

        if fts5 is not None:
            fts5.close()
        if brain._storage is not None:
            brain._storage.close()

    return {
        "project": project_name,
        "questions": len(questions),
        "documents": len(chunks),
        "glyphs": len(glyphs),
        "scan_ms": scan_ms,
        "methods": {
            method: summarize_method(rows) for method, rows in method_rows.items()
        },
    }


def record_result(
    rows: list[dict],
    documents: list[Document],
    qrels: set[str],
    total_relevant: int,
    latency_ms: float,
) -> None:
    relevance = [is_relevant(document, qrels) for document in documents]
    rows.append(
        {
            "rr": reciprocal_rank(relevance),
            "ndcg": ndcg(relevance, total_relevant),
            "p1": float(bool(relevance and relevance[0])),
            "latency_ms": latency_ms,
        }
    )


def scalability_benchmark(sizes: list[int], query_count: int = 10) -> list[dict]:
    results = []
    for size in sizes:
        with tempfile.TemporaryDirectory(prefix="glia-scale-") as temporary:
            workspace = Path(temporary)
            brain = GliaBrain(workspace=workspace, api_key=None)
            brain.init()
            for index in range(size):
                brain.substrate.store_glyph(
                    f"concept_{index}",
                    encode_text(f"concept {index} service behavior"),
                    content=f"Service behavior and decision number {index}",
                    source=f"src/service_{index}.py",
                )

            started = time.perf_counter()
            brain.save()
            save_ms = (time.perf_counter() - started) * 1000

            loaded = GliaBrain(workspace=workspace, api_key=None)
            started = time.perf_counter()
            loaded.load()
            load_ms = (time.perf_counter() - started) * 1000

            started = time.perf_counter()
            resolve_query(
                "service behavior 0", loaded.substrate, top_k=10, embedder=None
            )
            cold_query_ms = (time.perf_counter() - started) * 1000

            for index in range(min(3, query_count)):
                loaded.recall(f"service behavior {index}", top_k=10)

            pure_latencies = []
            for index in range(query_count):
                started = time.perf_counter()
                resolve_query(
                    f"service behavior {index}", loaded.substrate, top_k=10, embedder=None
                )
                pure_latencies.append((time.perf_counter() - started) * 1000)

            recall_latencies = []
            for index in range(query_count):
                started = time.perf_counter()
                loaded.recall(f"service behavior {index}", top_k=10)
                recall_latencies.append((time.perf_counter() - started) * 1000)

            adaptive_latencies = []
            for index in range(query_count):
                started = time.perf_counter()
                loaded.recall(
                    f"service behavior {index}", top_k=10, adapt=True
                )
                adaptive_latencies.append((time.perf_counter() - started) * 1000)

            target = loaded.substrate.glyphs["concept_0"]
            loaded.substrate.set_glyph_magnitude(
                target, min(2.0, target.magnitude + 0.001)
            )
            started = time.perf_counter()
            loaded.save()
            incremental_save_ms = (time.perf_counter() - started) * 1000
            assert loaded._storage is not None
            incremental_rows = dict(loaded._storage.last_save_stats)

            database_path = workspace / ".glia" / "memory.db"
            database_size = sum(
                path.stat().st_size
                for path in (
                    database_path,
                    database_path.with_name("memory.db-wal"),
                    database_path.with_name("memory.db-shm"),
                )
                if path.exists()
            )
            results.append(
                {
                    "glyphs": size,
                    "save_ms": save_ms,
                    "load_ms": load_ms,
                    "cold_query_ms": cold_query_ms,
                    "query_p50_ms": percentile(pure_latencies, 0.50),
                    "recall_p50_ms": percentile(recall_latencies, 0.50),
                    "adaptive_recall_p50_ms": percentile(adaptive_latencies, 0.50),
                    "incremental_save_ms": incremental_save_ms,
                    "incremental_rows": incremental_rows,
                    "database_kib": database_size / 1024,
                }
            )
            if loaded._storage is not None:
                loaded._storage.close()
            if brain._storage is not None:
                brain._storage.close()
    return results


def print_report(retrieval: list[dict], scalability: list[dict]) -> None:
    print("\nRETRIEVAL QUALITY (source-deduplicated, local-only)")
    for project in retrieval:
        print(
            f"\n{project['project']}: {project['questions']} queries, "
            f"{project['documents']} chunks, scan {project['scan_ms']:.1f} ms"
        )
        print(f"{'method':<18} {'MRR':>7} {'nDCG@10':>10} {'P@1':>7} {'p50 ms':>9} {'p95 ms':>9}")
        for method, metrics in project["methods"].items():
            print(
                f"{method:<18} {metrics['mrr']:>7.3f} {metrics['ndcg@10']:>10.3f} "
                f"{metrics['precision@1']:>7.3f} {metrics['latency_p50_ms']:>9.2f} "
                f"{metrics['latency_p95_ms']:>9.2f}"
            )

    print("\nSCALABILITY (median of local queries; cold cache measured once)")
    print(
        f"{'glyphs':>8} {'full save':>10} {'delta save':>11} {'load ms':>10} "
        f"{'cold ms':>10} {'warm ms':>10} {'recall ms':>11} {'adapt ms':>10} "
        f"{'delta rows':>12} {'DB+WAL KiB':>12}"
    )
    for row in scalability:
        delta_rows = row["incremental_rows"]
        changed = (
            delta_rows["regions_upserted"]
            + delta_rows["glyphs_upserted"]
            + delta_rows["relationships_upserted"]
            + delta_rows["regions_deleted"]
            + delta_rows["glyphs_deleted"]
            + delta_rows["relationships_deleted"]
        )
        print(
            f"{row['glyphs']:>8} {row['save_ms']:>10.2f} "
            f"{row['incremental_save_ms']:>11.2f} {row['load_ms']:>10.2f} "
            f"{row['cold_query_ms']:>10.2f} {row['query_p50_ms']:>10.2f} "
            f"{row['recall_p50_ms']:>11.2f} "
            f"{row['adaptive_recall_p50_ms']:>10.2f} {changed:>12} "
            f"{row['database_kib']:>12.1f}"
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--projects",
        nargs="+",
        default=["benchmark_project", "benchmark_project_2", "benchmark_project_3"],
    )
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 1000, 5000])
    parser.add_argument("--query-count", type=int, default=10)
    parser.add_argument("--json", action="store_true", dest="as_json")
    arguments = parser.parse_args()

    retrieval = [retrieval_benchmark(project) for project in arguments.projects]
    scalability = scalability_benchmark(arguments.sizes, arguments.query_count)
    payload = {"retrieval": retrieval, "scalability": scalability}
    if arguments.as_json:
        print(json.dumps(payload, indent=2))
    else:
        print_report(retrieval, scalability)


if __name__ == "__main__":
    main()
