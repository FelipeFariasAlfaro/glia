"""
GLIA AST Scanner v2 - Extracts code structure into the holographic substrate.
Supports: Python, JS/TS, Java, Go, Rust, C#, C/C++, Ruby, PHP, Kotlin, Swift, Gherkin, Markdown.
"""

from __future__ import annotations

import ast
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
        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return {"glyphs": 0, "relationships": 0}

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
        return scanners.get(ext, self._scan_generic)(content, substrate, source)

    def _store(self, substrate, name, content, source, context=""):
        """Store a glyph. Uses embeddings if available, otherwise local encoding."""
        encode_input = f"{name} {content} {Path(source).stem}"

        # Try enhanced embeddings first
        vector = None
        if self.embedder and self.embedder.is_available:
            vector = self.embedder.embed(encode_input)

        # Fallback to local encoding (free)
        if vector is None:
            vector = encode_text(encode_input)

        glyph_id = f"{context}_{name}" if context else name
        substrate.store_glyph(glyph_id=glyph_id, vector=vector, content=content[:200], source=source)

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

    def _relate(self, substrate, src, tgt, rel_type):
        rel_vector = encode_relationship(src, tgt, rel_type)
        substrate.store_relationship(rel_vector)

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
                    self._relate(substrate, module, alias.name.split(".")[0], "imports")
                    stats["relationships"] += 1
            elif isinstance(node, ast.ImportFrom) and node.module:
                self._relate(substrate, module, node.module.split(".")[0], "imports")
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
        self._store(substrate, module, f"Module {source}", source, "module")
        stats["glyphs"] += 1
        for match in re.finditer(r'(?:export\s+)?(?:async\s+)?function\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Function '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(', content):
            self._store(substrate, match.group(1), f"Function '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'(?:export\s+)?class\s+(\w+)', content):
            self._store(substrate, match.group(1), f"Class '{match.group(1)}' in {source}", source, module)
            stats["glyphs"] += 1
        for match in re.finditer(r'(?:import|require)\s*\(?["\']([^"\']+)["\']', content):
            self._relate(substrate, module, Path(match.group(1)).stem.replace("-", "_"), "imports")
            stats["relationships"] += 1
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
