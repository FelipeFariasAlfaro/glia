"""
GLIA AST Scanner v2 - Extracts code structure into the holographic substrate.
Supports: Python, JS/TS, Java, Go, Rust, C#, C/C++, Ruby, PHP, Kotlin, Swift, Gherkin, Markdown.
"""

from __future__ import annotations

import ast
import copy
import hashlib
import re
from pathlib import Path

from .substrate import Substrate
from .encoder import encode_text, encode_identifier, encode_relationship


class ASTScannerV2:
    def __init__(self, embedder=None):
        """
        Args:
            embedder: Optional GliaEmbedder for enhanced precision.
                      If None, uses local hash-based encoding (free).
        """
        self.embedder = embedder
    def scan_file(self, filepath: Path, substrate: Substrate, relative_path: str = "") -> dict:
        source = relative_path or filepath.name
        raw_content = filepath.read_bytes()
        content = raw_content.decode("utf-8", errors="ignore")
        content_hash = hashlib.sha256(raw_content).hexdigest()

        ext = filepath.suffix.lower()
        scanners = {
            ".py": self._scan_python, ".js": self._scan_js, ".ts": self._scan_js,
            ".jsx": self._scan_js, ".tsx": self._scan_js, ".java": self._scan_java,
            ".go": self._scan_go, ".rs": self._scan_rust, ".cs": self._scan_csharp,
            ".c": self._scan_c, ".cpp": self._scan_c, ".h": self._scan_c,
            ".rb": self._scan_ruby, ".php": self._scan_php, ".kt": self._scan_kotlin,
            ".swift": self._scan_swift, ".feature": self._scan_gherkin,
            ".md": self._scan_markdown, ".txt": self._scan_markdown,
        }
        scanner = scanners.get(ext, self._scan_generic)
        tracking_checkpoint = substrate.tracking_checkpoint()
        previous_region_ids = set(substrate.regions)
        previous_glyphs = {
            glyph_id: copy.deepcopy(glyph)
            for glyph_id, glyph in substrate.glyphs.items()
            if glyph.source == source
        }
        previous_relationships = {
            relationship_id: copy.deepcopy(relationship)
            for relationship_id, relationship in substrate.relationships.items()
            if relationship.source == source
        }
        affected_regions = {"default"}
        affected_regions.update(glyph.region_id for glyph in previous_glyphs.values())
        affected_regions.update(
            relationship.region_id for relationship in previous_relationships.values()
        )
        previous_regions = {
            region_id: copy.deepcopy(substrate.regions.get(region_id))
            for region_id in affected_regions
        }
        try:
            substrate.remove_source(source)
            stats = scanner(content, substrate, source)
            stats["hash"] = content_hash
            return stats
        except Exception:
            substrate.remove_source(source)
            for region_id in set(substrate.regions) - previous_region_ids:
                substrate.regions.pop(region_id, None)
            for region_id, region in previous_regions.items():
                if region is None:
                    substrate.regions.pop(region_id, None)
                else:
                    substrate.regions[region_id] = region
            substrate.glyphs.update(previous_glyphs)
            substrate.relationships.update(previous_relationships)
            substrate.restore_tracking(tracking_checkpoint)
            raise

    @staticmethod
    def _source_namespace(source: str) -> str:
        normalized = source.replace("\\", "/").strip("/")
        stem = re.sub(r"[^a-zA-Z0-9]+", "_", Path(normalized).stem).strip("_") or "file"
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:10]
        return f"{stem}_{digest}"

    def _store(self, substrate, name, content, source, context=""):
        """Store a source-qualified glyph using enhanced or local encoding."""
        encode_input = f"{name} {content} {source}"

        vector = None
        if self.embedder and self.embedder.is_available:
            vector = self.embedder.embed(encode_input)
        if vector is None:
            vector = encode_text(encode_input)

        namespace = self._source_namespace(source)
        local_id = f"{context}:{name}" if context else name
        glyph_id = f"{namespace}:{local_id}"
        substrate.store_glyph(
            glyph_id=glyph_id,
            vector=vector,
            content=content[:200],
            source=source,
        )

    def _extract_comments(self, content: str) -> list[str]:
        """Extract all comments from source code."""
        comments = []
        for line in content.split("\n"):
            line = line.strip()
            if line.startswith("#") or line.startswith("//"):
                comment = line.lstrip("#/").strip()
                if len(comment) > 10:
                    comments.append(comment)
        return comments

    def _relate(self, substrate, src, tgt, rel_type, source):
        rel_vector = encode_relationship(src, tgt, rel_type)
        identity = "|".join((source.replace("\\", "/"), src, tgt, rel_type))
        relationship_id = f"scan:{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]}"
        substrate.store_relationship(
            rel_vector,
            relationship_id=relationship_id,
            source=source,
        )

    def _scan_python(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._scan_generic(content, substrate, source)
        module = Path(source).stem

        # Module-level docstring (full, not just first line)
        module_doc = ""
        if tree.body and isinstance(tree.body[0], ast.Expr) and isinstance(getattr(tree.body[0], 'value', None), ast.Constant):
            val = tree.body[0].value.value
            if isinstance(val, str):
                module_doc = val.strip()[:500]
        self._store(substrate, module, module_doc or f"Module {source}", source, "module")
        stats["glyphs"] += 1

        # Imports as relationships
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self._relate(substrate, module, alias.name.split(".")[0], "imports", source)
                    stats["relationships"] += 1
            elif isinstance(node, ast.ImportFrom) and node.module:
                self._relate(substrate, module, node.module.split(".")[0], "imports", source)
                stats["relationships"] += 1

        # Functions and classes with FULL docstrings
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = self._py_doc_full(node) or f"Function '{node.name}' in {source}"
                self._store(substrate, node.name, doc, source, module)
                stats["glyphs"] += 1
            elif isinstance(node, ast.ClassDef):
                doc = self._py_doc_full(node) or f"Class '{node.name}' in {source}"
                self._store(substrate, node.name, doc, source, module)
                stats["glyphs"] += 1
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name.startswith("_") and item.name != "__init__":
                            continue
                        mdoc = self._py_doc_full(item) or f"Method '{item.name}' of '{node.name}'"
                        self._store(substrate, f"{node.name}.{item.name}", mdoc, source, module)
                        stats["glyphs"] += 1

        # Extract inline comments as additional glyphs (they contain hidden knowledge)
        comments = self._extract_comments(content)
        for i, comment in enumerate(comments[:10]):  # Max 10 comment glyphs per file
            self._store(substrate, f"note_{i}", comment, source, module)
            stats["glyphs"] += 1

        return stats

    def _py_doc_full(self, node):
        """Extract FULL docstring (not just first line)."""
        if node.body and isinstance(node.body[0], ast.Expr) and isinstance(getattr(node.body[0], 'value', None), ast.Constant):
            val = node.body[0].value.value
            if isinstance(val, str):
                return val.strip()[:300]
        return ""

    def _scan_js(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        module_summary = re.sub(r"\s+", " ", content[:500]).strip()
        self._store(
            substrate,
            module,
            module_summary or f"Module {source}",
            source,
            "module",
        )
        stats["glyphs"] += 1

        declarations = [
            re.compile(r"(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s+(\w+)"),
            re.compile(
                r"(?:export\s+)?(?:const|let|var)\s+(\w+)"
                r"(?:\s*:\s*[^=]+)?\s*=\s*(?:async\s*)?"
                r"(?:\([^)]*\)|\w+)\s*=>"
            ),
            re.compile(r"(?:export\s+)?class\s+(\w+)"),
            re.compile(r"(?:export\s+)?(?:interface|type|enum)\s+(\w+)"),
        ]
        seen = set()
        for pattern in declarations:
            for match in pattern.finditer(content):
                name = match.group(1)
                if name in seen:
                    continue
                seen.add(name)
                start = max(0, match.start() - 120)
                snippet = re.sub(
                    r"\s+", " ", content[start:match.start() + 360]
                ).strip()
                self._store(substrate, name, snippet, source, module)
                stats["glyphs"] += 1

        for match in re.finditer(
            r"(?:import\s+.*?\s+from\s+|require\s*\()[\"']([^\"']+)[\"']",
            content,
        ):
            self._relate(
                substrate,
                module,
                Path(match.group(1)).stem.replace("-", "_"),
                "imports",
                source,
            )
            stats["relationships"] += 1

        for index, comment in enumerate(self._extract_comments(content)[:8]):
            self._store(
                substrate,
                f"note_{index}",
                comment,
                source,
                module,
            )
            stats["glyphs"] += 1
        return stats

    def _scan_java(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"Java class {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:public|private|protected)?\s*(?:class|interface|enum)\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Class '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'(?:public|private|protected)\s+(?:static\s+)?[\w<>\[\]]+\s+(\w+)\s*\(', content):
            name = match.group(1)
            if name not in ("if", "for", "while", "switch", "catch"):
                self._store(substrate, name, f"Method '{name}' in {source}", source, module)
                stats["glyphs"] += 1
        return stats

    def _scan_go(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"Go file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'func\s+(?:\(\w+\s+\*?(\w+)\)\s+)?(\w+)\s*\(', content):
            receiver, name = match.group(1), match.group(2)
            label = f"{receiver}.{name}" if receiver else name
            self._store(substrate, label, f"Function '{label}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'type\s+(\w+)\s+(?:struct|interface)', content):
            self._store(substrate, match.group(1), f"Type '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_rust(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"Rust module {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Function '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'(?:pub\s+)?(?:struct|enum|trait)\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Type '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_csharp(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"C# file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:class|interface|record|struct)\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Class '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_c(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"C/C++ file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'[\w:*&<>]+\s+(\w+)\s*\([^)]*\)\s*(?:const\s*)?\{', content):
            name = match.group(1)
            if name not in ("if", "for", "while", "switch", "return", "sizeof"):
                self._store(substrate, name, f"Function '{name}' in {source}", source, module)
                stats["glyphs"] += 1
        return stats

    def _scan_ruby(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"Ruby file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:class|module)\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Class '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'def\s+(?:self\.)?(\w+[?!]?)', content):
            self._store(substrate, match.group(1), f"Method '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_php(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"PHP file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'class\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Class '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'function\s+(\w+)\s*\(', content):
            self._store(substrate, match.group(1), f"Function '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_kotlin(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"Kotlin file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:class|object|interface)\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Class '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'fun\s+(\w+)\s*\(', content):
            self._store(substrate, match.group(1), f"Function '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_swift(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        module = Path(source).stem
        self._store(substrate, module, f"Swift file {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:class|struct|protocol|enum|actor)\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Type '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'func\s+(\w+)\s*\(', content):
            self._store(substrate, match.group(1), f"Function '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        return stats

    def _scan_gherkin(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        feature_name = Path(source).stem
        feature_match = re.search(r'Feature:\s*(.+)$', content, re.MULTILINE)
        if feature_match:
            self._store(substrate, feature_name, f"Feature: {feature_match.group(1).strip()}", source, "feature")
            stats["glyphs"] += 1
        for match in re.finditer(r'Scenario(?:\s+Outline)?:\s*(.+)$', content, re.MULTILINE):
            name = re.sub(r'[^a-z0-9]', '_', match.group(1).strip().lower())[:40]
            self._store(substrate, name, f"Scenario: {match.group(1).strip()}", source, feature_name)
            stats["glyphs"] += 1
        return stats

    def _scan_markdown(self, content, substrate, source):
        stats = {"glyphs": 0, "relationships": 0}
        doc_name = Path(source).stem

        # Store the full document as one glyph with rich content
        # Take first 500 chars as the document summary
        doc_summary = content[:500].replace("\n", " ").strip()
        self._store(substrate, doc_name, doc_summary, source, "doc")
        stats["glyphs"] += 1

        # Also store each section
        for title in re.findall(r'^#{1,3}\s+(.+)$', content, re.MULTILINE)[:20]:
            section_id = re.sub(r'[^a-z0-9]', '_', title.strip().lower())[:40]
            pos = content.find(title)
            # Get content under this header (up to 300 chars)
            section_content = content[pos + len(title):pos + len(title) + 300]
            lines = [l.strip() for l in section_content.split("\n") if l.strip() and not l.strip().startswith("#")]
            intention = " ".join(lines)[:200] if lines else f"Section: {title.strip()}"
            self._store(substrate, section_id, intention, source, doc_name)
            stats["glyphs"] += 1
        return stats

    def _scan_generic(self, content, substrate, source):
        name = Path(source).stem
        intention = next((l.strip().strip("#/.*")[:150] for l in content.split("\n")[:10] if l.strip().strip("#/.*") and len(l.strip()) > 10), f"File: {source}")
        self._store(substrate, name, intention, source, "file")
        return {"glyphs": 1, "relationships": 0}
