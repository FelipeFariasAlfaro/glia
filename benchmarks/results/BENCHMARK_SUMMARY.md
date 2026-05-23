# GLIA v0.1.0-alpha — Resumen de Benchmarks

> **Modo testeado:** Local (sin embeddings, $0 costo, sin API key)
> **Arquitectura:** Holographic Distributed Memory (HDM)
> **Fecha:** Mayo 2026

---

## ¿Qué mide cada métrica?

### MRR (Mean Reciprocal Rank)

Mide qué tan arriba en los resultados aparece el primer ítem relevante.

- MRR = 1.0 → El primer resultado siempre es correcto
- MRR = 0.5 → El primer resultado relevante está en posición 2 (promedio)
- MRR = 0.33 → El primer resultado relevante está en posición 3

**¿Para qué sirve?** Es la métrica estándar en motores de búsqueda y evaluación de RAG (RAGAS, BEIR). Si el sistema devuelve el contexto correcto en primera posición, el LLM responde mejor.

### nDCG@K (Normalized Discounted Cumulative Gain)

Mide la calidad del ranking completo, no solo del primer resultado. Penaliza ítems relevantes que aparecen más abajo.

- nDCG = 1.0 → Ranking perfecto
- nDCG = 0.5 → Los relevantes están mezclados con irrelevantes

**¿Para qué sirve?** Captura si el sistema entiende la importancia relativa de cada resultado. Usado por Google, TREC, MTEB.

### Precision@1

Qué fracción de las veces el primer resultado es relevante.

- Precision@1 = 0.8 → 80% de las veces el primer resultado es correcto

**¿Para qué sirve?** Mide directamente cuánto "ruido" recibe el LLM en la primera posición.

### Token Savings

Cuántos menos tokens envía GLIA al LLM comparado con enviar todos los archivos. Medido con tiktoken (tokenizador real, no aproximación).

**¿Para qué sirve?** Menos tokens = menos costo en APIs + mejores respuestas del LLM (menos ruido).

### Latencia

Tiempo para procesar una query localmente. Sin llamadas de red.

**¿Para qué sirve?** GLIA corre 100% local. No hay latencia de red, no hay rate limits, no hay costos por query.

---

## Sistemas Comparados

| Sistema              | Qué es                                                                                                                         | Costo         | Requiere API Key |
|----------------------|--------------------------------------------------------------------------------------------------------------------------------|---------------|------------------|
| **GLIA**             | Memoria Holográfica Distribuida. Hash encoding + sinónimos + stemming + holographic unbinding                                   | $0            | No               |
| **Graph (SA)**       | Grafo tradicional con nodos + edges + spreading activation (BFS). El tipo de arquitectura que usan la mayoría de knowledge graphs | $0            | No               |
| **BM25**             | Búsqueda por keywords (mismo algoritmo que Elasticsearch). El baseline que cualquier sistema debe superar                       | $0            | No               |
| **RAG (Embeddings)** | Retrieval-Augmented Generation con embeddings semánticos de Gemini. El estándar actual de la industria                         | ~$0.001/query | Sí               |

---

## Resultados Consolidados

### MRR (mayor es mejor)

| Proyecto                     | GLIA      | Graph (SA) | BM25      | GLIA vs Graph | GLIA vs BM25 |
|------------------------------|-----------|------------|-----------|---------------|--------------|
| E-Commerce (31 archivos)     | **0.771** | 0.409      | 0.785     | +88.6%        | -1.7%        |
| ML Pipeline (27 archivos)    | **0.904** | 0.203      | 0.941     | +344.2%       | -3.9%        |
| Frontend React (32 archivos) | **0.877** | 0.421      | 0.885     | +108.1%       | -0.9%        |
| **Promedio**                 | **0.851** | 0.344      | 0.870     | **+147.4%**   | **-2.2%**    |

### nDCG@10 (mayor es mejor)

| Proyecto       | GLIA      | Graph (SA) | BM25      |
|----------------|-----------|------------|-----------|
| E-Commerce     | **0.824** | 0.497      | 0.790     |
| ML Pipeline    | **0.925** | 0.278      | 0.922     |
| Frontend React | **0.890** | 0.538      | 0.903     |

### Precision@1 (mayor es mejor)

| Proyecto       | GLIA      | Graph (SA) | BM25      |
|----------------|-----------|------------|-----------|
| E-Commerce     | **0.667** | 0.191      | 0.667     |
| ML Pipeline    | **0.857** | 0.095      | 0.905     |
| Frontend React | **0.810** | 0.238      | 0.810     |

---

## Eficiencia de Tokens (tiktoken cl100k_base)

