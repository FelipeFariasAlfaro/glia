# Benchmark: ML/Data Pipeline

> **Proyecto:** `benchmark_project_2` | **GLIA:** 0.1.0-alpha | **Modo:** Local ($0)

---

## Proyecto

Pipeline de ML: feature engineering, XGBoost training, drift detection, alertas, model registry, Airflow DAGs. 27 archivos Python + Markdown.

## Resultados

| Métrica | GLIA | Graph (SA) | BM25 |
|---------|------|-----------|------|
| **MRR** | 0.904 | 0.203 | 0.941 |
| **nDCG@5** | 0.911 | 0.235 | 0.936 |
| **nDCG@10** | 0.925 | 0.278 | 0.922 |
| **Precision@1** | 0.857 | 0.095 | 0.905 |

| Métrica | Valor |
|---------|-------|
| Glyphs | 375 |
| Scan time | 4.2s |
| Latencia | 117ms |
| Tokens (full) | 31,682 |
| Tokens (GLIA) | 602 |
| Ahorro | 98.1% (52.6x) |

## Observaciones

- **Mayor mejora sobre Graph (SA):** +344% en MRR. El grafo acierta solo 1 de cada 10 veces.
- **GLIA supera a BM25 en nDCG@10** (0.925 vs 0.922) — mejor ranking completo
- MRR de 0.904 — el primer resultado relevante está casi siempre en posición 1 o 2
- Vocabulario técnico de ML (features, drift, pipeline) favorece tanto a GLIA como a BM25
- BM25 gana en Precision@1 por 5 puntos — las keywords exactas de ML son muy específicas

## Reproducir

```bash
python benchmarks/benchmark_vs_graph.py benchmark_project_2
```
