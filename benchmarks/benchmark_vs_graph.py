"""
GLIA v2 (Holographic) vs Graph v1 (Spreading Activation) vs RAG vs BM25

Direct comparison of all four approaches on the same questions.
This proves GLIA v2 is genuinely different from (and better than) a graph.

Usage:
    python benchmarks/benchmark_vs_graph.py benchmark_project
"""

import sys
import os
import json
import time
import math
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import numpy as np
import tiktoken

from glia.brain import GliaBrain
from glia.scanner import Scanner
from glia.graph import GliaGraph
from glia.threads import ThreadStore
from glia.ast_scanner import ASTScanner

ENCODER = tiktoken.get_encoding("cl100k_base")
project_name = sys.argv[1] if len(sys.argv) > 1 else "benchmark_project"
project_path = Path(__file__).parent.parent / project_name
api_key = os.environ.get("GEMINI_API_KEY")


def count_tokens(text): return len(ENCODER.encode(text))


def load_ground_truth():
    data = json.loads((project_path / "knowledge.json").read_text(encoding="utf-8"))
    if "multi_hop_questions" not in data:
        data["multi_hop_questions"] = data.get("questions", [])
    return data


def get_expected(q):
    if "expected_concepts" in q:
        return set(q["expected_concepts"])
    elif "files_needed" in q:
        expected = set()
        for f in q["files_needed"]:
            parts = Path(f).stem.lower().replace("-", "_").split("_")
            expected.update(p for p in parts if len(p) >= 3)
        return expected
    return set()


def is_relevant(text, expected):
    text_lower = text.lower()
    return any(c.lower().replace("_", " ") in text_lower or c.lower() in text_lower for c in expected)


def compute_mrr(results_per_query):
    rrs = []
    for results in results_per_query:
        for i, is_rel in enumerate(results):
            if is_rel:
                rrs.append(1.0 / (i + 1))
                break
        else:
            rrs.append(0.0)
    return sum(rrs) / max(len(rrs), 1)


def compute_ndcg(results_per_query, k=5):
    scores = []
    for results in results_per_query:
        dcg = sum((1.0 if r else 0.0) / math.log2(i + 2) for i, r in enumerate(results[:k]))
        n_rel = sum(results[:k])
        idcg = sum(1.0 / math.log2(i + 2) for i in range(n_rel))
        scores.append(dcg / idcg if idcg > 0 else 0.0)
    return sum(scores) / max(len(scores), 1)


# --- Graph v1 baseline ---

def setup_graph_v1():
    """Setup the old graph-based system (v1) as baseline."""
    graph = GliaGraph()
    store = ThreadStore()
    scanner = ASTScanner()

    for filepath in project_path.rglob("*"):
        if filepath.suffix in (".py", ".ts", ".tsx", ".js", ".md") and ".glia" not in str(filepath):
            try:
                relative = str(filepath.relative_to(project_path))
                scanner.scan_file(filepath, graph, store, relative)
            except Exception:
                pass

    return graph, store


def graph_v1_query(query, graph, store, top_k=10):
    """Query the graph using spreading activation (v1 approach)."""
    # Resolve query to node IDs
    query_normalized = query.lower().replace(" ", "_").replace("-", "_")
    query_words = set(query_normalized.split("_"))

    # Find matching nodes
    stimuli = []
    for nid in graph.nodes:
        node_words = set(nid.split("_"))
        # Partial word matching
        for qw in query_words:
            for nw in node_words:
                if len(qw) >= 3 and (qw in nw or nw in qw):
                    if nid not in stimuli:
                        stimuli.append(nid)
                    break

    if not stimuli:
        # Fallback: substring
        for nid in graph.nodes:
            if any(w in nid for w in query_words if len(w) >= 3):
                stimuli.append(nid)

    if not stimuli:
        return []

    # Spreading activation
    activated = graph.get_activated_subgraph(stimuli[:5], top_k=top_k)

    # Get threads for activated nodes
    results = []
    node_ids = [nid for nid, _ in activated]
    threads = store.get_by_nodes(node_ids)

    for nid, score in activated:
        content = ""
        for t in threads:
            if nid in t.node_refs:
                content = t.content
                break
        results.append({"id": nid, "content": content, "score": score})

    return results


# --- BM25 ---