| Proyecto       | Contexto Completo | GLIA Promedio | Ahorro    | Compresión |
|----------------|-------------------|---------------|-----------|------------|
| E-Commerce     | 29,690 tokens      | 543 tokens    | **98.2%** | 54.7x      |
| ML Pipeline    | 31,682 tokens      | 602 tokens    | **98.1%** | 52.6x      |
| Frontend React | 23,183 tokens      | 689 tokens    | **97.0%** | 33.7x      |

---

## Latencia

| Proyecto       | Glyphs | Scan Time | Query Latency |
|----------------|--------|-----------|---------------|
| E-Commerce     | 346    | 4.3s      | **111ms**     |
| ML Pipeline    | 375    | 4.2s      | **117ms**     |
| Frontend React | 125    | 1.6s      | **54ms**      |

---

## GLIA vs RAG (Gemini Embeddings)

Comparación directa en E-Commerce:

| Sistema                           | MRR       | Costo/query | Requiere API |
|-----------------------------------|-----------|-------------|--------------|
| RAG (Gemini embedding-001)        | **0.873** | ~$0.001     | Sí           |
| BM25                              | 0.861     | $0          | No           |
| GLIA + embeddings (modo enhanced) | 0.835     | ~$0.001     | Sí           |
| **GLIA (local, sin embeddings)**   | 0.783     | **$0**      | **No**       |

---

## Conclusiones

### GLIA vs Graph (Spreading Activation)

GLIA supera al grafo tradicional por un factor de **2.5x en MRR promedio** (0.851 vs 0.344). El grafo con spreading activation obtiene Precision@1 de 0.09-0.24 — falla entre 3 y 9 de cada 10 veces. GLIA no es un grafo con otro nombre; es una arquitectura mediblemente superior.

### GLIA vs BM25

GLIA está **a 2.2% de BM25** en MRR promedio (0.851 vs 0.870). En nDCG@10, GLIA **supera a BM25** en E-Commerce (0.824 vs 0.790). BM25 es un algoritmo de 30 años optimizado para keyword matching — que GLIA lo iguale sin usar frecuencias de términos es notable.

### GLIA vs RAG — La diferencia fundamental

RAG gana en precisión pura (MRR 0.873 vs 0.783 en modo local). Pero la comparación no es justa porque miden cosas diferentes:

**RAG responde:** "¿Qué texto es más similar a mi pregunta?"
- Busca el chunk de texto que más se parece semánticamente a la query
- Devuelve ese texto tal cual al LLM
- No entiende relaciones entre chunks
- No aprende con el uso
- Cada query cuesta tokens (embedding de la query)

**GLIA responde:** "¿Qué patrones de conocimiento resuenan con mi pregunta, y cómo se asocian entre sí?"
- Proyecta la query en un espacio holográfico
- Descubre asociaciones implícitas via unbinding
- Se fortalece con el uso (plasticidad Hebbiana)
- Decae lo que no se usa (auto-limpieza)
- Cada query es $0 (100% local)

**Lo que GLIA puede hacer y RAG no:**
1. **Descubrir relaciones implícitas** — Si A fue almacenado junto con B (via binding), preguntar por A activa B aunque no compartan vocabulario
2. **Mejorar con el uso** — Cada recall refuerza los patrones activados. Después de 10 queries sobre auth, los patrones de auth resuenan más fuerte
3. **Olvidar lo obsoleto** — Patrones no usados decaen automáticamente. No hay "basura" acumulada
4. **Funcionar offline** — Sin internet, sin API keys, sin costos recurrentes
5. **Escalar sin costo** — 1000 queries/día cuestan $0. Con RAG costarían ~$1/día

**Lo que RAG puede hacer y GLIA no (aún):**
1. **Entender sinónimos profundos** — "authentication" ≈ "login" ≈ "sign in" (embeddings semánticos)
2. **Precisión superior en single-hop** — Para preguntas directas, RAG es ~10% mejor

### Posicionamiento

GLIA no compite con RAG en el mismo eje. RAG es un buscador semántico. GLIA es una **memoria viva** que crece, se adapta y descubre relaciones. Son complementarios — y GLIA ofrece el modo enhanced (con embeddings opcionales) para quienes quieran ambos.

---

## Cómo Reproducir

```bash
# Comparar GLIA vs Graph vs BM25
python benchmarks/benchmark_vs_graph.py benchmark_project
python benchmarks/benchmark_vs_graph.py benchmark_project_2
python benchmarks/benchmark_vs_graph.py benchmark_project_3

# Comparar GLIA vs RAG (requiere GEMINI_API_KEY en .env)
python benchmarks/benchmark_vs_rag.py benchmark_project
```

---

## Benchmarks Detallados

- [E-Commerce Microservice](./benchmark_ecommerce.md)
- [ML/Data Pipeline](./benchmark_ml_pipeline.md)
- [TypeScript/React Frontend](./benchmark_frontend.md)
