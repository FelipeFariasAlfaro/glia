"""
GLIA AST Scanner - Extracts code structure WITHOUT using AI.

Supports: Python, JavaScript, TypeScript, Java, Go, Rust, C#, C/C++,
Ruby, PHP, Kotlin, Swift, Gherkin, Markdown, Config files.

Creates the graph structure for FREE — no tokens, no API keys, instant.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Optional

from .graph import GliaGraph
from .threads import ThreadStore


class ASTScanner:
    """Extracts code structure from source files using AST/regex parsing."""

    def scan_file(
        self,
        filepath: Path,
        graph: GliaGraph,
        store: ThreadStore,
        relative_path: str = "",
    ) -> dict:
        source = relative_path or filepath.name
        stats = {"nodes": 0, "edges": 0}

        try:
            content = filepath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return stats

        ext = filepath.suffix.lower()

        scanners = {
            ".py": self._scan_python,
            ".js": self._scan_javascript,
            ".ts": self._scan_javascript,
            ".jsx": self._scan_javascript,
            ".tsx": self._scan_javascript,
            ".java": self._scan_java,
            ".go": self._scan_go,
            ".rs": self._scan_rust,
            ".cs": self._scan_csharp,
            ".c": self._scan_c_cpp,
            ".cpp": self._scan_c_cpp,
            ".h": self._scan_c_cpp,
            ".hpp": self._scan_c_cpp,
            ".rb": self._scan_ruby,
            ".php": self._scan_php,
            ".kt": self._scan_kotlin,
            ".swift": self._scan_swift,
            ".feature": self._scan_gherkin,
            ".md": self._scan_markdown,
            ".txt": self._scan_markdown,
            ".rst": self._scan_markdown,
            ".json": self._scan_config,
            ".yaml": self._scan_config,
            ".yml": self._scan_config,
            ".toml": self._scan_config,
        }

        scanner_fn = scanners.get(ext, self._scan_generic)
        return scanner_fn(content, graph, store, source)

    # --- Python (full AST) ---

    def _scan_python(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return self._scan_generic(content, graph, store, source)

        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        module_doc = self._extract_module_docstring(tree) or f"Module {source}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=module_doc, source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Imports
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imp_id = f"module_{alias.name.split('.')[0]}"
                    graph.add_node(imp_id)
                    graph.connect(module_id, imp_id, 0.5)
                    stats["edges"] += 1
            elif isinstance(node, ast.ImportFrom) and node.module:
                imp_id = f"module_{node.module.split('.')[0]}"
                graph.add_node(imp_id)
                graph.connect(module_id, imp_id, 0.5)
                stats["edges"] += 1

        # Functions and classes
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_id = self._make_id(module_name, node.name)
                doc = self._extract_docstring(node) or f"Function '{node.name}' in {source}"
                graph.add_node(func_id)
                store.add(thread_id=func_id, content=doc, source=source, node_refs=[func_id])
                graph.connect(func_id, module_id, 0.6)
                stats["nodes"] += 1
                stats["edges"] += 1

            elif isinstance(node, ast.ClassDef):
                class_id = self._make_id(module_name, node.name)
                doc = self._extract_docstring(node) or f"Class '{node.name}' in {source}"
                graph.add_node(class_id)
                store.add(thread_id=class_id, content=doc, source=source, node_refs=[class_id])
                graph.connect(class_id, module_id, 0.7)
                stats["nodes"] += 1
                stats["edges"] += 1

                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name.startswith("_") and item.name != "__init__":
                            continue
                        method_id = self._make_id(module_name, f"{node.name}_{item.name}")
                        method_doc = self._extract_docstring(item) or f"Method '{item.name}' of '{node.name}'"
                        graph.add_node(method_id)
                        store.add(thread_id=method_id, content=method_doc, source=source, node_refs=[method_id])
                        graph.connect(method_id, class_id, 0.85)
                        stats["nodes"] += 1
                        stats["edges"] += 1

        return stats

    # --- JavaScript / TypeScript ---

    def _scan_javascript(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"Module {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Functions: function name(), const name = () =>, export function, async
        patterns = [
            (r'(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)', 'function'),
            (r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\(([^)]*)\)\s*(?:=>|:)', 'arrow'),
            (r'(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\w+\s*=>', 'arrow'),
        ]
        for pattern, kind in patterns:
            for match in re.finditer(pattern, content):
                name = match.group(1)
                func_id = self._make_id(module_name, name)
                doc = self._find_jsdoc_above(content, match.start()) or f"Function '{name}' in {source}"
                graph.add_node(func_id)
                store.add(thread_id=func_id, content=doc, source=source, node_refs=[func_id])
                graph.connect(func_id, module_id, 0.6)
                stats["nodes"] += 1
                stats["edges"] += 1

        # Classes
        for match in re.finditer(r'(?:export\s+)?class\s+(\w+)(?:\s+extends\s+(\w+))?', content):
            name = match.group(1)
            parent = match.group(2)
            class_id = self._make_id(module_name, name)
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=f"Class '{name}' in {source}", source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1
            if parent:
                parent_id = self._make_id(module_name, parent)
                graph.add_node(parent_id)
                graph.connect(class_id, parent_id, 0.8)
                stats["edges"] += 1

        # Imports
        for match in re.finditer(r'(?:import|require)\s*\(?["\']([^"\']+)["\']', content):
            dep = match.group(1)
            dep_id = f"module_{Path(dep).stem.replace('-', '_').replace('@', '')}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        # Interfaces/Types (TypeScript)
        for match in re.finditer(r'(?:export\s+)?(?:interface|type)\s+(\w+)', content):
            name = match.group(1)
            type_id = self._make_id(module_name, name)
            graph.add_node(type_id)
            store.add(thread_id=type_id, content=f"Type/Interface '{name}' in {source}", source=source, node_refs=[type_id])
            graph.connect(type_id, module_id, 0.6)
            stats["nodes"] += 1
            stats["edges"] += 1

        return stats

    # --- Java ---

    def _scan_java(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"Java class {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Package
        pkg_match = re.search(r'package\s+([\w.]+);', content)
        if pkg_match:
            pkg_id = f"package_{pkg_match.group(1).replace('.', '_')}"
            graph.add_node(pkg_id)
            graph.connect(module_id, pkg_id, 0.5)
            stats["edges"] += 1

        # Imports
        for match in re.finditer(r'import\s+([\w.]+);', content):
            imp = match.group(1).split(".")[-1]
            imp_id = f"module_{imp.lower()}"
            graph.add_node(imp_id)
            graph.connect(module_id, imp_id, 0.5)
            stats["edges"] += 1

        # Classes and interfaces
        for match in re.finditer(r'(?:public|private|protected)?\s*(?:abstract\s+)?(?:class|interface|enum)\s+(\w+)(?:\s+extends\s+(\w+))?(?:\s+implements\s+([\w,\s]+))?', content):
            name = match.group(1)
            parent = match.group(2)
            class_id = self._make_id(module_name, name)
            doc = self._find_javadoc_above(content, match.start()) or f"Class '{name}' in {source}"
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=doc, source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.8)
            stats["nodes"] += 1
            stats["edges"] += 1
            if parent:
                parent_id = self._make_id(module_name, parent)
                graph.add_node(parent_id)
                graph.connect(class_id, parent_id, 0.8)
                stats["edges"] += 1

        # Methods
        for match in re.finditer(r'(?:public|private|protected)\s+(?:static\s+)?(?:[\w<>\[\]]+)\s+(\w+)\s*\(([^)]*)\)', content):
            name = match.group(1)
            if name in ("if", "for", "while", "switch", "catch"):
                continue
            method_id = self._make_id(module_name, name)
            doc = self._find_javadoc_above(content, match.start()) or f"Method '{name}' in {source}"
            graph.add_node(method_id)
            store.add(thread_id=method_id, content=doc, source=source, node_refs=[method_id])
            graph.connect(method_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        return stats

    # --- Go ---

    def _scan_go(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)

        # Package
        pkg_match = re.search(r'package\s+(\w+)', content)
        pkg_name = pkg_match.group(1) if pkg_match else module_name
        store.add(thread_id=module_id, content=f"Go package '{pkg_name}' in {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Functions
        for match in re.finditer(r'func\s+(?:\(\w+\s+\*?(\w+)\)\s+)?(\w+)\s*\(([^)]*)\)', content):
            receiver = match.group(1)
            name = match.group(2)
            if receiver:
                func_id = self._make_id(module_name, f"{receiver}_{name}")
                doc = self._find_go_comment_above(content, match.start()) or f"Method '{name}' on '{receiver}' in {source}"
            else:
                func_id = self._make_id(module_name, name)
                doc = self._find_go_comment_above(content, match.start()) or f"Function '{name}' in {source}"
            graph.add_node(func_id)
            store.add(thread_id=func_id, content=doc, source=source, node_refs=[func_id])
            graph.connect(func_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Structs
        for match in re.finditer(r'type\s+(\w+)\s+struct\s*\{', content):
            name = match.group(1)
            struct_id = self._make_id(module_name, name)
            doc = self._find_go_comment_above(content, match.start()) or f"Struct '{name}' in {source}"
            graph.add_node(struct_id)
            store.add(thread_id=struct_id, content=doc, source=source, node_refs=[struct_id])
            graph.connect(struct_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Interfaces
        for match in re.finditer(r'type\s+(\w+)\s+interface\s*\{', content):
            name = match.group(1)
            iface_id = self._make_id(module_name, name)
            graph.add_node(iface_id)
            store.add(thread_id=iface_id, content=f"Interface '{name}' in {source}", source=source, node_refs=[iface_id])
            graph.connect(iface_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Imports
        for match in re.finditer(r'"([\w/.-]+)"', content[:content.find("func ") if "func " in content else 500]):
            dep = match.group(1).split("/")[-1]
            dep_id = f"module_{dep.replace('-', '_')}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- Rust ---

    def _scan_rust(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"Rust module {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Functions
        for match in re.finditer(r'(?:pub\s+)?(?:async\s+)?fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(([^)]*)\)', content):
            name = match.group(1)
            func_id = self._make_id(module_name, name)
            doc = self._find_rust_doc_above(content, match.start()) or f"Function '{name}' in {source}"
            graph.add_node(func_id)
            store.add(thread_id=func_id, content=doc, source=source, node_refs=[func_id])
            graph.connect(func_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Structs and enums
        for match in re.finditer(r'(?:pub\s+)?(?:struct|enum)\s+(\w+)', content):
            name = match.group(1)
            struct_id = self._make_id(module_name, name)
            doc = self._find_rust_doc_above(content, match.start()) or f"Type '{name}' in {source}"
            graph.add_node(struct_id)
            store.add(thread_id=struct_id, content=doc, source=source, node_refs=[struct_id])
            graph.connect(struct_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Traits
        for match in re.finditer(r'(?:pub\s+)?trait\s+(\w+)', content):
            name = match.group(1)
            trait_id = self._make_id(module_name, name)
            graph.add_node(trait_id)
            store.add(thread_id=trait_id, content=f"Trait '{name}' in {source}", source=source, node_refs=[trait_id])
            graph.connect(trait_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # use statements
        for match in re.finditer(r'use\s+([\w:]+)', content):
            dep = match.group(1).split("::")[-1]
            dep_id = f"module_{dep.lower()}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- C# ---

    def _scan_csharp(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"C# file {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Namespace
        ns_match = re.search(r'namespace\s+([\w.]+)', content)
        if ns_match:
            ns_id = f"namespace_{ns_match.group(1).replace('.', '_').lower()}"
            graph.add_node(ns_id)
            graph.connect(module_id, ns_id, 0.5)
            stats["edges"] += 1

        # Classes/interfaces
        for match in re.finditer(r'(?:public|private|internal|protected)?\s*(?:abstract|static|sealed)?\s*(?:class|interface|record|struct)\s+(\w+)(?:\s*:\s*([\w,\s]+))?', content):
            name = match.group(1)
            class_id = self._make_id(module_name, name)
            doc = self._find_xml_doc_above(content, match.start()) or f"Class '{name}' in {source}"
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=doc, source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.8)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Methods
        for match in re.finditer(r'(?:public|private|protected|internal)\s+(?:static\s+)?(?:async\s+)?(?:[\w<>\[\]?]+)\s+(\w+)\s*\(([^)]*)\)', content):
            name = match.group(1)
            if name in ("if", "for", "while", "switch", "catch", "class", "new"):
                continue
            method_id = self._make_id(module_name, name)
            doc = self._find_xml_doc_above(content, match.start()) or f"Method '{name}' in {source}"
            graph.add_node(method_id)
            store.add(thread_id=method_id, content=doc, source=source, node_refs=[method_id])
            graph.connect(method_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # using statements
        for match in re.finditer(r'using\s+([\w.]+);', content):
            dep = match.group(1).split(".")[-1]
            dep_id = f"module_{dep.lower()}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- C/C++ ---

    def _scan_c_cpp(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"C/C++ file {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Functions
        for match in re.finditer(r'(?:[\w:*&<>]+)\s+(\w+)\s*\(([^)]*)\)\s*(?:const\s*)?\{', content):
            name = match.group(1)
            if name in ("if", "for", "while", "switch", "return", "sizeof"):
                continue
            func_id = self._make_id(module_name, name)
            graph.add_node(func_id)
            store.add(thread_id=func_id, content=f"Function '{name}' in {source}", source=source, node_refs=[func_id])
            graph.connect(func_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Classes/structs
        for match in re.finditer(r'(?:class|struct)\s+(\w+)', content):
            name = match.group(1)
            class_id = self._make_id(module_name, name)
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=f"Type '{name}' in {source}", source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # #include
        for match in re.finditer(r'#include\s*[<"]([^>"]+)[>"]', content):
            dep = Path(match.group(1)).stem
            dep_id = f"module_{dep.replace('-', '_').lower()}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- Ruby ---

    def _scan_ruby(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"Ruby file {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Classes and modules
        for match in re.finditer(r'(?:class|module)\s+(\w+)(?:\s*<\s*(\w+))?', content):
            name = match.group(1)
            class_id = self._make_id(module_name, name)
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=f"Class/Module '{name}' in {source}", source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Methods
        for match in re.finditer(r'def\s+(self\.)?(\w+[?!]?)', content):
            name = match.group(2)
            method_id = self._make_id(module_name, name.replace("?", "_q").replace("!", "_bang"))
            graph.add_node(method_id)
            store.add(thread_id=method_id, content=f"Method '{name}' in {source}", source=source, node_refs=[method_id])
            graph.connect(method_id, module_id, 0.6)
            stats["nodes"] += 1
            stats["edges"] += 1

        # require
        for match in re.finditer(r'require[_relative]*\s*["\']([^"\']+)["\']', content):
            dep = Path(match.group(1)).stem
            dep_id = f"module_{dep.replace('-', '_')}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- PHP ---

    def _scan_php(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"PHP file {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Classes
        for match in re.finditer(r'class\s+(\w+)(?:\s+extends\s+(\w+))?', content):
            name = match.group(1)
            class_id = self._make_id(module_name, name)
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=f"Class '{name}' in {source}", source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Functions/methods
        for match in re.finditer(r'(?:public|private|protected|static)?\s*function\s+(\w+)\s*\(', content):
            name = match.group(1)
            func_id = self._make_id(module_name, name)
            graph.add_node(func_id)
            store.add(thread_id=func_id, content=f"Function '{name}' in {source}", source=source, node_refs=[func_id])
            graph.connect(func_id, module_id, 0.6)
            stats["nodes"] += 1
            stats["edges"] += 1

        # use/require
        for match in re.finditer(r'(?:use|require|include)\s+["\']?([^"\';\s]+)', content):
            dep = Path(match.group(1)).stem
            dep_id = f"module_{dep.replace('-', '_').lower()}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- Kotlin ---

    def _scan_kotlin(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"Kotlin file {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Classes/objects/interfaces
        for match in re.finditer(r'(?:data\s+|sealed\s+|abstract\s+)?(?:class|object|interface)\s+(\w+)', content):
            name = match.group(1)
            class_id = self._make_id(module_name, name)
            graph.add_node(class_id)
            store.add(thread_id=class_id, content=f"Class '{name}' in {source}", source=source, node_refs=[class_id])
            graph.connect(class_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Functions
        for match in re.finditer(r'(?:suspend\s+)?fun\s+(?:<[^>]+>\s*)?(\w+)\s*\(', content):
            name = match.group(1)
            func_id = self._make_id(module_name, name)
            graph.add_node(func_id)
            store.add(thread_id=func_id, content=f"Function '{name}' in {source}", source=source, node_refs=[func_id])
            graph.connect(func_id, module_id, 0.6)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Imports
        for match in re.finditer(r'import\s+([\w.]+)', content):
            dep = match.group(1).split(".")[-1]
            dep_id = f"module_{dep.lower()}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- Swift ---

    def _scan_swift(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        module_name = Path(source).stem
        module_id = f"module_{module_name}"
        graph.add_node(module_id)
        store.add(thread_id=module_id, content=f"Swift file {source}", source=source, node_refs=[module_id])
        stats["nodes"] += 1

        # Classes/structs/protocols/enums
        for match in re.finditer(r'(?:class|struct|protocol|enum|actor)\s+(\w+)', content):
            name = match.group(1)
            type_id = self._make_id(module_name, name)
            graph.add_node(type_id)
            store.add(thread_id=type_id, content=f"Type '{name}' in {source}", source=source, node_refs=[type_id])
            graph.connect(type_id, module_id, 0.7)
            stats["nodes"] += 1
            stats["edges"] += 1

        # Functions
        for match in re.finditer(r'func\s+(\w+)\s*\(', content):
            name = match.group(1)
            func_id = self._make_id(module_name, name)
            graph.add_node(func_id)
            store.add(thread_id=func_id, content=f"Function '{name}' in {source}", source=source, node_refs=[func_id])
            graph.connect(func_id, module_id, 0.6)
            stats["nodes"] += 1
            stats["edges"] += 1

        # import
        for match in re.finditer(r'import\s+(\w+)', content):
            dep = match.group(1)
            dep_id = f"module_{dep.lower()}"
            graph.add_node(dep_id)
            graph.connect(module_id, dep_id, 0.5)
            stats["edges"] += 1

        return stats

    # --- Gherkin ---

    def _scan_gherkin(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        feature_name = Path(source).stem.lower().replace(" ", "_")

        feature_match = re.search(r'Feature:\s*(.+)$', content, re.MULTILINE)
        if feature_match:
            feature_id = self._make_id(feature_name, "feature")
            graph.add_node(feature_id)
            store.add(thread_id=feature_id, content=f"BDD Feature: {feature_match.group(1).strip()}", source=source, node_refs=[feature_id])
            stats["nodes"] += 1

        for match in re.finditer(r'Scenario(?:\s+Outline)?:\s*(.+)$', content, re.MULTILINE):
            scenario_id = self._make_id(feature_name, match.group(1).strip()[:40])
            graph.add_node(scenario_id)
            store.add(thread_id=scenario_id, content=f"Scenario: {match.group(1).strip()}", source=source, node_refs=[scenario_id])
            stats["nodes"] += 1
            if feature_match:
                graph.connect(scenario_id, self._make_id(feature_name, "feature"), 0.8)
                stats["edges"] += 1

        return stats

    # --- Markdown ---

    def _scan_markdown(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        doc_name = Path(source).stem.lower().replace(" ", "_")
        prev_id = None

        headers = re.findall(r'^(#{1,3})\s+(.+)$', content, re.MULTILINE)
        for level, title in headers[:20]:
            section_id = self._make_id(doc_name, title.strip()[:40])
            lines = content[content.find(f"{level} {title}"):].split("\n")[1:5]
            intention = ""
            for line in lines:
                line = line.strip()
                if line and not line.startswith("#") and len(line) > 10:
                    intention = line[:150]
                    break
            if not intention:
                intention = f"Section '{title.strip()}' in {source}"

            graph.add_node(section_id)
            store.add(thread_id=section_id, content=intention, source=source, node_refs=[section_id])
            stats["nodes"] += 1
            if prev_id:
                graph.connect(prev_id, section_id, 0.4)
                stats["edges"] += 1
            prev_id = section_id

        return stats

    # --- Config files ---

    def _scan_config(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        config_name = Path(source).stem.lower().replace(".", "_")
        config_id = f"config_{config_name}"
        graph.add_node(config_id)
        store.add(thread_id=config_id, content=f"Configuration: {source}", source=source, node_refs=[config_id])
        stats["nodes"] += 1
        return stats

    # --- Generic fallback ---

    def _scan_generic(self, content, graph, store, source):
        stats = {"nodes": 0, "edges": 0}
        file_id = f"file_{Path(source).stem.lower().replace('-', '_').replace('.', '_')}"
        intention = ""
        for line in content.split("\n")[:10]:
            line = line.strip().strip("#").strip("/").strip("*").strip()
            if line and len(line) > 10:
                intention = line[:150]
                break
        if not intention:
            intention = f"File: {source}"
        graph.add_node(file_id)
        store.add(thread_id=file_id, content=intention, source=source, node_refs=[file_id])
        stats["nodes"] += 1
        return stats

    # --- Helper methods ---

    def _make_id(self, module: str, name: str) -> str:
        clean = re.sub(r'[^a-z0-9_]', '_', name.lower().replace(" ", "_"))
        clean = re.sub(r'_+', '_', clean).strip("_")
        if module and not clean.startswith(module):
            return f"{module}_{clean}"[:60]
        return clean[:60]

    def _extract_docstring(self, node) -> str:
        if (node.body and isinstance(node.body[0], ast.Expr)
                and isinstance(node.body[0].value, ast.Constant)
                and isinstance(node.body[0].value.value, str)):
            return node.body[0].value.value.strip().split("\n")[0][:150]
        return ""

    def _extract_module_docstring(self, tree) -> str:
        if (tree.body and isinstance(tree.body[0], ast.Expr)
                and isinstance(tree.body[0].value, ast.Constant)
                and isinstance(tree.body[0].value.value, str)):
            return tree.body[0].value.value.strip().split("\n")[0][:150]
        return ""

    def _find_jsdoc_above(self, content: str, pos: int) -> str:
        before = content[:pos].rstrip()
        match = re.search(r'/\*\*\s*\n?\s*\*?\s*(.+?)(?:\n|\*/)', before[-300:])
        if match:
            return match.group(1).strip()[:150]
        # Single line comment
        lines = before.split("\n")
        if lines and lines[-1].strip().startswith("//"):
            return lines[-1].strip().lstrip("/").strip()[:150]
        return ""

    def _find_javadoc_above(self, content: str, pos: int) -> str:
        return self._find_jsdoc_above(content, pos)

    def _find_go_comment_above(self, content: str, pos: int) -> str:
        before = content[:pos].rstrip()
        lines = before.split("\n")
        if lines and lines[-1].strip().startswith("//"):
            return lines[-1].strip().lstrip("/").strip()[:150]
        return ""

    def _find_rust_doc_above(self, content: str, pos: int) -> str:
        before = content[:pos].rstrip()
        lines = before.split("\n")
        if lines and lines[-1].strip().startswith("///"):
            return lines[-1].strip().lstrip("/").strip()[:150]
        return ""

    def _find_xml_doc_above(self, content: str, pos: int) -> str:
        before = content[:pos].rstrip()
        match = re.search(r'<summary>\s*(.+?)\s*</summary>', before[-500:])
        if match:
            return match.group(1).strip()[:150]
        return ""
