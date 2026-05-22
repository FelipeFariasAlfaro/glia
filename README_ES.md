# 🧠 GLIA - Memoria Holográfica Distribuida para Agentes de IA

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Version](https://img.shields.io/badge/version-0.1.0--alpha-orange.svg)]()

**GLIA** es un sistema de memoria persistente para agentes de IA basado en **Memoria Holográfica Distribuida (HDM)**. No es un grafo. No es RAG. Es una arquitectura genuinamente distinta donde el conocimiento se almacena como patrones distribuidos en un espacio vectorial de alta dimensión, y la recuperación funciona por **resonancia** — proyección paralela de patrones, no búsqueda de texto ni traversal de nodos.

---

## ¿Qué problema resuelve?

Los agentes de IA (Cline, Claude, Cursor, Copilot, etc) pierden contexto entre sesiones. Cada chat nuevo empieza de cero — sin memoria de bugs pasados, decisiones arquitectónicas, ni cómo se relacionan las partes del proyecto.

GLIA resuelve esto manteniendo una **memoria relacional persistente** que crece con cada interacción y se fortalece con el uso.

---

## ¿En qué se diferencia?

| | RAG | Grafos | Texto plano | **GLIA** |
|---|---|---|---|---|
| Almacena | Chunks vectorizados | Nodos + aristas | Texto indexado | **Patrones distribuidos (glyphs)** |
| Busca por | Similitud coseno | Traversal BFS/DFS | Keywords | **Resonancia (proyección paralela)** |
| Relaciones | No tiene | Aristas explícitas | No tiene | **Holográficas (codificadas en el vector)** |
| Si corrompes 30% | Pierde chunks | Pierde caminos | Pierde texto | **Sigue funcionando (propiedad holográfica)** |
| Razonamiento analógico | No | No | No | **Sí (aritmética vectorial)** |
| Costo de indexar | Tokens | Tokens | $0 | **$0 (AST parsing)** |
| Storage | O(N×D) | O(N + E) | O(N) | **O(R×D) constante por región** |

---

## Capacidades que un grafo NO puede hacer

GLIA demuestra operaciones estructuralmente imposibles en un grafo tradicional:

1. **One-shot learning**: Una sola operación `bind(A, B)` crea una asociación recuperable. Sin entrenamiento iterativo.
2. **Degradación graceful**: Corrompe 30% de las dimensiones → similitud 0.85. Un grafo con 30% de edges borrados pierde caminos enteros.
3. **Razonamiento analógico**: `king - man + woman ≈ queen`. Sin edge explícito "king→queen".
4. **Queries conjuntivas**: Buscar cosas relacionadas a A **Y** B simultáneamente por superposición.
5. **Storage O(D)**: 500 glyphs en 8KB. Un grafo necesitaría potencialmente 250K edges.

Ejecuta `python examples/demo_v2.py` para ver estas capacidades en acción.

---

## Instalación

GLIA se instala **una vez** en tu máquina como herramienta global. Se clona en cualquier ubicación (NO dentro de tu proyecto).

**Paso 1: Clonar GLIA**

```bash
# En cualquier lugar de tu máquina
cd ~/tools
git clone https://github.com/FelipeFariasAlfaro/glia.git
cd glia
```

**Paso 2: Instalar**

```bash
pip install -e .
```

**Paso 3: Verificar**

```bash
python -m glia --version
# Output: glia, version 0.1.0-alpha
```

> **Nota Windows:** Si ves un warning de PATH, usa `python -m glia` en vez de `glia`.

---

## Uso en tu proyecto

Ve a **tu proyecto** (el que quieres que GLIA recuerde) e inicializa:

**Paso 1: Inicializar**

```bash
cd /ruta/a/tu/proyecto
python -m glia init
```

Crea una carpeta `.glia/` con un `memory.db` vacío. Agrega `.glia/` a tu `.gitignore`.

**Paso 2: Escanear (gratis, instantáneo, sin IA)**

```bash
python -m glia scan
```

Parsea todos los archivos con AST. Extrae funciones, clases, imports, docstrings. Crea glyphs en el substrate. Toma segundos, cuesta $0, no necesita API key.

**Paso 3: Consultar**

```bash
python -m glia recall "autenticación JWT"
python -m glia recall "configuración base de datos"
```

**Paso 4: Enseñar (opcional, usa Gemini Flash)**

```bash
python -m glia learn "El bug de sesiones era porque el token expiraba en ms en vez de seconds. Fix en auth.py línea 25."
```

Para esto necesitas un `.env` en tu proyecto:
```
GEMINI_API_KEY=tu_key_aqui
GLIA_MODEL=gemini-3.1-flash-lite-preview
```

Obtén tu key gratis en: https://aistudio.google.com/apikey

> **Importante:** La API key solo se necesita para `glia learn`. Los comandos `scan`, `recall`, `stats` y `forget` funcionan **sin API key**.

---

## Estructura de carpetas

```
~/tools/glia/                  ← Código fuente de GLIA (se clona una vez)
    src/glia/
    pyproject.toml

~/projects/mi-api/             ← TU proyecto
    .glia/                     ← Creado por 'glia init' (agregar a .gitignore)
        memory.db              ← Memoria holográfica de este proyecto
    .env                       ← Tu API key (agregar a .gitignore)
    src/
    ...

~/projects/otro-proyecto/      ← Otro proyecto (memoria separada)
    .glia/
        memory.db
    ...
```

Cada proyecto tiene su propia memoria. GLIA se instala una vez y se usa en muchos proyectos.

---

## ¿Cómo funciona GLIA por dentro?

### La analogía: El cerebro no es un disco duro

Cuando recuerdas el aroma de un pastel, tu cerebro no busca en una carpeta llamada "Recuerdos/Pasteles/aroma.txt". Lo que ocurre es que un estímulo pequeño (el olor) **activa un patrón** de neuronas que, por interferencia, reconstruye el recuerdo completo: la cocina, tu abuela, la conversación que tuviste.

El conocimiento no está en un punto. Está **distribuido** en un patrón de activación.

GLIA replica este principio computacionalmente.

---

### Paso 1: Codificación — Convertir conocimiento en patrones

Cuando GLIA escanea tu proyecto o aprende algo nuevo, convierte cada unidad de conocimiento en un **glyph**: un vector de 1024 dimensiones.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                  │
│  "Generate a JWT token for the user"                            │
│                                                                  │
│         │ encode_text()                                          │
│         ▼                                                        │
│                                                                  │
│  [0.023, -0.041, 0.087, ..., -0.012, 0.055, 0.031]             │
│   ←──────────── 1024 dimensiones ──────────────────→            │
│                                                                  │
│  Cada dimensión NO tiene significado individual.                 │
│  El significado está DISTRIBUIDO en el patrón completo.         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

La codificación es **determinista** — el mismo texto siempre produce el mismo vector. No usa IA, no gasta tokens. Es puro hashing + proyección aleatoria con semilla fija.

**¿Por qué 1024 dimensiones?** En espacios de alta dimensión, vectores aleatorios son casi ortogonales entre sí (similitud ≈ 0). Esto permite almacenar miles de conceptos sin que se "pisen" unos a otros.

---

### Paso 2: Almacenamiento — Superposición en el Substrate

Los glyphs no se guardan en filas de una tabla. Se **superponen** (suman) en una región del substrate:

```
┌─────────────────────────────────────────────────────────────────┐
│                    SUBSTRATE (Región "default")                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Glyph 1: "JWT authentication"                                  │
│  [0.02, -0.04, 0.08, ..., -0.01, 0.05, 0.03]                   │
│                          +                                       │
│  Glyph 2: "Token refresh endpoint"                              │
│  [0.05, 0.01, -0.03, ..., 0.07, -0.02, 0.04]                   │
│                          +                                       │
│  Glyph 3: "Session timeout bug"                                 │
│  [-0.01, 0.06, 0.02, ..., 0.03, 0.08, -0.05]                   │
│                          =                                       │
│  ─────────────────────────────────────────────                   │
│  Región:                                                         │
│  [0.06, 0.03, 0.07, ..., 0.09, 0.11, 0.02]                     │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │ Los 3 glyphs COEXISTEN en el mismo     │                    │
│  │ vector. No hay filas separadas.         │                    │
│  │ El tamaño de la región es CONSTANTE     │                    │
│  │ (1024 floats) sin importar cuántos      │                    │
│  │ glyphs se almacenen.                   │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**¿Cómo es posible que no se pierdan?** Porque en 1024 dimensiones, vectores aleatorios son casi ortogonales. Cada glyph "vive" en su propia dirección del espacio. Al sumarlos, no se destruyen — coexisten como ondas superpuestas.

---

### Paso 3: Relaciones — Codificación holográfica (sin edges)

En un grafo, la relación "A está conectado con B" se almacena como un edge explícito en una tabla. En GLIA, las relaciones se codifican **dentro del mismo espacio vectorial** usando convolución circular:

```
┌─────────────────────────────────────────────────────────────────┐
│                    BINDING (Convolución Circular)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Concepto A: "generate_token"                                    │
│  [0.02, -0.04, 0.08, ...]                                       │
│                                                                  │
│  Concepto B: "jwt_secret"                                        │
│  [0.05, 0.01, -0.03, ...]                                       │
│                                                                  │
│         bind(A, B) = convolución_circular(A, B)                  │
│                                                                  │
│  Resultado: [0.07, -0.02, 0.01, ...]                            │
│                                                                  │
│  ┌─────────────────────────────────────────┐                    │
│  │ Propiedades del binding:                │                    │
│  │                                         │                    │
│  │ • bind(A,B) es DISTINTO a A y a B       │                    │
│  │ • unbind(bind(A,B), A) ≈ B              │                    │
│  │ • No crea ningún "edge" explícito       │                    │
│  │ • La relación VIVE en el vector mismo   │                    │
│  └─────────────────────────────────────────┘                    │
│                                                                  │
│  Este binding se SUMA al substrate:                              │
│  substrate += bind(A, B)                                         │
│                                                                  │
│  Ahora, si en el futuro preguntas por A,                        │
│  el substrate "resuena" también con B                            │
│  porque su interferencia está codificada ahí.                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**No hay tabla de edges. No hay lista de relaciones. Las relaciones son patrones de interferencia dentro del mismo vector.**

---

### Paso 4: Recuperación — Resonancia (no búsqueda)

Cuando preguntas algo, GLIA no busca en una tabla. Codifica tu pregunta como vector y lo **proyecta** contra todos los glyphs simultáneamente:

```
┌─────────────────────────────────────────────────────────────────┐
│                    RESONANCIA                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Query: "¿por qué expiran los tokens?"                          │
│         │                                                        │
│         ▼ encode_text()                                          │
│  Stimulus: [0.03, -0.02, 0.06, ..., 0.01, 0.04, -0.03]        │
│         │                                                        │
│         ▼ comparar contra TODOS los glyphs (paralelo)          │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐       │
│  │                                                       │       │
│  │  cosine(stimulus, glyph_1) = 0.69  ← ¡RESUENA!     │       │
│  │  cosine(stimulus, glyph_2) = 0.13                    │       │
│  │  cosine(stimulus, glyph_3) = 0.12                    │       │
│  │  cosine(stimulus, glyph_4) = 0.04                    │       │
│  │  cosine(stimulus, glyph_5) = 0.02                    │       │
│  │  ...                                                  │       │
│  │  cosine(stimulus, glyph_N) = 0.01                    │       │
│  │                                                       │       │
│  │  Todos se comparan AL MISMO TIEMPO.                   │       │
│  │  No hay traversal secuencial.                         │       │
│  │  No hay "siguiente nodo".                             │       │
│  │  Es proyección paralela.                              │       │
│  │                                                       │       │
│  └──────────────────────────────────────────────────────┘       │
│                                                                  │
│  Resultado: Los glyphs que "resuenan" (alta similitud)         │
│  son los que comparten patrón con tu pregunta.                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**La diferencia clave con un grafo:** En un grafo, si no hay un camino de edges entre A y B, nunca los conectas. En GLIA, si A y B comparten patrón (aunque nunca se hayan "conectado" explícitamente), resuenan juntos.

---

### Paso 5: Plasticidad — La memoria está viva

Los glyphs no son estáticos. Tienen **magnitud** (volumen) que cambia con el uso:

```
┌─────────────────────────────────────────────────────────────────┐
│                    PLASTICIDAD                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  REFUERZO (Hebbiano): Cada vez que un glyph resuena            │
│  en una consulta, su magnitud SUBE.                             │
│                                                                  │
│  Día 1:  jwt_auth  magnitud: 1.0  ████████████                  │
│  Día 5:  jwt_auth  magnitud: 1.2  ██████████████  (se usó 4x)  │
│  Día 10: jwt_auth  magnitud: 1.4  ████████████████ (se usó 8x) │
│                                                                  │
│  Los patrones frecuentes "suenan más fuerte" en futuras         │
│  consultas. Se vuelven más fáciles de encontrar.                │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  DECAIMIENTO: Los glyphs que NO se usan pierden magnitud.      │
│                                                                  │
│  Día 1:  old_framework  magnitud: 1.0  ████████████             │
│  Día 30: old_framework  magnitud: 0.7  ████████  (no se usó)   │
│  Día 90: old_framework  magnitud: 0.3  ████     (sigue sin uso)│
│  Día 180: old_framework magnitud: 0.0  (olvidado)              │
│                                                                  │
│  La memoria se AUTO-LIMPIA. Solo sobrevive lo relevante.        │
│                                                                  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                  │
│  CO-ACTIVACIÓN: Si dos glyphs resuenan juntos en la misma      │
│  consulta, se crea un binding entre ellos en el substrate.      │
│                                                                  │
│  Consulta activa jwt_auth Y session_bug al mismo tiempo         │
│  → substrate += bind(jwt_auth, session_bug) × 0.02             │
│  → En futuras consultas, preguntar por uno activará al otro     │
│                                                                  │
│  "Lo que resuena junto, se asocia más fuerte."                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Paso 6: El output — Mapa Cognitivo

GLIA no devuelve texto crudo ni archivos completos. Devuelve un **mapa cognitivo** estructurado:

```
## GLIA Cognitive Map for: "generar token JWT"

### Resonating Patterns (by strength)
  • [0.69] auth_generate_token: Generate a JWT-like token for the user. (src/auth.py)
  • [0.13] auth_verify_token: Verify and decode a token. (src/auth.py)
  • [0.12] module_auth: Authentication module - JWT token management. (src/auth.py)
  • [0.05] app_login: Authenticate user and return JWT token. (src/app.py)

### Source Files
  → src/auth.py
  → src/app.py
```

El agente recibe:
- **Qué patrones resonaron** (y con qué fuerza)
- **Qué significa cada uno** (intención en 1 línea)
- **Dónde buscar** si necesita más detalle

No recibe bloques de texto para descifrar. Recibe un mapa de navegación.

---

### Flujo completo de una sesión

```
┌─────────────────────────────────────────────────────────────────┐
│                     SESIÓN DE TRABAJO                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. MCP Server arranca                                           │
│     ├──▶ Detecta archivos cambiados (compara hashes)            │
│     ├──▶ Re-escanea con AST los modificados (gratis)            │
│     └──▶ Substrate actualizado con nuevos glyphs               │
│                                                                  │
│  2. Usuario pregunta: "¿por qué falla el login?"               │
│     ├──▶ Agente llama glia_recall("login falla")               │
│     ├──▶ Query se codifica como vector                          │
│     ├──▶ Resonancia paralela contra todos los glyphs           │
│     ├──▶ Top-K glyphs resonantes se refuerzan (+magnitud)      │
│     ├──▶ Co-activación entre los top results                    │
│     └──▶ Mapa cognitivo devuelto al agente                     │
│                                                                  │
│  3. Agente arregla el bug                                        │
│     ├──▶ Agente llama glia_learn("El login fallaba porque...")  │
│     ├──▶ Gemini Flash destila en conceptos                      │
│     ├──▶ Cada concepto se codifica como glyph                  │
│     ├──▶ Relaciones se codifican como bindings                  │
│     └──▶ Todo se superpone en el substrate                      │
│                                                                  │
│  4. Dev hace commit                                              │
│     ├──▶ Git hook captura mensaje + archivos                    │
│     └──▶ Se registra como conocimiento histórico                │
│                                                                  │
│  5. Pasa el tiempo sin usar ciertos conceptos                   │
│     ├──▶ Decaimiento reduce magnitud de glyphs no usados       │
│     └──▶ Glyphs con magnitud 0 se olvidan efectivamente       │
│                                                                  │
│  ═══════════════════════════════════════════════════════════     │
│  RESULTADO: La memoria CRECE con lo relevante                    │
│             y OLVIDA lo obsoleto — automáticamente               │
│  ═══════════════════════════════════════════════════════════     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### ¿Por qué esto NO es un grafo?

| Propiedad | Grafo | GLIA |
|---|---|---|
| Estructura | Nodos + Aristas explícitas | Vectores superpuestos en un espacio continuo |
| Relaciones | Tabla de edges | Patrones de interferencia (bindings) |
| Recuperación | Traversal secuencial (BFS/DFS) | Proyección paralela (cosine similarity) |
| Si borras 30% | Pierdes caminos completos | Sigue funcionando (propiedad holográfica) |
| Analogías | Imposible | Nativo (aritmética vectorial) |
| Storage | Crece con cada relación (O(N²)) | Constante por región (O(D)) |
| Tabla de edges en DB | Sí | **NO** |

Si abres el `memory.db` de GLIA, encontrarás tablas `substrate_regions` y `glyphs`. **No encontrarás ninguna tabla de edges o relaciones.** Las relaciones no existen como registros — existen como interferencias matemáticas dentro de los vectores.

---

## Benchmarks

GLIA fue evaluado contra Graph (Spreading Activation) y BM25 (Elasticsearch) en tres proyectos de dominios distintos, usando métricas estándar de Information Retrieval (MRR, nDCG, Precision@K) con conteo real de tokens (tiktoken).

### Resultados (modo local, $0, sin embeddings)

| Proyecto | GLIA | Graph (SA) | BM25 | GLIA vs Graph |
|----------|------|-----------|------|---------------|
| E-Commerce (Python, 31 archivos) | MRR **0.771** | 0.409 | 0.785 | **+88%** |
| ML Pipeline (Python, 27 archivos) | MRR **0.904** | 0.203 | 0.941 | **+344%** |
| Frontend (TypeScript, 32 archivos) | MRR **0.877** | 0.421 | 0.885 | **+108%** |

### Eficiencia

| Métrica | Valor promedio |
|---------|---------------|
| Token savings | **97.8%** (compresión 47x) |
| Latencia | **94ms** promedio |
| Scan | **3.4s** promedio, $0 |
| Edges | **0** (holográfico) |

### GLIA vs RAG (Gemini Embeddings)

| Sistema | MRR | Costo |
|---------|-----|-------|
| RAG (Gemini embedding-001) | 0.873 | ~$0.001/query |
| **GLIA (local)** | 0.783 | **$0** |
| GLIA + embeddings (opcional) | 0.835 | ~$0.001/query |

**Conclusión:** GLIA supera a grafos tradicionales por 2.5x. Iguala a BM25 (-2.2%). Pierde contra RAG en precisión pura (-10%) pero a $0 de costo y con capacidades que RAG no tiene (plasticidad, unbinding, offline).

### 🛡️ Integridad Metodológica

Nuestros benchmarks no son estimaciones; son pruebas rigurosas diseñadas bajo estándares de Information Retrieval:
1. **Evaluación Zero-Shot:** GLIA no fue pre-entrenado en los proyectos de prueba. Todas las evaluaciones son *zero-shot* usando el escáner AST estándar.
2. **Métricas de Industria:** Usamos **MRR** (Mean Reciprocal Rank) y **nDCG** en lugar de métricas subjetivas, garantizando que el orden y la precisión del contexto entregado son óptimos para el LLM.
3. **Cálculo Real de Tokens:** El ahorro del 97% no es una aproximación (caracteres / 4). Se mide usando `tiktoken` (cl100k_base), reflejando exactamente el impacto en tu factura de API.
4. **Reproducibilidad:** Todos los scripts de evaluación (`run_benchmark_v2.py`) y los repositorios de prueba (e-commerce, ML pipeline, frontend) están incluidos en el repositorio para verificación pública.

📊 [Ver benchmarks completos](docs/benchmarks/BENCHMARK_SUMMARY.md)

---

## Comandos CLI

| Comando | Qué hace | Costo |
|---|---|---|
| `python -m glia init` | Inicializar GLIA en el directorio actual | Gratis |
| `python -m glia scan` | Escanear proyecto con AST (todos los lenguajes) | Gratis |
| `python -m glia recall "query"` | Recuperar por resonancia | Gratis |
| `python -m glia learn "texto"` | Enseñar conocimiento nuevo (destilación IA) | Tokens |
| `python -m glia stats` | Estadísticas de la memoria | Gratis |
| `python -m glia forget` | Aplicar decaimiento temporal | Gratis |
| `python -m glia changes` | Detectar archivos modificados manualmente | Gratis |
| `python -m glia hook` | Instalar git hook post-commit | Gratis |
| `python -m glia serve` | Iniciar servidor MCP | Gratis |
| `python -m glia context "query"` | Obtener contexto crudo para inyectar en LLM | Gratis |

---

## Integración MCP (IDE / CLI)

GLIA se expone como servidor MCP compatible con cualquier cliente MCP.

### Cline (VS Code)

En la configuración MCP de Cline:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "C:\\ruta\\a\\tu\\proyecto",
        "GEMINI_API_KEY": "tu_key",
        "GLIA_MODEL": "gemini-3.1-flash-lite-preview"
      }
    }
  }
}
```

### Gemini CLI

Crear `.gemini/settings.json` en tu proyecto:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": ".",
        "GEMINI_API_KEY": "tu_key",
        "GLIA_MODEL": "gemini-3.1-flash-lite-preview"
      }
    }
  }
}
```

### Claude Desktop

Editar `%APPDATA%\Claude\claude_desktop_config.json` (Windows) o `~/Library/Application Support/Claude/claude_desktop_config.json` (Mac):

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "/ruta/a/proyecto",
        "GEMINI_API_KEY": "tu_key"
      }
    }
  }
}
```

