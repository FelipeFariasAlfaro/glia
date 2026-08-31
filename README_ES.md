# GLIA: Memoria Holográfica Distribuida para Agentes de IA

[Leer en inglés](README.md) | [Changelog](CHANGELOG.md)

Prerelease actual: `0.2.0a0`.

GLIA es un sistema de memoria persistente para agentes de IA basado en Memoria Holográfica Distribuida (HDM). Almacena conocimiento como patrones distribuidos de alta dimensión, lo recupera por resonancia y codifica relaciones como contribuciones holográficas reversibles. No es una base de datos de grafos, un índice BM25 ni un flujo RAG convencional.

GLIA está pensado para agentes que necesitan contexto durable del proyecto: decisiones de arquitectura, estructura de código, procedencia de fuentes, conocimiento operativo y adaptación acotada de la memoria entre sesiones.

## Qué hace GLIA

- Codifica texto y código de forma determinista en vectores de 1024 dimensiones, sin requerir una clave de API.
- Almacena glyphs en regiones de memoria superpuestas y los puntúa mediante resonancia vectorial paralela.
- Codifica asociaciones con binding circular y contribuciones de relación explícitas y reversibles, no con aristas de un grafo.
- Escanea archivos compatibles de forma incremental, rastrea hashes por fuente y elimina contribuciones de archivos borrados o ignorados.
- Ofrece recall estable y de solo lectura por defecto; `adapt` persiste refuerzo hebbiano acotado y `explore` reserva resultados para asociaciones holográficas.
- Persiste memoria por proyecto en SQLite con WAL, durabilidad síncrona completa, revisiones optimistas, validación, backups y recuperación ante contención transitoria.

## Modelo central

```text
texto o código fuente
        |
        v
codificación determinista
        |
        v
glyph vectorial + metadata
        |
        v
superposición en una región
        |
        +-- contribuciones de relación unidas y reversibles
        |
        v
resonancia contra un vector de consulta
        |
        v
glyphs, fuentes y contexto cognitivo ordenados
```

Una región es la suma de cada vector de glyph ponderado por su magnitud más sus contribuciones de relación. Este invariante se valida antes de cada commit persistente. Los glyphs, relaciones y regiones administrados por el sustrato exponen datos vectoriales inmutables; las APIs de mutación soportadas conservan la superposición regional de forma atómica.

GLIA también persiste metadata de glyphs para permitir procedencia, ranking, eliminación por fuente y recuperación exacta. Los vectores regionales tienen dimensión fija, pero la huella durable total incluye metadata de glyphs y relaciones. GLIA no afirma que el tamaño total de la base de datos sea constante al crecer la memoria.

## Confiabilidad y escalabilidad

La implementación actual prioriza un comportamiento predecible ante fallos, escritores concurrentes y crecimiento de memoria.

- Los commits SQLite usan revisiones optimistas. Un escritor obsoleto se rechaza en vez de sobrescribir conocimiento nuevo.
- `GliaBrain` recarga y reaplica mutaciones deterministas después de conflictos de revisión.
- `BEGIN IMMEDIATE` reintenta errores transitorios `SQLITE_BUSY` y `SQLITE_LOCKED` con backoff acotado.
- El seguimiento de cambios escribe sólo regiones, glyphs y relaciones modificados, mientras la reconciliación de membresía detecta diccionarios limpiados externamente y elimina filas obsoletas de forma exacta.
- El estado dirty sólo se limpia después de un commit exitoso. Un conflicto o rollback conserva el trabajo pendiente.
- La carga y el guardado SQLite validan dimensión vectorial, valores finitos, membresía regional, contadores de glyphs y superposición holográfica exacta.
- Las actualizaciones del escáner y su estado se confirman atómicamente. Los fallos por archivo restauran contribuciones y estado de tracking previos.
- La resonancia usa una matriz vectorial cacheada e inmutable. Las consultas repetidas evitan reconstruir la matriz y las mutaciones soportadas invalidan el caché.
- Los backups usan la API de respaldo SQLite y se publican de forma atómica con nombres únicos.

## Instalación

Requisitos:

- Python 3.11 o posterior
- NumPy
- Git para la integración post-commit opcional
- Una clave de Gemini sólo para `learn` asistido por LLM

```bash
cd ~/tools
git clone https://github.com/FelipeFariasAlfaro/glia.git
cd glia
python -m venv .venv
.venv/bin/pip install -e .
.venv/bin/glia --help
```

## Inicio rápido

Ejecuta estos comandos dentro del proyecto que quieres que GLIA recuerde.

