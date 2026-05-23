"""
GLIA Benchmark v2 — Industry-standard evaluation metrics.

Uses:
- tiktoken for REAL token counting (cl100k_base encoding)
- Standard IR metrics: MRR, nDCG@K, Precision@K, Recall@K
- Real USD cost calculation (Gemini Flash pricing)
- Latency percentiles (P50, P95, P99)

Usage:
    python benchmarks/run_benchmark_v2.py benchmark_project
    python benchmarks/run_benchmark_v2.py benchmark_project_2
    python benchmarks/run_benchmark_v2.py benchmark_project_3
"""

import sys
import json
import time
import math
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import tiktoken

from glia.brain import GliaBrain
from glia.scanner import Scanner

# Tiktoken encoder (cl100k_base = GPT-4, GPT-4o, similar to Gemini tokenization)
ENCODER = tiktoken.get_encoding("cl100k_base")

# Pricing (Gemini 2.0 Flash as of May 2026)
PRICE_PER_1M_INPUT_TOKENS = 0.10  # USD per 1M input tokens
PRICE_PER_1M_OUTPUT_TOKENS = 0.40  # USD per 1M output tokens

project_name = sys.argv[1] if len(sys.argv) > 1 else "benchmark_project"


def count_tokens(text: str) -> int:
    """Count tokens using tiktoken (real tokenizer, not approximation)."""
    return len(ENCODER.encode(text))


def load_ground_truth():
    gt_path = Path(__file__).parent.parent / project_name / "knowledge.json"
    data = json.loads(gt_path.read_text(encoding="utf-8"))
    if "multi_hop_questions" not in data:
        if "questions" in data:
            data["multi_hop_questions"] = data["questions"]
    return data


def get_expected_concepts(q: dict) -> set:
    """Extract expected concepts from question (handles different formats)."""
    if "expected_concepts" in q:
        return set(q["expected_concepts"])
    elif "files_needed" in q:
        expected = set()
        for f in q["files_needed"]:
            parts = Path(f).stem.lower().replace("-", "_").split("_")
            expected.update(p for p in parts if len(p) >= 3)
        return expected
    return set()


def setup_glia():
    workspace = Path(__file__).parent.parent / project_name
    brain = GliaBrain(workspace=workspace)

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


def compute_mrr(results_per_query: list[list[bool]]) -> float:
    """Mean Reciprocal Rank — standard IR metric."""
    reciprocal_ranks = []
    for results in results_per_query:
        for i, is_relevant in enumerate(results):
            if is_relevant:
                reciprocal_ranks.append(1.0 / (i + 1))
                break
        else:
            reciprocal_ranks.append(0.0)
    return sum(reciprocal_ranks) / max(len(reciprocal_ranks), 1)


def compute_ndcg(results_per_query: list[list[bool]], k: int = 10) -> float:
    """Normalized Discounted Cumulative Gain @ K."""
    ndcg_scores = []
    for results in results_per_query:
        # DCG
        dcg = sum(
            (1.0 if rel else 0.0) / math.log2(i + 2)
            for i, rel in enumerate(results[:k])
        )
        # Ideal DCG (all relevant items at top)
        n_relevant = sum(results[:k])
        idcg = sum(1.0 / math.log2(i + 2) for i in range(n_relevant))
        ndcg_scores.append(dcg / idcg if idcg > 0 else 0.0)
    return sum(ndcg_scores) / max(len(ndcg_scores), 1)


def compute_precision_at_k(results_per_query: list[list[bool]], k: int) -> float:
    """Precision@K — fraction of top-K results that are relevant."""
    precisions = []
    for results in results_per_query:
        top_k = results[:k]
        precisions.append(sum(top_k) / max(len(top_k), 1))
    return sum(precisions) / max(len(precisions), 1)


def compute_recall_at_k(results_per_query: list[list[bool]], k: int, total_relevant: list[int]) -> float:
    """Recall@K — fraction of relevant items found in top-K."""
    recalls = []
    for results, n_rel in zip(results_per_query, total_relevant):
        top_k = results[:k]
        recalls.append(sum(top_k) / max(n_rel, 1))
    return sum(recalls) / max(len(recalls), 1)


