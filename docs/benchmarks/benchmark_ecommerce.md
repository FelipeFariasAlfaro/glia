# Benchmark: E-Commerce Microservice

> **Proyecto:** `benchmark_project` | **GLIA:** 0.1.0-alpha | **Modo:** Local ($0)

---

## Proyecto

Microservicio e-commerce: API REST, JWT RS256, pagos Stripe, inventario, notificaciones, workers async, event-driven. 31 archivos Python + Markdown.

## Resultados

| Métrica | GLIA | Graph (SA) | BM25 |
|---------|------|-----------|------|
| **MRR** | 0.771 | 0.409 | 0.785 |
| **nDCG@5** | 0.796 | 0.473 | 0.786 |
| **nDCG@10** | 0.824 | 0.497 | 0.790 |
| **Precision@1** | 0.667 | 0.191 | 0.667 |

| Métrica | Valor |
|---------|-------|
| Glyphs | 346 |
| Scan time | 4.3s |
| Latencia | 111ms |
| Tokens (full) | 29,690 |
| Tokens (GLIA) | 543 |
| Ahorro | 98.2% (54.7x) |

## GLIA vs RAG (este proyecto)

| Sistema | MRR | Costo |
|---------|-----|-------|
| RAG (Gemini) | 0.873 | ~$0.001/query |
| GLIA + embeddings | 0.835 | ~$0.001/query |
| GLIA (local) | 0.783 | $0 |

## Observaciones

- GLIA supera a BM25 en nDCG@5 (+1.3%) y nDCG@10 (+4.3%) — mejor ranking general
- Precision@1 idéntica a BM25
- Graph (SA) falla 4 de cada 5 veces (Precision@1 = 0.19)
- GLIA pierde 10% contra RAG en MRR, pero a $0 de costo

## Reproducir

```bash
python benchmarks/benchmark_vs_graph.py benchmark_project
```
