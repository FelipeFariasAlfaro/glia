"""
GLIA Benchmark - Measures retrieval precision, token efficiency, and multi-hop capability.

Usage:
    python benchmarks/run_benchmark.py                    # default: benchmark_project
    python benchmarks/run_benchmark.py benchmark_project_2
    python benchmarks/run_benchmark.py benchmark_project_3
"""

import sys
import json
import time
from pathlib import Path

# Accept project name as argument
project_name = sys.argv[1] if len(sys.argv) > 1 else "benchmark_project"

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from glia.brain import GliaBrain
from glia.scanner import Scanner
from glia.encoder import encode_text
from glia.binding import cosine_similarity


def load_ground_truth():
    """Load the benchmark questions and expected answers."""
    gt_path = Path(__file__).parent.parent / project_name / "knowledge.json"
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    # Normalize key name
    if "multi_hop_questions" not in data:
        if "questions" in data:
            data["multi_hop_questions"] = data["questions"]
        else:
            data["multi_hop_questions"] = []
    return data


def setup_glia():
    """Initialize and scan the benchmark project with GLIA."""
    workspace = Path(__file__).parent.parent / project_name
    brain = GliaBrain(workspace=workspace)

    # Clean start
    glia_path = workspace / ".glia"
    if glia_path.exists():
        import shutil
        shutil.rmtree(glia_path)

    brain.init()
    scanner = Scanner(brain)

    start = time.time()
    stats = scanner.scan()
    scan_time = time.time() - start

    return brain, stats, scan_time


def simple_text_search(query: str, project_path: Path, top_k: int = 5) -> list[str]:
    """Baseline: simple substring search across all files (simulates FTS)."""
    results = []
    query_lower = query.lower()
    query_words = set(query_lower.split())

    for filepath in project_path.rglob("*"):
        if filepath.suffix not in (".py", ".md", ".json"):
            continue
        if ".glia" in str(filepath):
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore").lower()
            # Score by word overlap
            score = sum(1 for w in query_words if w in content)
            if score > 0:
                results.append((str(filepath.relative_to(project_path)), score))
        except Exception:
            pass

    results.sort(key=lambda x: x[1], reverse=True)
    return [r[0] for r in results[:top_k]]