def main():
    print(f"{'='*70}")
    print(f"GLIA Benchmark v2 - Industry-Standard Metrics")
    print(f"Project: {project_name}")
    print(f"Token counting: tiktoken (cl100k_base)")
    print(f"{'='*70}")

    ground_truth = load_ground_truth()
    questions = ground_truth["multi_hop_questions"]
    print(f"Questions: {len(questions)}")

    # Setup
    brain, scan_stats, scan_time = setup_glia()
    n_glyphs = brain.stats()["nodes"]
    print(f"Scan: {scan_time:.2f}s -> {n_glyphs} glyphs")

    project_path = Path(__file__).parent.parent / project_name

    # Calculate full context tokens (REAL count)
    full_context = ""
    for filepath in project_path.rglob("*"):
        if filepath.suffix in (".py", ".ts", ".tsx", ".js", ".md") and ".glia" not in str(filepath):
            try:
                full_context += filepath.read_text(encoding="utf-8", errors="ignore") + "\n"
            except Exception:
                pass
    full_context_tokens = count_tokens(full_context)

    # Run queries
    results_relevance = []  # list of [bool, bool, ...] per query
    total_relevant_per_query = []
    glia_tokens_list = []
    latencies = []

    for q in questions:
        expected = get_expected_concepts(q)
        total_relevant_per_query.append(len(expected))

        start = time.time()
        result = brain.recall(q["question"], top_k=10)
        latency = time.time() - start
        latencies.append(latency)

        # Count real tokens in GLIA response
        context = result["context"]
        glia_tokens_list.append(count_tokens(context))

        # Evaluate relevance of each result
        relevance = []
        for node_id, _ in result["activated_nodes"][:10]:
            # Check if this result matches any expected concept
            node_text = f"{node_id} {next((t['content'] for t in result.get('threads', []) if t['id'] == node_id), '')}".lower()
            is_relevant = any(
                concept.lower().replace("_", " ") in node_text or
                concept.lower() in node_text
                for concept in expected
            )
            relevance.append(is_relevant)

        # Pad to 10 if fewer results
        while len(relevance) < 10:
            relevance.append(False)
        results_relevance.append(relevance)

    # Compute metrics
    mrr = compute_mrr(results_relevance)
    ndcg_5 = compute_ndcg(results_relevance, k=5)
    ndcg_10 = compute_ndcg(results_relevance, k=10)
    precision_1 = compute_precision_at_k(results_relevance, k=1)
    precision_3 = compute_precision_at_k(results_relevance, k=3)
    precision_5 = compute_precision_at_k(results_relevance, k=5)
    recall_3 = compute_recall_at_k(results_relevance, k=3, total_relevant=total_relevant_per_query)
    recall_5 = compute_recall_at_k(results_relevance, k=5, total_relevant=total_relevant_per_query)
    recall_10 = compute_recall_at_k(results_relevance, k=10, total_relevant=total_relevant_per_query)

    # Token stats
    avg_glia_tokens = sum(glia_tokens_list) / len(glia_tokens_list)
    max_glia_tokens = max(glia_tokens_list)
    min_glia_tokens = min(glia_tokens_list)
    compression_ratio = full_context_tokens / max(avg_glia_tokens, 1)
    savings_pct = (1 - avg_glia_tokens / full_context_tokens) * 100

    # Cost calculation
    cost_full_per_query = full_context_tokens * PRICE_PER_1M_INPUT_TOKENS / 1_000_000
    cost_glia_per_query = avg_glia_tokens * PRICE_PER_1M_INPUT_TOKENS / 1_000_000
    cost_savings_pct = (1 - cost_glia_per_query / cost_full_per_query) * 100

    # Latency stats
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted) // 2] * 1000
    p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)] * 1000
    p99 = latencies_sorted[int(len(latencies_sorted) * 0.99)] * 1000
    avg_latency = sum(latencies) / len(latencies) * 1000

    # Print results
    print(f"\n{'='*70}")
    print("RETRIEVAL QUALITY (Standard IR Metrics)")
    print(f"{'='*70}")
    print(f"  {'MRR (Mean Reciprocal Rank)':<35} {mrr:.4f}")
    print(f"  {'nDCG@5':<35} {ndcg_5:.4f}")
    print(f"  {'nDCG@10':<35} {ndcg_10:.4f}")
    print(f"  {'Precision@1':<35} {precision_1:.4f}")
    print(f"  {'Precision@3':<35} {precision_3:.4f}")
    print(f"  {'Precision@5':<35} {precision_5:.4f}")
    print(f"  {'Recall@3':<35} {recall_3:.4f}")
    print(f"  {'Recall@5':<35} {recall_5:.4f}")
    print(f"  {'Recall@10':<35} {recall_10:.4f}")

    print(f"\n{'='*70}")
    print("TOKEN EFFICIENCY (tiktoken cl100k_base - real count)")
    print(f"{'='*70}")
    print(f"  {'Full context (all files)':<35} {full_context_tokens:,} tokens")
    print(f"  {'GLIA avg per query':<35} {avg_glia_tokens:.0f} tokens")
    print(f"  {'GLIA min per query':<35} {min_glia_tokens} tokens")
    print(f"  {'GLIA max per query':<35} {max_glia_tokens} tokens")
    print(f"  {'Compression ratio':<35} {compression_ratio:.1f}x")
    print(f"  {'Token savings':<35} {savings_pct:.1f}%")

    print(f"\n{'='*70}")
    print("COST (Gemini 2.0 Flash pricing: $0.10/1M input tokens)")
    print(f"{'='*70}")
    print(f"  {'Cost per query (full context)':<35} ${cost_full_per_query:.6f}")
    print(f"  {'Cost per query (GLIA)':<35} ${cost_glia_per_query:.6f}")
    print(f"  {'Cost savings':<35} {cost_savings_pct:.1f}%")
    print(f"  {'Cost per 1000 queries (full)':<35} ${cost_full_per_query * 1000:.4f}")
    print(f"  {'Cost per 1000 queries (GLIA)':<35} ${cost_glia_per_query * 1000:.4f}")

    print(f"\n{'='*70}")
    print("LATENCY")
    print(f"{'='*70}")
    print(f"  {'Average':<35} {avg_latency:.1f} ms")
    print(f"  {'P50':<35} {p50:.1f} ms")
    print(f"  {'P95':<35} {p95:.1f} ms")
    print(f"  {'P99':<35} {p99:.1f} ms")

    print(f"\n{'='*70}")
    print("SYSTEM")
    print(f"{'='*70}")
    print(f"  {'Project files':<35} {scan_stats['learned']}")
    print(f"  {'Glyphs created':<35} {n_glyphs}")
    print(f"  {'Scan time':<35} {scan_time:.2f}s")
    print(f"  {'Scan cost':<35} $0.00 (AST only, no AI)")
    print(f"  {'Storage':<35} memory.db (SQLite)")
    print(f"  {'Vector dimension':<35} 1024")

    print(f"\n{'='*70}")

    # Cleanup
    import shutil
    shutil.rmtree(project_path / ".glia", ignore_errors=True)


if __name__ == "__main__":
    main()
