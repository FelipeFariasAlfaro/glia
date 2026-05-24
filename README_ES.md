# 🧠 GLIA - Memoria Holográfica Distribuida para Agentes de IA

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-green.svg)](https://modelcontextprotocol.io/)
[![Multi-Provider](https://img.shields.io/badge/AI-Gemini%20|%20OpenAI%20|%20Claude-blueviolet.svg)](#configuración)

**GLIA** es un sistema de memoria persistente para agentes de IA basado en **Memoria Holográfica Distribuida (HDM)**. Proporciona a los agentes contexto epistémico a largo plazo entre sesiones. No es un grafo. No es RAG. Es una arquitectura genuinamente distinta donde el conocimiento se almacena como patrones distribuidos en un espacio vectorial de alta dimensión, y la recuperación funciona por **resonancia** — proyección paralela de patrones, no búsqueda de texto ni traversal de nodos.

**Funciona con cualquier proyecto** (Python, JavaScript, TypeScript, Java, Go, Rust, C#, C/C++, Ruby, PHP, Kotlin, Swift, y más). GLIA es una herramienta escrita en Python que analiza y memoriza cualquier codebase.

---

## Tabla de Contenidos

- [Instalación](#instalación)
- [Configuración](#configuración)
- [Inicio Rápido](#inicio-rápido)
- [Comandos CLI](#comandos-cli)
- [Integración MCP (IDE / CLI)](#integración-mcp-ide--cli)
- [Instruir al agente para que use GLIA](#instruir-al-agente-para-que-use-glia)
- [Herramientas MCP disponibles](#herramientas-mcp-disponibles)
- [Lenguajes soportados](#lenguajes-soportados)
- [Flujo de trabajo recomendado](#flujo-de-trabajo-recomendado)
- [Estructura de carpetas](#estructura-de-carpetas)
- [¿Qué problema resuelve?](#qué-problema-resuelve)
- [¿Cómo funciona GLIA por dentro?](#cómo-funciona-glia-por-dentro)
- [Demo](#demo-sin-api-key)
- [Requisitos](#requisitos)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Troubleshooting](#troubleshooting)
- [Benchmarks](#benchmarks)
- [Autor](#autor)

---

## Instalación

GLIA se instala **una vez** en tu máquina como herramienta global.

```bash
# Instalar desde PyPI (Gemni)
pip install glia-memory

# Con soporte OpenAI
pip install glia-memory[openai]

# Con soporte Anthropic (Claude)
pip install glia-memory[anthropic]

# Todos los providers
pip install glia-memory[all]
```

O instalar desde el código fuente (para desarrollo):

```bash
git clone https://github.com/FelipeFariasAlfaro/glia.git
cd glia
pip install -e ".[all]"
```

---

## Configuración

Crea un archivo `glia.env` en la raíz de tu proyecto:

```ini
# Provider: gemini, openai, o anthropic
GLIA_PROVIDER=gemini

# API key del provider elegido
GEMINI_API_KEY=tu_key_aqui
# OPENAI_API_KEY=tu_key_aqui
# ANTHROPIC_API_KEY=tu_key_aqui

# Modelo (opcional — usa el default del provider si no se especifica)
# siempre es mejor ingresar el modelo manualmente
# GLIA_MODEL=gemini-2.5-flash
```

| Provider | Modelo default | Obtener key |
|---|---|---|
| `gemini` | `gemini-2.5-flash` | https://aistudio.google.com/apikey |
| `openai` | `gpt-4o-mini` | https://platform.openai.com/api-keys |
| `anthropic` | `claude-sonnet-4-20250514` | https://console.anthropic.com/ |

> **Nota:** La API key solo se necesita para `glia learn`. Todos los demás comandos (`scan`, `recall`, `stats`, `forget`, `changes`) funcionan **offline sin API key ni costo**.

> **Nota:** Si no se encuentra `glia.env`, GLIA busca `.env` como fallback por retrocompatibilidad. Usar `glia.env` evita conflictos con el `.env` propio de tu proyecto.

---

## Inicio Rápido

```bash
# 1. Inicializar GLIA en tu proyecto
python -m glia init

# 2. Escanear tu codebase (gratis, usa parseo AST)
python -m glia scan

# 3. Consultar la memoria
python -m glia recall "flujo de autenticación"

# 4. Enseñar algo nuevo (usa IA)
python -m glia learn "El bug de sesiones era porque el token expiraba en ms en vez de segundos"

# 5. Instalar git hook para aprendizaje automático
python -m glia hook
```

---

## Comandos CLI

| Comando | Qué hace | Costo |
|---|---|---|
| `glia init` | Inicializar GLIA en el directorio actual | Gratis |
| `glia scan` | Escanear proyecto con AST (todos los lenguajes) | Gratis |
| `glia recall "query"` | Recuperar por resonancia | Gratis |
| `glia learn "texto"` | Enseñar conocimiento nuevo (destilación IA) | Tokens |
| `glia watch` | Monitorear archivos y re-escanear al guardar (tiempo real) | Gratis |
| `glia stats` | Estadísticas de la memoria | Gratis |
| `glia forget` | Aplicar decaimiento temporal | Gratis |
| `glia changes` | Detectar archivos modificados manualmente | Gratis |
| `glia hook` | Instalar git hook post-commit | Gratis |
| `glia serve` | Iniciar servidor MCP | Gratis |
| `glia context "query"` | Obtener contexto crudo para inyectar en LLM | Gratis |

### Detalle de comandos

**`glia init`**
Crea una carpeta `.glia/` en tu proyecto con la base de datos de memoria. Se ejecuta una vez por proyecto.

**`glia scan`**
Parsea todos los archivos fuente usando AST (Abstract Syntax Tree) y almacena la estructura (funciones, clases, métodos, imports) como glyphs en la memoria. Incremental — solo re-escanea archivos que cambiaron desde el último scan. Soporta 15+ lenguajes.

**`glia recall "query"`**
Codifica tu consulta como vector y encuentra patrones que resuenan con ella. Devuelve un mapa cognitivo mostrando qué conceptos coincidieron y dónde encontrarlos. No necesita IA — pura matemática.

**`glia learn "texto"`**
Envía texto a tu provider de IA configurado (Gemini/OpenAI/Claude) que lo destila en conceptos y relaciones, luego los almacena como glyphs. Úsalo para conocimiento que no está en el código: explicaciones de bugs, decisiones arquitectónicas, reglas de negocio.

**`glia watch`**
Corre en segundo plano monitoreando la carpeta del proyecto. Cuando guardas un archivo, automáticamente lo re-escanea con AST (gratis). Mantiene la memoria sincronizada con tu código en tiempo real sin intervención manual.

**`glia stats`**
Muestra cuántos conceptos (glyphs) hay almacenados, la dimensión vectorial y el número de regiones.

**`glia forget`**
Aplica decaimiento temporal a todos los glyphs. Los patrones que no se han usado pierden magnitud. Los que llegan a magnitud cero se olvidan efectivamente. Úsalo periódicamente para mantener la memoria limpia.

**`glia changes`**
Compara hashes de archivos contra el último scan para detectar cuáles fueron modificados manualmente. Útil para saber qué cambió entre sesiones.

**`glia hook`**
Instala un git hook post-commit que automáticamente llama `glia learn` con el mensaje del commit y los archivos cambiados después de cada commit. Esto captura la *intención* detrás de los cambios (cuesta tokens por commit).

**`glia serve`**
Inicia el servidor MCP en transporte stdio. Lo usan los IDEs (Kiro, Cursor, Cline, etc.) para conectarse a GLIA.

**`glia context "query"`**
Como `recall` pero solo muestra el string de contexto crudo (sin formato). Diseñado para pipear a otras herramientas o prompts de LLM.

---

## Integración MCP (IDE / CLI)

GLIA se expone como servidor MCP compatible con cualquier cliente MCP. El provider se configura via `glia.env` en tu proyecto, o via variables de entorno en la config MCP.

### Kiro

En `.kiro/settings/mcp.json`:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "."
      }
    }
  }
}
```

### Cline (VS Code)

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "C:\\ruta\\a\\tu\\proyecto"
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
        "GLIA_WORKSPACE": "."
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
        "GLIA_WORKSPACE": "/ruta/a/proyecto"
      }
    }
  }
}
```

### Antigravity (Google)

Click en "Manage MCP Servers" → "View raw config" para abrir `mcp_config.json`, luego agrega:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": "."
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
        "GLIA_WORKSPACE": "."
      }
    }
  }
}
```

### Sobreescribir provider via config MCP

Si quieres usar un provider distinto al de `glia.env`, pásalo como variables de entorno:

```json
{
  "mcpServers": {
    "glia": {
      "command": "python",
      "args": ["-m", "glia.mcp_server"],
      "env": {
        "GLIA_WORKSPACE": ".",
        "GLIA_PROVIDER": "openai",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

---

## Instruir al agente para que use GLIA

Conectar el servidor MCP no es suficiente — necesitas decirle al agente **cuándo y cómo** usar GLIA. Sin instrucciones explícitas, la mayoría de los agentes no consultarán GLIA por su cuenta.

### Regla de sistema recomendada (agregar a las reglas del agente en tu IDE)

```
## GLIA Memory

Tienes acceso a GLIA, una memoria persistente del proyecto via MCP.

**SIEMPRE haz esto:**
- Al INICIO de cada tarea, llama `glia_recall` con el tema en el que vas a trabajar. Esto te da contexto sobre decisiones pasadas, bugs y arquitectura.
- Después de arreglar un bug o tomar una decisión importante, llama `glia_learn` para registrar qué hiciste y por qué.
- Cuando modifiques un archivo significativamente, llama `glia_learn_file` para que la memoria se mantenga actualizada.

**Ejemplos:**
- Antes de arreglar un bug: `glia_recall("error autenticación login")`
- Después de arreglarlo: `glia_learn("El login fallaba porque el token JWT expiraba en milisegundos en vez de segundos. Se arregló en auth_service.py convirtiendo a segundos.")`
- Después de una decisión de diseño: `glia_learn("Se eligió PostgreSQL sobre MongoDB para el servicio de órdenes porque necesitamos transacciones ACID para pagos.")`
```

### Dónde poner esta regla en cada IDE

| IDE | Archivo / Ubicación |
|---|---|
| **Kiro** | `.kiro/steering/glia.md` |
| **Cursor** | `.cursor/rules/glia.mdc` o `.cursorrules` |
| **Cline** | `.clinerules` |
| **Claude Desktop** | Incluir en tu system prompt |
| **Antigravity** | `AGENTS.md` o `GEMINI.md` en la raíz del proyecto |
| **Gemini CLI** | `GEMINI.md` en la raíz del proyecto |
| **Windsurf** | `.windsurfrules` |

### Ejemplo: Steering file para Kiro

Crear `.kiro/steering/glia.md`:

```markdown
---
inclusion: auto
---

## GLIA Memory System

Este proyecto usa GLIA para memoria persistente entre sesiones.

Antes de comenzar cualquier tarea, llama `glia_recall` con el tema relevante para obtener contexto sobre decisiones pasadas y bugs.

Después de completar una tarea, llama `glia_learn` para registrar:
- Qué se hizo
- Por qué se hizo así
- Cualquier gotcha o lección aprendida

Esto asegura que futuras sesiones tengan contexto completo sin tener que redescubrir todo.
```

### Ejemplo: Reglas para Cursor

Crear `.cursor/rules/glia.mdc`:

```
---
description: Integración con memoria GLIA
globs: **/*
alwaysApply: true
---

Tienes acceso a la memoria GLIA via herramientas MCP.

SIEMPRE llama glia_recall al inicio de una tarea para verificar contexto existente.
SIEMPRE llama glia_learn después de arreglar bugs o tomar decisiones arquitectónicas.
```

### Ejemplo: Antigravity (AGENTS.md)

Crear `AGENTS.md` en la raíz del proyecto:

```markdown
# Agent Instructions

## Memory
Usa las herramientas MCP de GLIA para memoria persistente:
- `glia_recall(query)` — Consultar memoria antes de empezar a trabajar
- `glia_learn(content, source)` — Registrar decisiones y bug fixes
- `glia_scan()` — Re-escanear después de refactors grandes
```

### Pro tip: El git hook maneja los commits automáticamente

Si ejecutaste `python -m glia hook`, los mensajes de commit ya se capturan automáticamente. Las reglas de arriba son para enseñarle al agente a usar GLIA **durante** la sesión — para el razonamiento y decisiones que no terminan en mensajes de commit.

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

## Estructura de carpetas

```
~/tools/glia/                  ← Código fuente de GLIA (se clona una vez)
    src/glia/
    pyproject.toml

~/projects/mi-api/             ← TU proyecto
    .glia/                     ← Creado por 'glia init' (agregar a .gitignore)
        memory.db              ← Memoria holográfica de este proyecto
    glia.env                   ← Config del provider (agregar a .gitignore)
    src/
    ...

~/projects/otro-proyecto/      ← Otro proyecto (memoria separada)
    .glia/
        memory.db
    glia.env
    ...
```

Cada proyecto tiene su propia memoria. GLIA se instala una vez y se usa en muchos proyectos.

---

## ¿Qué problema resuelve?

Los agentes de IA (Cline, Claude, Cursor, Copilot, Kiro, etc.) pierden contexto entre sesiones. Cada chat nuevo empieza de cero — sin memoria de bugs pasados, decisiones arquitectónicas, ni cómo se relacionan las partes del proyecto.

GLIA resuelve esto manteniendo una **memoria relacional persistente** que crece con cada interacción y se fortalece con el uso.

---

## ¿Cómo funciona GLIA por dentro?

### La analogía: El cerebro no es un disco duro

Cuando recuerdas el aroma de un pastel, tu cerebro no busca en una carpeta llamada "Recuerdos/Pasteles/aroma.txt". Un estímulo pequeño (el olor) **activa un patrón** de neuronas que, por interferencia, reconstruye el recuerdo completo: la cocina, tu abuela, la conversación que tuviste.

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
│  Vector de la región:                                            │
│  [0.06, 0.03, 0.07, ..., 0.09, 0.11, 0.02]                     │
│                                                                  │
│  Los 3 glyphs COEXISTEN en el mismo vector.                     │
│  El tamaño de la región es CONSTANTE (1024 floats)              │
│  sin importar cuántos glyphs se almacenen.                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Paso 3: Relaciones — Codificación holográfica (sin edges)

En un grafo, "A está conectado con B" se almacena como un edge explícito. En GLIA, las relaciones se codifican **dentro del mismo espacio vectorial** usando convolución circular:

```
bind(A, B) = convolución_circular(A, B)

Propiedades:
• bind(A,B) es DISTINTO a A y a B
• unbind(bind(A,B), A) ≈ B
• No crea ningún "edge" explícito
• La relación VIVE en el vector mismo
```

**No hay tabla de edges. Las relaciones son patrones de interferencia dentro de los vectores.**

---

### Paso 4: Recuperación — Resonancia (no búsqueda)

Cuando preguntas algo, GLIA codifica tu pregunta como vector y lo **proyecta** contra todos los glyphs simultáneamente:

```
Query: "¿por qué expiran los tokens?"
         │
         ▼ encode_text()
    [vector stimulus 1024-d]
         │
         ▼ similitud coseno contra TODOS los glyphs (paralelo)
         │
    cosine(stimulus, glyph_1) = 0.69  ← ¡RESUENA!
    cosine(stimulus, glyph_2) = 0.13
    cosine(stimulus, glyph_3) = 0.12
    ...
    cosine(stimulus, glyph_N) = 0.01
```

**Diferencia clave con un grafo:** En un grafo, si no hay camino entre A y B, nunca los conectas. En GLIA, si A y B comparten patrón (aunque nunca se hayan "conectado" explícitamente), resuenan juntos.

---

### Paso 5: Plasticidad — La memoria está viva

- **Refuerzo (Hebbiano):** Cada vez que un glyph resuena, su magnitud sube. Los patrones frecuentes "suenan más fuerte" en futuras consultas.
- **Decaimiento:** Los glyphs que NO se usan pierden magnitud con el tiempo. La memoria se auto-limpia.
- **Co-activación:** Si dos glyphs resuenan juntos, se crea un binding entre ellos. "Lo que resuena junto, se asocia más fuerte."

---

### ¿Por qué esto NO es un grafo?

| Propiedad | Grafo | GLIA |
|---|---|---|
| Estructura | Nodos + Aristas explícitas | Vectores superpuestos en espacio continuo |
| Relaciones | Tabla de edges | Patrones de interferencia (bindings) |
| Recuperación | Traversal secuencial (BFS/DFS) | Proyección paralela (cosine similarity) |
| Si borras 30% | Pierdes caminos completos | Sigue funcionando (propiedad holográfica) |
| Analogías | Imposible | Nativo (aritmética vectorial) |
| Storage | Crece con cada relación O(N²) | Constante por región O(D) |
| Tabla de edges en DB | Sí | **NO** |

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
- **API Key** (opcional — solo para `glia learn`, cualquier provider soportado)

---

## Estructura del proyecto

```
glia/
├── src/glia/
│   ├── config.py            # Configuración multi-provider (glia.env)
│   ├── binding.py           # Convolución circular (bind/unbind)
│   ├── encoder.py           # Codificación determinista texto→vector
│   ├── synonyms.py          # Diccionario de sinónimos de programación
│   ├── substrate.py         # Regiones de memoria con superposición
│   ├── resonance.py         # Recuperación por proyección paralela + unbinding
│   ├── plasticity.py        # Refuerzo Hebbiano + decaimiento temporal
│   ├── cognitive_map.py     # Output estructurado para LLMs
│   ├── brain.py             # Orquestador principal
│   ├── storage.py           # Persistencia SQLite (sin tabla de edges)
│   ├── embeddings.py        # Embeddings opcionales (modo enhanced)
│   ├── distiller.py         # Destilación multi-provider
│   ├── ast_scanner_v2.py    # Scanner multi-lenguaje para substrate
│   ├── scanner.py           # Scanner de proyecto (incremental)
│   ├── mcp_server.py        # Servidor MCP
│   └── cli.py               # Interfaz de línea de comandos
├── docs/
│   └── ARCHITECTURE.md      # Arquitectura detallada con diagramas
├── benchmarks/
│   ├── projects/            # Proyectos de prueba (ecommerce, ml_pipeline, frontend)
│   ├── results/             # Reportes de resultados
│   ├── benchmark_vs_graph.py
│   ├── benchmark_vs_rag.py
│   └── run_benchmark_v2.py  # Script principal de benchmark
└── tests/                   # Tests unitarios
```

---

## Troubleshooting

**"glia" no se reconoce** → Usa `python -m glia` o agrega Python Scripts al PATH.

**El MCP server no conecta** → Verifica que `python -m glia.mcp_server` corre sin errores. Verifica que `GLIA_WORKSPACE` apunta a un directorio con `.glia/` inicializado.

**"No resonating patterns"** → Ejecuta `python -m glia scan` primero, luego `python -m glia stats` para verificar que hay glyphs.

**"resource busy or locked"** → Desconecta el MCP server en tu IDE antes de borrar `.glia/`.

**Errores de provider** → Verifica que tu `glia.env` tiene el `GLIA_PROVIDER` correcto y la API key correspondiente. Ejecuta `python -c "from glia.config import get_config; c = get_config(); print(c.provider, c.model)"` para verificar.

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

### Integridad Metodológica

1. **Evaluación Zero-Shot:** GLIA no fue pre-entrenado en los proyectos de prueba. Todas las evaluaciones son zero-shot usando el escáner AST estándar.
2. **Métricas de Industria:** MRR (Mean Reciprocal Rank) y nDCG garantizan orden óptimo del contexto para el LLM.
3. **Cálculo Real de Tokens:** Medido con `tiktoken` (cl100k_base), no aproximaciones de caracteres.
4. **Reproducibilidad:** Todos los scripts de evaluación y repositorios de prueba están incluidos para verificación pública.

📊 [Ver benchmarks completos](benchmarks/results/BENCHMARK_SUMMARY.md)

---

## Autor

**Felipe Farías Alfaro**
- GitHub: [FelipeFariasAlfaro](https://github.com/FelipeFariasAlfaro)
- Web: [felipefariasalfaro.github.io](https://felipefariasalfaro.github.io)

---

## Licencia

[MIT](LICENSE)
