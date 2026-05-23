"""
GLIA vs RAG Benchmark — Direct comparison using Gemini embeddings.

Compares:
- GLIA (holographic resonance, $0 indexing)
- RAG with Gemini embeddings (text-embedding-004, cosine similarity)
- BM25/FTS baseline (keyword matching)

Uses the same questions and ground truth for fair comparison.

Usage:
    python benchmarks/benchmark_vs_rag.py benchmark_project
    python benchmarks/benchmark_vs_rag.py benchmark_project_2
    python benchmarks/benchmark_vs_rag.py benchmark_project_3
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

from google import genai

from glia.brain import GliaBrain
from glia.scanner import Scanner

ENCODER = tiktoken.get_encoding("cl100k_base")
PRICE_PER_1M_INPUT = 0.10  # Gemini Flash input

project_name = sys.argv[1] if len(sys.argv) > 1 else "benchmark_project"
project_path = Path(__file__).parent.parent / project_name

# Gemini client for embeddings
api_key = os.environ.get("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)


def count_tokens(text: str) -> int:
    return len(ENCODER.encode(text))


def load_ground_truth():
    gt_path = project_path / "knowledge.json"
    data = json.loads(gt_path.read_text(encoding="utf-8"))
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


# --- RAG Implementation (Gemini Embeddings) ---

def chunk_files(project_path: Path, chunk_size: int = 500) -> list[dict]:
    """Chunk all project files into ~500 char segments (standard RAG chunking)."""
    chunks = []
    for filepath in project_path.rglob("*"):
        if filepath.suffix not in (".py", ".ts", ".tsx", ".js", ".md"):
            continue
        if ".glia" in str(filepath):
            continue
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        relative = str(filepath.relative_to(project_path))

        # Split into chunks of ~500 chars with overlap
        for i in range(0, len(content), chunk_size - 100):
            chunk_text = content[i:i + chunk_size]
            if len(chunk_text.strip()) > 50:
                chunks.append({
                    "text": chunk_text,
                    "source": relative,
                    "start": i,
                })
    return chunks


def embed_texts(texts: list[str], batch_size: int = 20) -> list[list[float]]:
    """Embed texts using Gemini embedding model."""
    all_embeddings = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=batch,
            )
            for emb in result.embeddings:
                all_embeddings.append(emb.values)
        except Exception as e:
            print(f"  Embedding error: {e}")
            # Fallback: zero vectors
            for _ in batch:
                all_embeddings.append([0.0] * 768)
        time.sleep(0.5)  # Rate limiting
    return all_embeddings


def cosine_sim(a, b):
    a = np.array(a)
    b = np.array(b)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a < 1e-10 or norm_b < 1e-10:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def rag_retrieve(query_embedding, chunk_embeddings, chunks, top_k=5):
    """Standard RAG retrieval: cosine similarity against all chunks."""
    scores = []
    for i, emb in enumerate(chunk_embeddings):
        sim = cosine_sim(query_embedding, emb)
        scores.append((chunks[i], sim))
    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# --- BM25 Implementation ---

def bm25_score(query_words, doc_words, avg_dl, k1=1.5, b=0.75):
    """Simple BM25 scoring."""
    dl = len(doc_words)
    score = 0.0
    for qw in query_words:
        tf = doc_words.count(qw)
        if tf > 0:
            idf = 1.0  # Simplified
            numerator = tf * (k1 + 1)
            denominator = tf + k1 * (1 - b + b * dl / max(avg_dl, 1))
            score += idf * numerator / denominator
    return score


def bm25_retrieve(query, chunks, top_k=5):
    """BM25 retrieval over chunks."""
    query_words = re.split(r'[^a-z0-9]+', query.lower())
    query_words = [w for w in query_words if len(w) >= 2]

    all_doc_words = [re.split(r'[^a-z0-9]+', c["text"].lower()) for c in chunks]
    avg_dl = sum(len(d) for d in all_doc_words) / max(len(all_doc_words), 1)

    scores = []
    for i, doc_words in enumerate(all_doc_words):
        score = bm25_score(query_words, doc_words, avg_dl)
        scores.append((chunks[i], score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:top_k]


# --- Metrics ---

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


def is_relevant(text, expected_concepts):
    text_lower = text.lower()
    return any(c.lower().replace("_", " ") in text_lower or c.lower() in text_lower for c in expected_concepts)


# --- Main ---

def main():
    print(f"{'='*70}")
    print(f"GLIA vs RAG vs BM25 — Direct Comparison")
    print(f"Project: {project_name}")
    print(f"Embeddings: Gemini gemini-embedding-001")
    print(f"{'='*70}")

    gt = load_ground_truth()
    questions = gt["multi_hop_questions"]
    print(f"Questions: {len(questions)}")

    # --- Setup GLIA ---
    print("\n[1/3] Setting up GLIA...")
    import shutil
    glia_path = project_path / ".glia"
    if glia_path.exists():
        shutil.rmtree(glia_path)

    brain = GliaBrain(workspace=project_path, api_key=api_key)
    brain.init()
    scanner = Scanner(brain)
    glia_start = time.time()
    scanner.scan()
    glia_scan_time = time.time() - glia_start
    print(f"  GLIA scan: {glia_scan_time:.2f}s, {brain.stats()['nodes']} glyphs, $0")

    # --- Setup RAG ---
    print("\n[2/3] Setting up RAG (Gemini embeddings)...")
    chunks = chunk_files(project_path)
    print(f"  Chunks: {len(chunks)}")

    rag_start = time.time()
    chunk_texts = [c["text"] for c in chunks]
    chunk_embeddings = embed_texts(chunk_texts)
    rag_index_time = time.time() - rag_start
    # Estimate cost: embedding pricing is $0.00025/1K chars for Gemini
    total_chars = sum(len(t) for t in chunk_texts)
    rag_index_cost = total_chars / 1000 * 0.00025
    print(f"  RAG indexing: {rag_index_time:.1f}s, ${rag_index_cost:.4f}")

    # --- Setup BM25 ---
    print("\n[3/3] BM25 ready (no setup needed)")

    # --- Run queries ---
    print(f"\nRunning {len(questions)} queries...")

    glia_results = []
    rag_results = []
    bm25_results = []
    glia_tokens = []
    rag_tokens = []
    glia_latencies = []
    rag_latencies = []
    bm25_latencies = []

    for i, q in enumerate(questions):
        expected = get_expected(q)
        question = q["question"]

        # GLIA
        start = time.time()
        glia_result = brain.recall(question, top_k=10)
        glia_latencies.append(time.time() - start)
        glia_tokens.append(count_tokens(glia_result["context"]))

        glia_relevance = []
        for nid, _ in glia_result["activated_nodes"][:10]:
            text = f"{nid} {next((t['content'] for t in glia_result.get('threads', []) if t['id'] == nid), '')}"
            glia_relevance.append(is_relevant(text, expected))
        while len(glia_relevance) < 10:
            glia_relevance.append(False)
        glia_results.append(glia_relevance)

        # RAG
        start = time.time()
        q_emb = embed_texts([question])[0]
        rag_top = rag_retrieve(q_emb, chunk_embeddings, chunks, top_k=10)
        rag_latencies.append(time.time() - start)

        rag_context = "\n".join(c["text"] for c, _ in rag_top[:5])
        rag_tokens.append(count_tokens(rag_context))

        rag_relevance = []
        for chunk, score in rag_top[:10]:
            rag_relevance.append(is_relevant(chunk["text"], expected))
        while len(rag_relevance) < 10:
            rag_relevance.append(False)
        rag_results.append(rag_relevance)

        # BM25
        start = time.time()
        bm25_top = bm25_retrieve(question, chunks, top_k=10)
        bm25_latencies.append(time.time() - start)

        bm25_relevance = []
        for chunk, score in bm25_top[:10]:
            bm25_relevance.append(is_relevant(chunk["text"], expected))
        while len(bm25_relevance) < 10:
            bm25_relevance.append(False)
        bm25_results.append(bm25_relevance)

        if (i + 1) % 5 == 0:
            print(f"  Processed {i+1}/{len(questions)}")

    # --- Compute metrics ---
    print(f"\n{'='*70}")
    print("RESULTS — GLIA vs RAG (Gemini Embeddings) vs BM25")
    print(f"{'='*70}")

    print(f"\n{'Metric':<25} {'GLIA':<15} {'RAG':<15} {'BM25':<15}")
    print("-" * 70)
    print(f"{'MRR':<25} {compute_mrr(glia_results):.4f}{'':<10} {compute_mrr(rag_results):.4f}{'':<10} {compute_mrr(bm25_results):.4f}")
    print(f"{'nDCG@5':<25} {compute_ndcg(glia_results, 5):.4f}{'':<10} {compute_ndcg(rag_results, 5):.4f}{'':<10} {compute_ndcg(bm25_results, 5):.4f}")
    print(f"{'nDCG@10':<25} {compute_ndcg(glia_results, 10):.4f}{'':<10} {compute_ndcg(rag_results, 10):.4f}{'':<10} {compute_ndcg(bm25_results, 10):.4f}")
    print(f"{'Precision@1':<25} {sum(r[0] for r in glia_results)/len(glia_results):.4f}{'':<10} {sum(r[0] for r in rag_results)/len(rag_results):.4f}{'':<10} {sum(r[0] for r in bm25_results)/len(bm25_results):.4f}")
    print(f"{'Precision@5':<25} {sum(sum(r[:5])/5 for r in glia_results)/len(glia_results):.4f}{'':<10} {sum(sum(r[:5])/5 for r in rag_results)/len(rag_results):.4f}{'':<10} {sum(sum(r[:5])/5 for r in bm25_results)/len(bm25_results):.4f}")

    avg_glia_tokens = sum(glia_tokens) / len(glia_tokens)
    avg_rag_tokens = sum(rag_tokens) / len(rag_tokens)

    print(f"\n{'Metric':<25} {'GLIA':<15} {'RAG':<15} {'BM25':<15}")
    print("-" * 70)
    print(f"{'Avg tokens/query':<25} {avg_glia_tokens:.0f}{'':<10} {avg_rag_tokens:.0f}{'':<10} {'N/A':<15}")
    print(f"{'Indexing time':<25} {glia_scan_time:.1f}s{'':<10} {rag_index_time:.1f}s{'':<10} {'0s':<15}")
    print(f"{'Indexing cost':<25} {'$0.00':<15} {'${:.4f}'.format(rag_index_cost):<15} {'$0.00':<15}")
    print(f"{'Avg latency':<25} {sum(glia_latencies)/len(glia_latencies)*1000:.0f}ms{'':<10} {sum(rag_latencies)/len(rag_latencies)*1000:.0f}ms{'':<10} {sum(bm25_latencies)/len(bm25_latencies)*1000:.0f}ms")
    print(f"{'Query cost':<25} {'$0.00':<15} {'~$0.0001':<15} {'$0.00':<15}")

    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    glia_mrr = compute_mrr(glia_results)
    rag_mrr = compute_mrr(rag_results)
    bm25_mrr = compute_mrr(bm25_results)
    winner = "GLIA" if glia_mrr >= rag_mrr else "RAG"
    print(f"  Winner (MRR): {winner} ({max(glia_mrr, rag_mrr):.4f} vs {min(glia_mrr, rag_mrr):.4f})")
    print(f"  Token efficiency: GLIA uses {avg_glia_tokens:.0f} tokens vs RAG {avg_rag_tokens:.0f} tokens")
    print(f"  Cost advantage: GLIA indexing is free, RAG costs ${rag_index_cost:.4f}")
    print(f"  GLIA is {'better' if glia_mrr > rag_mrr else 'comparable to' if abs(glia_mrr - rag_mrr) < 0.05 else 'worse than'} RAG on retrieval quality")
    print(f"  GLIA is {'more' if avg_glia_tokens < avg_rag_tokens else 'less'} token-efficient than RAG")

    # Cleanup
    shutil.rmtree(glia_path, ignore_errors=True)


if __name__ == "__main__":
    main()
