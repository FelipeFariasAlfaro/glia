# GLIA Hackathon Pitch — Flujo Completo

## El problema (10 segundos)

Los agentes de IA revisan código sin contexto. No saben que hace 2 meses hubo un incidente por usar `JSON.stringify` en logs de pagos. Aprueban código que repite errores del pasado.

## La solución (20 segundos)

GLIA es un agente autónomo que actúa como Tech Lead digital. Tiene memoria holográfica del proyecto — recuerda incidentes, decisiones y convenciones. Revisa cada Merge Request con ese contexto y aprende de cada merge aprobado.

---

## Cómo funciona (el flujo completo)

### 1. Cómo se enseña (la memoria)

```
Developer o Tech Lead
        │
        │  "Nunca usar JSON.stringify en payment logs.
        │   Incidente #402: causó CPU spike."
        │
        ▼
   POST /learn
        │
        ▼
┌─────────────────────────────────┐
│  GLIA Engine (Cloud Run)        │
│                                  │
│  1. Gemini Flash destila el     │
│     texto en conceptos          │
│  2. Codifica como glyphs        │
│     (vectores 1024-d)           │
│  3. Almacena en memory.db       │
│     (SQLite en el container)    │
└─────────────────────────────────┘
```

También aprende automáticamente del código cuando se hace merge (paso 4 abajo).

---

### 2. Cómo vive en Google Cloud

```
┌─────────────────────────────────────────────────────────┐
│                  Google Cloud Run                         │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  FastAPI Container                                  │ │
│  │                                                     │ │
│  │  Endpoints:                                         │ │
│  │    POST /webhook/gitlab  ← GitLab envía eventos    │ │
│  │    POST /learn           ← Enseñar manualmente     │ │
│  │    GET  /recall?q=...    ← Consultar memoria       │ │
│  │    POST /sync-memory     ← Subir memory.db local   │ │
│  │                                                     │ │
│  │  Internos:                                          │ │
│  │    • GLIA Engine (substrate, resonance, plasticity) │ │
│  │    • Gemini 3.1 Flash Lite (razonamiento)          │ │
│  │    • memory.db (SQLite, persistido en el container) │ │
│  └────────────────────────────────────────────────────┘ │
│                                                          │
│  Configuración:                                          │
│    GEMINI_API_KEY (env var)                              │
│    GITLAB_PERSONAL_ACCESS_TOKEN (env var)                │
│    GLIA_MODEL=gemini-3.1-flash-lite-preview             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

Un solo container. Sin bases de datos externas. Sin infraestructura compleja. Deploy con un comando `gcloud run deploy`.

---

### 3. Cómo trabaja el agente (la review)

Cuando llega un webhook de MR abierto:

```
┌──────────────┐     webhook      ┌──────────────────────┐
│   GitLab     │ ──────────────▶  │  GLIA (Cloud Run)    │
│              │                   │                      │
│  MR abierto  │                   │  1. Recibe el diff   │
│  con diff    │                   │                      │
└──────────────┘                   │  2. glia_recall()    │
                                   │     "¿Qué sé sobre   │
                                   │      estos archivos?" │
                                   │                      │
                                   │  3. Gemini analiza:  │
                                   │     diff + contexto  │
                                   │     de memoria       │
                                   │                      │
                                   │  4. Genera review    │
                                   │     con fundamento   │
                                   │     histórico        │
                                   └──────────┬───────────┘
                                              │
                                    POST comment via
                                    GitLab API
                                              │
                                              ▼
                                   ┌──────────────────┐
                                   │  GitLab MR       │
                                   │                  │
                                   │  💬 GLIA Review: │
                                   │  "Este código usa│
                                   │  JSON.stringify  │
                                   │  en payment logs.│
                                   │  Incidente #402  │
                                   │  demostró que    │
                                   │  causa CPU spike.│
                                   │  Usar Custom     │
                                   │  Logger.serialize│
                                   │  en su lugar."   │
                                   └──────────────────┘
```

---

### 4. Cómo aprende del merge (el loop cerrado)

Cuando el MR se aprueba y se mergea:

```
┌──────────────┐     webhook      ┌──────────────────────┐
│   GitLab     │ ──────────────▶  │  GLIA (Cloud Run)    │
│              │  (merge event)    │                      │
│  MR mergeado │                   │  1. Detecta que es   │
│              │                   │     un merge event   │
└──────────────┘                   │                      │
                                   │  2. Obtiene el diff  │
                                   │     final aprobado   │
                                   │                      │
                                   │  3. glia_learn()     │
                                   │     "Este código fue │
                                   │      aprobado por el │
                                   │      equipo"         │
                                   │                      │
                                   │  4. Nuevos glyphs    │
                                   │     se superponen    │
                                   │     en el substrate  │
                                   │                      │
                                   │  ✅ Memoria crece    │
                                   │     automáticamente  │
                                   └──────────────────────┘
```

---

### 5. Comunicación con GitLab (resumen)

```
GitLab ──webhook──▶ GLIA          (GitLab notifica eventos)
GLIA ──API call──▶ GitLab         (GLIA posta comentarios)

Eventos que GLIA escucha:
  • merge_request (opened)  → Trigger review
  • merge_request (merged)  → Trigger learn

Acciones que GLIA ejecuta:
  • POST /projects/:id/merge_requests/:iid/notes
    (Posta el comentario de review en el MR)
```

No hay polling. No hay cron jobs. Es event-driven: GitLab empuja, GLIA reacciona.

---

## El pitch en 60 segundos

> "GLIA es un Tech Lead digital que vive en Cloud Run. Tiene memoria holográfica del proyecto — no un grafo, no RAG, sino patrones distribuidos que resuenan por asociación. Cuando alguien abre un Merge Request, GitLab le avisa. GLIA consulta su memoria, encuentra incidentes y decisiones relacionadas, y Gemini genera una review con fundamento histórico. Cuando el MR se mergea, GLIA aprende automáticamente el código aprobado. El loop se cierra solo. La memoria crece con cada merge y se limpia sola con el tiempo. Cero configuración después del deploy. Un comando de gcloud y listo."

---

## Demo script (2 minutos)

1. **Mostrar la memoria vacía** → `curl /recall?q=payment` → "No patterns found"
2. **Enseñar una regla** → `curl -X POST /learn` con el incidente de JSON.stringify
3. **Verificar que aprendió** → `curl /recall?q=payment+logging` → Muestra el incidente
4. **Abrir un MR con código malo** → Push con `JSON.stringify(payload)` en payment logs
5. **GLIA comenta automáticamente** → Mostrar el comentario en GitLab citando el incidente
6. **Corregir y mergear** → GLIA aprende el patrón correcto
7. **Verificar que creció** → `curl /recall?q=payment+logging` → Ahora muestra AMBOS: el incidente Y el fix aprobado