### Cursor

Crear `.cursor/mcp.json` en la raíz del proyecto:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": ".",
        "GEMINI_API_KEY": "tu_key"
      }
    }
  }
}
```

---

## Herramientas MCP disponibles

| Herramienta | Descripción | Costo |
|---|---|---|
| `glia_recall(query, top_k)` | Recuperar contexto por resonancia | Gratis |
| `glia_learn(content, source)` | Enseñar conocimiento nuevo | Tokens |
| `glia_scan(path)` | Escanear proyecto con AST | Gratis |
| `glia_learn_file(file_path)` | Re-escanear un archivo específico | Gratis |
| `glia_stats()` | Estadísticas de memoria | Gratis |
| `glia_forget(decay_rate)` | Aplicar decaimiento temporal | Gratis |
| `glia_changes()` | Detectar archivos modificados | Gratis |

---

## Lenguajes soportados

El scanner AST extrae funciones, clases, métodos, imports y dependencias de:

Python • JavaScript • TypeScript • Java • Go • Rust • C# • C/C++ • Ruby • PHP • Kotlin • Swift • Gherkin (.feature) • Markdown • Archivos de configuración (JSON, YAML, TOML)

---

## Cómo funciona

GLIA usa **Memoria Holográfica Distribuida** basada en Vector Symbolic Architectures (VSA):

1. **Codificación**: Texto/código → vector de 1024 dimensiones (determinista, sin IA)
2. **Almacenamiento**: Glyphs se superponen en regiones del substrate (suma vectorial)
3. **Relaciones**: Codificadas holográficamente via convolución circular (sin edges)
4. **Recuperación**: Query → vector → similitud coseno contra todos los glyphs (paralelo)
5. **Plasticidad**: Patrones usados se refuerzan, los no usados decaen

```
Query: "generar token JWT"
         │
         ▼ encode_text()
    [vector 1024-d]
         │
         ▼ resonate() — comparación paralela
         │
    ┌────┴────────────────────────────────────────┐
    │  auth_generate_token  (0.69)  ← resonó!     │
    │  auth_verify_token    (0.13)                 │
    │  module_auth          (0.12)                 │
    │  app_login            (0.05)                 │
    └─────────────────────────────────────────────┘