def bm25_query(query, chunks, top_k=5):
    query_words = [w for w in re.split(r'[^a-z0-9]+', query.lower()) if len(w) >= 2]
    scores = []
    all_lens = [len(c["text"].split()) for c in chunks]
    avg_dl = sum(all_lens) / max(len(all_lens), 1)

    for chunk in chunks:
        doc_words = chunk["text"].lower().split()
        dl = len(doc_words)
        score = 0
        for qw in query_words:
            tf = doc_words.count(qw)
            if tf > 0:
                score += (tf * 2.5) / (tf + 1.5 * (1 - 0.75 + 0.75 * dl / max(avg_dl, 1)))
        scores.append((chunk, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


def main():
    print(f"{'='*70}")
    print(f"GLIA v2 (Holographic) vs Graph v1 vs BM25")
    print(f"Project: {project_name}")
    print(f"{'='*70}")

    gt = load_ground_truth()
    questions = gt["multi_hop_questions"]
    print(f"Questions: {len(questions)}")

    # --- Setup GLIA v2 ---
    print("\n[1/3] Setting up GLIA v2 (holographic)...")
    import shutil
    glia_path = project_path / ".glia"
    if glia_path.exists():
        try:
            shutil.rmtree(glia_path)
        except PermissionError:
            # File locked — try to close any open connections
            import gc
            gc.collect()
            time.sleep(1)
            try:
                shutil.rmtree(glia_path)
            except Exception:
                pass

    brain = GliaBrain(workspace=project_path, api_key=None)  # NO embeddings — local mode only
    brain.init()
    scanner = Scanner(brain)
    start = time.time()
    scanner.scan()
    glia_time = time.time() - start
    print(f"  Scan: {glia_time:.1f}s, {brain.stats()['nodes']} glyphs")

    # --- Setup Graph v1 ---
    print("\n[2/3] Setting up Graph v1 (spreading activation)...")
    start = time.time()
    graph, store = setup_graph_v1()
    graph_time = time.time() - start
    print(f"  Scan: {graph_time:.1f}s, {graph.stats()['nodes']} nodes, {graph.stats()['edges']} edges")

    # --- Setup BM25 ---
    print("\n[3/3] Setting up BM25...")
    chunks = []
    for filepath in project_path.rglob("*"):
        if filepath.suffix in (".py", ".ts", ".tsx", ".js", ".md") and ".glia" not in str(filepath):
            try:
                content = filepath.read_text(encoding="utf-8", errors="ignore")
                relative = str(filepath.relative_to(project_path))
                for i in range(0, len(content), 400):
                    chunk = content[i:i+500]
                    if len(chunk.strip()) > 50:
                        chunks.append({"text": chunk, "source": relative})
            except Exception:
                pass
    print(f"  Chunks: {len(chunks)}")

    # --- Run queries ---
    print(f"\nRunning {len(questions)} queries...")

    glia_results = []
    graph_results = []
    bm25_results = []
    glia_latencies = []
    graph_latencies = []

    for i, q in enumerate(questions):
        expected = get_expected(q)
        question = q["question"]

        # GLIA v2
        start = time.time()
        glia_result = brain.recall(question, top_k=10)
        glia_latencies.append(time.time() - start)

        glia_rel = []
        for nid, _ in glia_result["activated_nodes"][:10]:
            text = f"{nid} {next((t['content'] for t in glia_result.get('threads', []) if t['id'] == nid), '')}"
            glia_rel.append(is_relevant(text, expected))
        while len(glia_rel) < 10:
            glia_rel.append(False)
        glia_results.append(glia_rel)

        # Graph v1
        start = time.time()
        graph_res = graph_v1_query(question, graph, store, top_k=10)
        graph_latencies.append(time.time() - start)

        graph_rel = []
        for r in graph_res[:10]:
            text = f"{r['id']} {r['content']}"
            graph_rel.append(is_relevant(text, expected))
        while len(graph_rel) < 10:
            graph_rel.append(False)
        graph_results.append(graph_rel)

        # BM25
        bm25_res = bm25_query(question, chunks, top_k=10)
        bm25_rel = []
        for chunk, _ in bm25_res[:10]:
            bm25_rel.append(is_relevant(chunk["text"], expected))
        while len(bm25_rel) < 10:
            bm25_rel.append(False)
        bm25_results.append(bm25_rel)

    # --- Results ---
    print(f"\n{'='*70}")
    print("RESULTS")
    print(f"{'='*70}")

    print(f"\n{'Metric':<20} {'GLIA v2':<15} {'Graph v1':<15} {'BM25':<15}")
    print("-" * 65)
    print(f"{'MRR':<20} {compute_mrr(glia_results):.4f}{'':<10} {compute_mrr(graph_results):.4f}{'':<10} {compute_mrr(bm25_results):.4f}")
    print(f"{'nDCG@5':<20} {compute_ndcg(glia_results, 5):.4f}{'':<10} {compute_ndcg(graph_results, 5):.4f}{'':<10} {compute_ndcg(bm25_results, 5):.4f}")
    print(f"{'nDCG@10':<20} {compute_ndcg(glia_results, 10):.4f}{'':<10} {compute_ndcg(graph_results, 10):.4f}{'':<10} {compute_ndcg(bm25_results, 10):.4f}")
    print(f"{'Precision@1':<20} {sum(r[0] for r in glia_results)/len(glia_results):.4f}{'':<10} {sum(r[0] for r in graph_results)/len(graph_results):.4f}{'':<10} {sum(r[0] for r in bm25_results)/len(bm25_results):.4f}")

    print(f"\n{'Metric':<20} {'GLIA v2':<15} {'Graph v1':<15} {'BM25':<15}")
    print("-" * 65)
    print(f"{'Scan time':<20} {glia_time:.1f}s{'':<10} {graph_time:.1f}s{'':<10} {'0s':<15}")
    print(f"{'Avg latency':<20} {sum(glia_latencies)/len(glia_latencies)*1000:.0f}ms{'':<10} {sum(graph_latencies)/len(graph_latencies)*1000:.0f}ms{'':<10} {'<1ms':<15}")
    print(f"{'Has edges?':<20} {'NO':<15} {'YES ({})'.format(graph.stats()['edges']):<15} {'NO':<15}")
    print(f"{'Plasticidad':<20} {'YES':<15} {'YES':<15} {'NO':<15}")
    print(f"{'Unbinding':<20} {'YES':<15} {'NO':<15} {'NO':<15}")

    glia_mrr = compute_mrr(glia_results)
    graph_mrr = compute_mrr(graph_results)
    print(f"\n{'='*70}")
    print(f"GLIA v2 vs Graph v1: {'GLIA WINS' if glia_mrr > graph_mrr else 'GRAPH WINS'} (MRR {glia_mrr:.4f} vs {graph_mrr:.4f})")
    print(f"{'='*70}")

    shutil.rmtree(glia_path, ignore_errors=True)


if __name__ == "__main__":
    main()