```bash
# Inicializar la memoria durable local
python -m glia init

# Escanear archivos fuente y documentación compatibles
python -m glia scan

# Recall estable y de solo lectura
python -m glia recall "autenticación sesión token"

# Adaptación acotada explícita
python -m glia recall "autenticación sesión token" --adapt

# Exploración explícita de asociaciones holográficas
python -m glia recall "autenticación sesión token" --explore

# Inspeccionar almacenamiento durable
python -m glia doctor --deep
```

`recall` es de solo lectura por defecto. Usa `--adapt` sólo cuando quieras persistir refuerzo. Usa `--explore` sólo cuando necesites descubrir asociaciones; el ranking estable no mezcla evidencia de unbinding en sus resultados principales.

Para enseñar conocimiento destilado con un LLM, configura estas variables opcionales en el proyecto destino:

```text
GEMINI_API_KEY=tu_clave_aqui
GLIA_MODEL=gemini-3.1-flash-lite-preview
```

```bash
python -m glia learn "La expiración del token de sesión se expresa en segundos, no en milisegundos."
```

## CLI y MCP

Comandos CLI útiles:

| Comando | Propósito |
|---|---|
| `python -m glia init` | Crear almacenamiento `.glia` local al proyecto |
| `python -m glia scan` | Escanear el proyecto incrementalmente |
| `python -m glia recall "consulta"` | Recuperar resultados de resonancia estables |
| `python -m glia recall "consulta" --adapt` | Persistir refuerzo acotado |
| `python -m glia recall "consulta" --explore` | Incluir exploración de asociaciones holográficas |
| `python -m glia learn "texto"` | Destilar y almacenar conocimiento nuevo |
| `python -m glia forget` | Aplicar decaimiento temporal |
| `python -m glia stats` | Informar estadísticas de memoria |
| `python -m glia doctor --deep` | Ejecutar verificaciones de integridad SQLite |
| `python -m glia backup` | Crear un backup SQLite durable |

GLIA también expone un servidor MCP. Configura el cliente para ejecutar `python -m glia.mcp_server` y define `GLIA_WORKSPACE` con el proyecto destino. Reinicia o reconecta el servidor MCP después de actualizar GLIA para que su proceso cargue la implementación nueva.

## Extracción compatible

El escáner extrae estructura útil de Python, JavaScript, TypeScript, Java, Go, Rust, C#, C/C++, Ruby, PHP, Kotlin, Swift, Gherkin, Markdown, texto y archivos de configuración frecuentes. Usa identidades calificadas por fuente, por lo que archivos con el mismo nombre base no colisionan.

## Benchmarks

El benchmark reproducible de fase 2 compara GLIA con recuperación HDM directa, Okapi BM25 y SQLite FTS5 sobre juicios de relevancia versionados. También mide persistencia y escalado de consultas de forma local.

Ejecútalo así:

```bash
.venv/bin/python benchmarks/benchmark_phase2.py --sizes 100 1000 5000 --query-count 10
```

Resultados locales finales de fase 3 con 5.000 glyphs:

| Métrica | Resultado |
|---|---:|
| Guardado inicial completo | 180,08 ms |
| Guardado incremental validado de un glyph | 26,26 ms |
| Filas cambiadas en ese guardado incremental | 1 región y 1 glyph |
| Consulta fría, incluida la construcción de matriz | 32,13 ms |
| Consulta caliente con caché | 6,10 ms |
| Recall público estable | 7,10 ms |
| Recall adaptativo | 65,13 ms |
| Tamaño SQLite, WAL y SHM | 86.047 KiB |

El MRR de recuperación en el mismo benchmark fue 0,837 para el fixture backend, 0,802 para ML y 0,776 para TypeScript/React. BM25 y FTS5 siguen siendo baselines léxicos más fuertes y rápidos para recuperación por términos exactos; el valor diferencial de GLIA es la resonancia HDM persistente, el binding reversible, la plasticidad acotada, el escaneo con procedencia y la exploración de asociaciones.

Los tiempos dependen del hardware y del estado del proceso. La calidad se mide con juicios de relevancia versionados, no se infiere durante cada ejecución.

## Notas operativas

- Agrega `.glia/` al `.gitignore` del proyecto destino, salvo que quieras compartir intencionalmente la base de memoria.
- No edites archivos SQLite mientras un servidor MCP o comando CLI está escribiendo. GLIA reintenta locks transitorios, pero deben evitarse transacciones externas largas.
- Usa `glia doctor --deep` para diagnosticar preocupaciones de persistencia.
- Usa `glia backup` antes de mover, inspeccionar manualmente o recuperar memoria del proyecto.
- Si un servidor MCP sigue ejecutando código antiguo después de una actualización, reconéctalo desde el cliente MCP.

## Licencia

GLIA se distribuye bajo la [Licencia MIT](LICENSE).