```

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para diagramas detallados.

---

## Flujo de trabajo recomendado

```bash
# Setup inicial (una vez)
python -m glia init
python -m glia scan
python -m glia hook
# Configurar MCP en tu IDE

# Después trabaja normalmente — GLIA aprende automáticamente:
# • El agente llama glia_learn después de arreglar bugs o tomar decisiones
# • El git hook captura mensajes de commit
# • Archivos modificados se re-escanean al reconectar el MCP server
```

---

## Demo (sin API key)

```bash
python examples/demo_v2.py
```

Demuestra: resonancia, one-shot learning, degradación graceful, razonamiento analógico, queries conjuntivas y eficiencia de storage.

---

## Requisitos

- **Python 3.11+**
- **numpy**
- **Git** (para el hook automático)
- **Gemini API Key** (opcional — solo para `glia learn`)

---

## Estructura del proyecto

```
glia/
├── src/glia/
│   ├── binding.py           # Convolución circular (bind/unbind)
│   ├── encoder.py           # Codificación determinista texto→vector
│   ├── synonyms.py          # Diccionario de sinónimos de programación
│   ├── substrate.py         # Regiones de memoria con superposición
│   ├── resonance.py         # Recuperación por proyección paralela + unbinding
│   ├── plasticity.py        # Refuerzo Hebbiano + decaimiento temporal
│   ├── cognitive_map.py     # Output estructurado para LLMs
│   ├── brain.py             # Orquestador principal
│   ├── storage.py           # Persistencia SQLite (sin tabla de edges)
│   ├── embeddings.py        # Embeddings opcionales (Gemini, modo enhanced)
│   ├── distiller.py         # Destilación con LLM (Gemini Flash)
│   ├── ast_scanner_v2.py    # Scanner multi-lenguaje para substrate
│   ├── scanner.py           # Scanner de proyecto (incremental)
│   ├── mcp_server.py        # Servidor MCP
│   └── cli.py               # Interfaz de línea de comandos
├── docs/
│   ├── ARCHITECTURE.md      # Arquitectura detallada con diagramas
│   └── benchmarks/          # Resultados de benchmarks
├── benchmarks/              # Scripts de benchmark reproducibles
├── examples/
│   └── demo_v2.py           # Demo de capacidades holográficas
└── benchmark_project*/      # Proyectos de prueba para benchmarks
```

---

## Troubleshooting

**"glia" no se reconoce** → Usa `python -m glia` o agrega Python Scripts al PATH.

**El MCP server no conecta** → Verifica que `python -m glia.mcp_server` corre sin errores. Verifica que `GLIA_WORKSPACE` apunta a un directorio con `.glia/` inicializado.

**"No resonating patterns"** → Ejecuta `python -m glia scan` primero, luego `python -m glia stats` para verificar que hay glyphs.

**"resource busy or locked"** → Desconecta el MCP server en tu IDE antes de borrar `.glia/`.

---

## Autor

**Felipe Farías Alfaro**
- GitHub: [FelipeFariasAlfaro](https://github.com/FelipeFariasAlfaro)
- Web: [felipefariasalfaro.github.io](https://felipefariasalfaro.github.io)

---

## Licencia

[MIT](LICENSE)
