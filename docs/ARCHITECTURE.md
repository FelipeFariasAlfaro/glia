# GLIA — Arquitectura: Memoria Holográfica Distribuida

> **Versión:** 0.1.0-alpha
> **Arquitectura:** Holographic Distributed Memory (HDM)
> **Base teórica:** Vector Symbolic Architectures (VSA)

---

## Visión General

GLIA almacena conocimiento como **patrones distribuidos** en un espacio vectorial de 1024 dimensiones. No hay nodos discretos ni aristas explícitas. Las relaciones se codifican holográficamente dentro del mismo espacio vectorial usando convolución circular.

```
┌─────────────────────────────────────────────────────────────────┐
│                        memory.db (SQLite)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ SUBSTRATE_REGIONS                                        │    │
│  │                                                          │    │
│  │ id       │ vector (BLOB, 1024 floats)  │ glyph_count    │    │
│  │ ─────────┼─────────────────────────────┼─────────────── │    │
│  │ default  │ [0.06, 0.03, 0.07, ...]     │ 346            │    │
│  │                                                          │    │
│  │ Todos los glyphs SUPERPUESTOS en un solo vector.        │    │
│  │ Tamaño CONSTANTE sin importar cuántos glyphs haya.      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ GLYPHS (metadata + vector individual)                    │    │
│  │                                                          │    │
│  │ id                │ vector (BLOB)  │ magnitude │ content │    │
│  │ ──────────────────┼────────────────┼───────────┼──────── │    │
│  │ auth_generate_tkn │ [0.02, -0.04]  │ 1.2       │ "Gen.." │    │
│  │ session_bug       │ [-0.01, 0.06]  │ 0.8       │ "Bug.." │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │ ⚠️  NO HAY TABLA DE EDGES / RELACIONES                   │    │
│  │                                                          │    │
│  │ Las relaciones se codifican como interferencias          │    │
│  │ holográficas DENTRO del vector del substrate.            │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Componentes del Sistema

```
┌─────────────────────────────────────────────────────────────────┐
│                        GLIA Engine                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Encoder    │  │  Substrate   │  │   Resonance Engine   │  │
│  │              │  │              │  │                      │  │
│  │ • text→glyph│  │ • regions[]  │  │ • resonate(stimulus) │  │
│  │ • synonyms  │  │ • superpose  │  │ • multihop(chain)    │  │
│  │ • stemming  │  │ • store      │  │ • unbind(discover)   │  │
│  │ • bigrams   │  │              │  │ • conjunctive(A∧B)   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Plasticity  │  │   Storage    │  │     AST Scanner      │  │
│  │              │  │  (SQLite)    │  │                      │  │
│  │ • reinforce  │  │              │  │ • Python (AST)       │  │
│  │ • decay      │  │ • save BLOB  │  │ • JS/TS (regex)      │  │
│  │ • co_activate│  │ • load BLOB  │  │ • Java, Go, Rust...  │  │
│  │ • forget     │  │ • no edges!  │  │ • Markdown, Gherkin  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │  Embeddings  │  │  Distiller   │  │   Cloud Engine       │  │
│  │  (opcional)  │  │  (Gemini)    │  │   (Vertex AI)        │  │
│  │              │  │              │  │                      │  │
│  │ • Gemini API │  │ • learn()    │  │ • Native IAM Auth    │  │
│  │ • enhanced   │  │ • Vertex AI  │  │ • No API Keys        │  │
│  │ • fallback   │  │ • conceptos  │  │ • Enterprise Scale   │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                                                  │
├─────────────────────────────────────────────────────────────────┤
│                        MCP Server                                │
│  glia_recall │ glia_learn │ glia_scan │ glia_forget │ glia_stats│
└─────────────────────────────────────────────────────────────────┘
```

---

## Operaciones Fundamentales

### 1. Codificación (Encoder)

```
Texto: "Generate a JWT token for the user"
         │
         ▼ tokenize + expand synonyms + stem
    ["generate", "jwt", "token", "user", "auth", "authentication", ...]
         │
         ▼ hash cada palabra → vector aleatorio determinista
         ▼ sumar (bag-of-words) + bigrams + trigrams
         ▼ normalizar
         │
    [0.023, -0.041, 0.087, ..., -0.012, 0.055]  ← 1024 dimensiones