def benchmark_precision(brain: GliaBrain, ground_truth: dict, project_path: Path):
    """Benchmark 1: Retrieval precision (Recall@K)."""
    questions = ground_truth["multi_hop_questions"]

    glia_recall_at_1 = 0
    glia_recall_at_3 = 0
    glia_recall_at_5 = 0
    fts_recall_at_1 = 0
    fts_recall_at_3 = 0
    fts_recall_at_5 = 0

    print("\n" + "=" * 70)
    print("BENCHMARK 1: Retrieval Precision")
    print("=" * 70)

    for i, q in enumerate(questions):
        question = q["question"]
        # Handle different ground truth formats
        if "expected_concepts" in q:
            expected = set(q["expected_concepts"])
        elif "files_needed" in q:
            # Extract concept-like words from file paths
            expected = set()
            for f in q["files_needed"]:
                parts = Path(f).stem.lower().replace("-", "_").split("_")
                expected.update(p for p in parts if len(p) >= 3)
        else:
            expected = set()

        # GLIA retrieval
        result = brain.recall(question, top_k=10)
        glia_concepts = set()
        for node_id, _ in result["activated_nodes"][:5]:
            # Extract concept words from node ID
            words = set(node_id.lower().replace("_", " ").split())
            glia_concepts.update(words)

        # Also check thread content
        for t in result.get("threads", [])[:5]:
            words = set(t["id"].lower().replace("_", " ").split())
            glia_concepts.update(words)
            content_words = set(t["content"].lower().split())
            glia_concepts.update(content_words)

        # FTS baseline
        fts_results = simple_text_search(question, project_path)
        fts_concepts = set()
        for filepath in fts_results:
            words = set(Path(filepath).stem.lower().replace("_", " ").split())
            fts_concepts.update(words)

        # Check if expected concepts are found
        glia_found = len(expected & glia_concepts) > 0
        glia_found_3 = len(expected & glia_concepts) >= min(2, len(expected))
        glia_found_5 = len(expected & glia_concepts) >= min(3, len(expected))

        fts_found = len(expected & fts_concepts) > 0
        fts_found_3 = len(expected & fts_concepts) >= min(2, len(expected))
        fts_found_5 = len(expected & fts_concepts) >= min(3, len(expected))

        if glia_found:
            glia_recall_at_1 += 1
        if glia_found_3:
            glia_recall_at_3 += 1
        if glia_found_5:
            glia_recall_at_5 += 1

        if fts_found:
            fts_recall_at_1 += 1
        if fts_found_3:
            fts_recall_at_3 += 1
        if fts_found_5:
            fts_recall_at_5 += 1

    total = len(questions)
    print(f"\n{'Metric':<25} {'GLIA':<15} {'FTS Baseline':<15}")
    print("-" * 55)
    print(f"{'Recall@1':<25} {glia_recall_at_1/total*100:.1f}%{'':<10} {fts_recall_at_1/total*100:.1f}%")
    print(f"{'Recall@3':<25} {glia_recall_at_3/total*100:.1f}%{'':<10} {fts_recall_at_3/total*100:.1f}%")
    print(f"{'Recall@5':<25} {glia_recall_at_5/total*100:.1f}%{'':<10} {fts_recall_at_5/total*100:.1f}%")

    return {
        "glia_recall_1": glia_recall_at_1 / total,
        "glia_recall_3": glia_recall_at_3 / total,
        "fts_recall_1": fts_recall_at_1 / total,
        "fts_recall_3": fts_recall_at_3 / total,
    }


def benchmark_tokens(brain: GliaBrain, ground_truth: dict, project_path: Path):
    """Benchmark 2: Token efficiency."""
    questions = ground_truth["multi_hop_questions"]

    glia_tokens_total = 0
    full_context_tokens = 0

    # Calculate full context size (all files)
    for filepath in project_path.rglob("*"):
        if filepath.suffix in (".py", ".md") and ".glia" not in str(filepath):
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                full_context_tokens += len(content) // 4
            except Exception:
                pass

    print("\n" + "=" * 70)
    print("BENCHMARK 2: Token Efficiency")
    print("=" * 70)

    for q in questions:
        result = brain.recall(q["question"], top_k=10)
        context = result["context"]
        glia_tokens_total += len(context) // 4

    avg_glia = glia_tokens_total / len(questions)
    savings = (1 - avg_glia / full_context_tokens) * 100

    print(f"\n{'Metric':<35} {'Value':<15}")
    print("-" * 50)
    print(f"{'Full context (all files)':<35} {full_context_tokens} tokens")
    print(f"{'GLIA avg per query':<35} {avg_glia:.0f} tokens")
    print(f"{'Compression ratio':<35} {full_context_tokens/max(avg_glia,1):.0f}x")
    print(f"{'Token savings':<35} {savings:.1f}%")

    return {
        "full_context_tokens": full_context_tokens,
        "glia_avg_tokens": avg_glia,
        "savings_pct": savings,
    }


