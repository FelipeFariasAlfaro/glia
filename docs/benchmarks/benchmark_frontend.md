# Benchmark: TypeScript/React Frontend

> **Proyecto:** `benchmark_project_3` | **GLIA:** 0.1.0-alpha | **Modo:** Local ($0)

---

## Proyecto

SPA React/TypeScript: componentes, hooks (useAuth, useWebSocket), Redux (slices, middleware), API client con interceptors, routing, feature flags. 32 archivos TypeScript + Markdown.

## Resultados

| Métrica | GLIA | Graph (SA) | BM25 |
|---------|------|-----------|------|
| **MRR** | 0.877 | 0.421 | 0.885 |
| **nDCG@5** | 0.892 | 0.490 | 0.913 |
| **nDCG@10** | 0.890 | 0.538 | 0.903 |
| **Precision@1** | 0.810 | 0.238 | 0.810 |

| Métrica | Valor |
|---------|-------|
| Glyphs | 125 |
| Scan time | 1.6s |
| Latencia | 54ms |
| Tokens (full) | 23,183 |
| Tokens (GLIA) | 689 |
| Ahorro | 97.0% (33.7x) |

## Observaciones

- **Precision@1 idéntica a BM25** — ambos aciertan 81% de las veces
- **MRR a solo 0.9% de BM25** — prácticamente empate
- **Latencia más baja:** 54ms (solo 125 glyphs)
- **Scan más rápido:** 1.6s (archivos TypeScript son más concisos)
- Graph (SA) sigue fallando: Precision@1 de 0.24
- TypeScript con camelCase favorece la codificación (useAuth, OrderActions se descomponen bien en palabras semánticas)

## Reproducir

```bash
python benchmarks/benchmark_vs_graph.py benchmark_project_3
```
