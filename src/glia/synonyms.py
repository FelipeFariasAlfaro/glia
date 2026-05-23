"""
GLIA Synonyms - Static synonym expansion for programming concepts.

Expands queries and content with related terms so that
"authentication" resonates with "login", "auth", "sign in", etc.
without needing AI embeddings.

This is a curated dictionary of programming/software synonyms.
"""

# Each group contains words that should be treated as semantically related.
# When encoding, all synonyms in a group contribute to the same vector components.
SYNONYM_GROUPS = [
    # Auth
    {"auth", "authentication", "login", "signin", "sign_in", "credentials", "authenticate"},
    {"logout", "signout", "sign_out", "session_end"},
    {"token", "jwt", "bearer", "access_token", "refresh_token"},
    {"password", "passwd", "secret", "credential", "hash"},
    {"permission", "authorization", "role", "access", "privilege", "rbac"},

    # Database
    {"database", "db", "datastore", "storage", "persistence", "repository"},
    {"query", "sql", "select", "insert", "update", "delete"},
    {"migration", "schema", "migrate", "alter", "ddl"},
    {"connection", "pool", "conn", "client", "session"},
    {"cache", "redis", "memcached", "caching", "ttl", "invalidate"},
    {"transaction", "commit", "rollback", "atomic"},

    # API / HTTP
    {"api", "endpoint", "route", "handler", "controller"},
    {"request", "req", "http", "fetch", "call"},
    {"response", "res", "reply", "status_code"},
    {"get", "post", "put", "patch", "delete", "crud"},
    {"middleware", "interceptor", "filter", "hook", "pipe"},
    {"webhook", "callback", "notification", "event"},

    # Error handling
    {"error", "exception", "failure", "fault", "crash", "bug"},
    {"retry", "backoff", "resilience", "circuit_breaker", "fallback"},
    {"timeout", "deadline", "expiry", "expiration", "ttl"},
    {"validate", "validation", "check", "verify", "sanitize"},

    # Architecture
    {"service", "module", "component", "layer", "microservice"},
    {"config", "configuration", "settings", "env", "environment"},
    {"deploy", "deployment", "release", "ship", "ci_cd", "pipeline"},
    {"test", "testing", "spec", "unit_test", "integration_test"},
    {"monitor", "monitoring", "observability", "metrics", "alert", "logging"},

    # State / Data flow
    {"state", "store", "redux", "context", "slice"},
    {"event", "emit", "publish", "subscribe", "listener", "bus"},
    {"queue", "worker", "job", "background", "async", "task"},
    {"stream", "websocket", "realtime", "socket", "sse"},

    # Frontend
    {"component", "widget", "element", "view", "page"},
    {"render", "display", "show", "ui", "interface"},
    {"hook", "effect", "lifecycle", "mount", "unmount"},
    {"route", "navigation", "path", "url", "link"},

    # Common actions
    {"create", "add", "new", "insert", "register"},
    {"read", "get", "fetch", "retrieve", "find", "search", "query"},
    {"update", "edit", "modify", "change", "patch"},
    {"delete", "remove", "destroy", "drop", "cancel"},

    # Payment / Business
    {"payment", "pay", "charge", "billing", "invoice", "stripe"},
    {"order", "purchase", "cart", "checkout", "transaction"},
    {"user", "account", "profile", "customer", "member"},
    {"notification", "notify", "alert", "email", "sms", "push"},

    # ML / Data
    {"model", "training", "train", "fit", "predict", "inference"},
    {"feature", "column", "attribute", "field", "variable"},
    {"pipeline", "workflow", "dag", "etl", "transform"},
    {"drift", "degradation", "decay", "shift", "distribution_change"},
]

# Build lookup: word → set of synonyms
_SYNONYM_MAP: dict[str, set[str]] = {}
for group in SYNONYM_GROUPS:
    for word in group:
        _SYNONYM_MAP[word] = group


def expand_synonyms(words: list[str]) -> list[str]:
    """
    Expand a list of words with their synonyms.
    Returns the original words + all synonyms found.
    """
    expanded = set(words)
    for word in words:
        word_lower = word.lower()
        if word_lower in _SYNONYM_MAP:
            expanded.update(_SYNONYM_MAP[word_lower])
    return list(expanded)


def get_synonyms(word: str) -> set[str]:
    """Get all synonyms for a word."""
    return _SYNONYM_MAP.get(word.lower(), {word.lower()})