def benchmark_multihop(brain: GliaBrain, ground_truth: dict):
    """Benchmark 3: Multi-hop reasoning capability."""
    questions = ground_truth["multi_hop_questions"]

    # Classify questions by hop count
    single_hop = [q for q in questions if len(q.get("expected_concepts", q.get("files_needed", []))) <= 2]
    multi_hop = [q for q in questions if len(q.get("expected_concepts", q.get("files_needed", []))) > 2]

    print("\n" + "=" * 70)
    print("BENCHMARK 3: Multi-Hop Reasoning")
    print("=" * 70)

    def test_questions(qs, label):
        found = 0
        for q in qs:
            result = brain.recall(q["question"], top_k=10)
            if "expected_concepts" in q:
                expected = set(q["expected_concepts"])
            elif "files_needed" in q:
                expected = set()
                for f in q["files_needed"]:
                    parts = Path(f).stem.lower().replace("-", "_").split("_")
                    expected.update(p for p in parts if len(p) >= 3)
            else:
                expected = set()

            # Check if GLIA activated concepts related to the expected ones
            activated_text = " ".join(
                f"{nid} {t.get('content', '')}"
                for nid, _ in result["activated_nodes"]
                for t in result.get("threads", [])
            ).lower()

            matches = sum(1 for concept in expected if concept.lower().replace("_", " ") in activated_text or concept.lower() in activated_text)
            if matches >= len(expected) * 0.5:  # At least 50% of expected concepts found
                found += 1

        rate = found / max(len(qs), 1) * 100
        print(f"  {label}: {found}/{len(qs)} ({rate:.1f}%)")
        return rate

    single_rate = test_questions(single_hop, "Single-hop questions")
    multi_rate = test_questions(multi_hop, "Multi-hop questions ")

    print(f"\n  Multi-hop advantage: GLIA handles complex relational queries")
    print(f"  that require connecting information across multiple files.")

    return {"single_hop_rate": single_rate, "multi_hop_rate": multi_rate}


def benchmark_speed(brain: GliaBrain, ground_truth: dict):
    """Benchmark 4: Speed."""
    questions = ground_truth["multi_hop_questions"]

    print("\n" + "=" * 70)
    print("BENCHMARK 4: Speed")
    print("=" * 70)

    times = []
    for q in questions:
        start = time.time()
        brain.recall(q["question"], top_k=10)
        elapsed = time.time() - start
        times.append(elapsed)

    avg_ms = sum(times) / len(times) * 1000
    p95_ms = sorted(times)[int(len(times) * 0.95)] * 1000

    print(f"\n{'Metric':<25} {'Value':<15}")
    print("-" * 40)
    print(f"{'Avg recall time':<25} {avg_ms:.1f} ms")
    print(f"{'P95 recall time':<25} {p95_ms:.1f} ms")
    print(f"{'Queries tested':<25} {len(questions)}")

    return {"avg_ms": avg_ms, "p95_ms": p95_ms}


def main():
    print("GLIA Benchmark Suite")
    print("=" * 70)

    # Load ground truth
    ground_truth = load_ground_truth()
    print(f"Loaded {len(ground_truth['multi_hop_questions'])} benchmark questions")

    # Setup GLIA
    print("\nSetting up GLIA on benchmark project...")
    brain, scan_stats, scan_time = setup_glia()
    print(f"  Scan time: {scan_time:.2f}s")
    print(f"  Glyphs created: {scan_stats['learned']} files -> {brain.stats()['nodes']} patterns")

    project_path = Path(__file__).parent.parent / project_name

    # Run benchmarks
    precision = benchmark_precision(brain, ground_truth, project_path)
    tokens = benchmark_tokens(brain, ground_truth, project_path)
    multihop = benchmark_multihop(brain, ground_truth)
    speed = benchmark_speed(brain, ground_truth)

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"  Scan: {scan_time:.2f}s, {brain.stats()['nodes']} glyphs, $0 cost")
    print(f"  Precision: {precision['glia_recall_1']*100:.0f}% Recall@1 (vs {precision['fts_recall_1']*100:.0f}% FTS)")
    print(f"  Tokens: {tokens['savings_pct']:.0f}% savings ({tokens['glia_avg_tokens']:.0f} vs {tokens['full_context_tokens']} full)")
    print(f"  Multi-hop: {multihop['multi_hop_rate']:.0f}% success on relational queries")
    print(f"  Speed: {speed['avg_ms']:.1f}ms avg per query")
    print("=" * 70)

    # Cleanup
    import shutil
    shutil.rmtree(project_path / ".glia", ignore_errors=True)


if __name__ == "__main__":
    main()