```

### 2. Binding (Convolución Circular)

```
    Concepto A: "generate_token"    Concepto B: "jwt_secret"
    [0.02, -0.04, 0.08, ...]       [0.05, 0.01, -0.03, ...]
              │                              │
              └──────────┬───────────────────┘
                         │
                         ▼ FFT(A) × FFT(B) → IFFT
                         │
    Binding: [0.07, -0.02, 0.01, ...]
    
    • Distinto a A y a B
    • unbind(binding, A) ≈ B
    • Se SUMA al substrate (no crea edge)
```

### 3. Resonancia (Recuperación)

```
    Query: "¿por qué expiran los tokens?"
         │
         ▼ encode_text()
    Stimulus: [0.03, -0.02, 0.06, ...]
         │
         ▼ cosine_similarity contra CADA glyph (paralelo)
         │
    ┌────────────────────────────────────────────┐
    │  glyph_1: cos = 0.69  ← RESUENA           │
    │  glyph_2: cos = 0.13                       │
    │  glyph_3: cos = 0.12                       │
    │  ...                                        │
    │  glyph_N: cos = 0.01                       │
    └────────────────────────────────────────────┘
         │
         ▼ Top-K por score (score = cos × magnitude)
         │
         ▼ Holographic Unbinding (multi-hop)
         │  Para cada top result, unbind del substrate
         │  para descubrir asociaciones implícitas
         │
         ▼ Cognitive Map (output estructurado)
```

### 4. Plasticidad

```
    REFUERZO: glyph activado → magnitude += 0.02
    
    DECAIMIENTO: magnitude -= rate × log(1 + horas_sin_uso)
    
    CO-ACTIVACIÓN: si A y B resuenan juntos →
                   substrate += bind(A, B) × 0.02
                   (futuras queries por A también activan B)
```

---

## Flujo de Datos Completo

```
┌─────────────────────────────────────────────────────────────────┐
│ SCAN (gratis, AST)                                               │
│                                                                  │
│  archivo.py → AST parse → funciones, clases, imports, docstrings │
│            → encode_text(nombre + docstring)                     │
│            → substrate.store_glyph(vector)                       │
│            → encode_relationship(imports) → substrate += binding │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ RECALL (gratis, local)                                           │
│                                                                  │
│  query → encode_text(query)                                      │
│       → resonate(stimulus, all_glyphs)                          │
│       → unbind(substrate, top_results) → discover associations  │
│       → reinforce(activated_glyphs)                             │
│       → co_activate(top_pairs)                                  │
│       → build_cognitive_map(results)                            │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│ LEARN (usa Gemini Flash)                                         │
│                                                                  │
│  texto → Gemini destila → conceptos + intenciones               │
│       → encode_text(concepto + intención)                       │
│       → substrate.store_glyph(vector)                           │
│       → encode_relationship(relaciones) → substrate += bindings │
└─────────────────────────────────────────────────────────────────┘
```

---

## ¿Por qué NO es un grafo?

| Propiedad | Grafo | GLIA |
|---|---|---|
| Unidad de almacenamiento | Nodo (etiqueta discreta) | Glyph (vector 1024-d) |
| Relaciones | Tabla de edges | Interferencias holográficas en el substrate |
| Recuperación | BFS/DFS secuencial | Proyección paralela (cosine) |
| Si borras 30% | Pierdes caminos | Sigue funcionando (holográfico) |
| Analogías | Imposible | Nativo (aritmética vectorial) |
| Storage | O(N + E) crece con relaciones | O(R × D) constante por región |
| Tabla de edges en DB | Sí | **NO** |

---

## Archivos del Sistema

| Archivo | Responsabilidad |
|---------|----------------|
| `binding.py` | Convolución circular, unbind, cosine similarity |
| `encoder.py` | Texto → vector (synonyms, stemming, bigrams, trigrams) |
| `synonyms.py` | Diccionario estático de sinónimos de programación |
| `substrate.py` | Regiones + glyphs + superposición |
| `resonance.py` | Resonancia, multi-hop, unbinding, conjunctive queries |
| `plasticity.py` | Reinforce, decay, co-activate |
| `cognitive_map.py` | Formateo de output para LLMs |
| `brain.py` | Orquestador (learn, recall, forget, stats) |
| `storage.py` | SQLite persistence (BLOB vectors, no edges) |
| `ast_scanner_v2.py` | Parser multi-lenguaje → glyphs |
| `embeddings.py` | Embeddings opcionales (Gemini) para modo enhanced |
| `distiller.py` | Destilación con LLM para glia_learn |
| `scanner.py` | Scan incremental de proyecto |
| `mcp_server.py` | Servidor MCP (stdio) |
| `cli.py` | Interfaz de línea de comandos |
