"""
GLIA Graph Engine - The associative memory core.

A node in GLIA stores NO content. It is a pure pointer whose meaning
emerges from its connections to other nodes. Like a neuron, it only
"knows" who it's connected to and how strongly.

The content (threads/hilos) lives in a separate layer and is only
retrieved AFTER the graph determines what's relevant via spreading activation.
"""

from __future__ import annotations

import json
import time
import math
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


@dataclass
class Edge:
    """A weighted, directed connection between two nodes (a synapse)."""

    target: str
    weight: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_activated: float = field(default_factory=time.time)
    activation_count: int = 0

    def reinforce(self, amount: float = 0.1) -> None:
        """Strengthen this synapse (Hebbian learning: fire together, wire together)."""
        self.weight = min(1.0, self.weight + amount)
        self.last_activated = time.time()
        self.activation_count += 1

    def decay(self, rate: float = 0.01, now: Optional[float] = None) -> None:
        """Weaken this synapse based on time since last activation."""
        now = now or time.time()
        hours_since = (now - self.last_activated) / 3600
        decay_amount = rate * math.log1p(hours_since)
        self.weight = max(0.0, self.weight - decay_amount)


@dataclass
class Node:
    """
    A pure pointer node. Contains NO semantic content.
    Its meaning is defined entirely by its edges to other nodes.
    """

    id: str
    edges: dict[str, Edge] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_activated: float = field(default_factory=time.time)
    activation_count: int = 0

    def connect(self, target_id: str, weight: float = 0.5) -> Edge:
        """Create or reinforce a connection to another node."""
        if target_id in self.edges:
            self.edges[target_id].reinforce()
            return self.edges[target_id]
        edge = Edge(target=target_id, weight=weight)
        self.edges[target_id] = edge
        return edge

    def disconnect(self, target_id: str) -> None:
        """Remove a connection."""
        self.edges.pop(target_id, None)

    def activate(self) -> None:
        """Mark this node as activated (touched during retrieval)."""
        self.last_activated = time.time()
        self.activation_count += 1


class GliaGraph:
    """
    The associative memory graph.

    Implements spreading activation: when a node is activated,
    energy propagates through its connections with decay,
    building a subgraph of "what lit up" — the reconstructed memory.
    """

    def __init__(self) -> None:
        self.nodes: dict[str, Node] = {}

    def add_node(self, node_id: str) -> Node:
        """Create a node if it doesn't exist, return it."""
        if node_id not in self.nodes:
            self.nodes[node_id] = Node(id=node_id)
        return self.nodes[node_id]

    def connect(self, source_id: str, target_id: str, weight: float = 0.5) -> None:
        """Create a bidirectional weighted connection between two nodes."""
        source = self.add_node(source_id)
        self.add_node(target_id)
        source.connect(target_id, weight)
        # Bidirectional but with slightly less weight on the reverse
        self.nodes[target_id].connect(source_id, weight * 0.8)

    def spreading_activation(
        self,
        stimulus: str | list[str],
        energy: float = 1.0,
        decay_factor: float = 0.6,
        min_activation: float = 0.1,
        max_hops: int = 4,
    ) -> dict[str, float]:
        """
        Spreading activation algorithm.

        Starting from one or more stimulus nodes, propagate energy
        through the graph. Each hop multiplies energy by the edge weight
        and the decay factor. Nodes accumulate energy from multiple paths.

        Returns a dict of {node_id: activation_level} for all nodes
        that received energy above the minimum threshold.

        This is how the brain retrieves memories: a small stimulus
        activates a network of associated concepts by propagation.
        """
        if isinstance(stimulus, str):
            stimulus = [stimulus]

        # Activation levels accumulate (multiple paths can energize a node)
        activations: dict[str, float] = {}

        # BFS with energy propagation
        # (node_id, current_energy, current_hop)
        queue: list[tuple[str, float, int]] = []

        for s in stimulus:
            if s in self.nodes:
                queue.append((s, energy, 0))
                self.nodes[s].activate()

        visited_paths: set[tuple[str, str]] = set()

        while queue:
            node_id, current_energy, hop = queue.pop(0)

            if current_energy < min_activation:
                continue
            if hop > max_hops:
                continue

            # Accumulate activation
            activations[node_id] = activations.get(node_id, 0.0) + current_energy

            # Propagate to neighbors
            node = self.nodes[node_id]
            for edge_id, edge in node.edges.items():
                path_key = (node_id, edge_id)
                if path_key in visited_paths:
                    continue
                visited_paths.add(path_key)

                # Energy transmitted = current * edge_weight * decay
                transmitted = current_energy * edge.weight * decay_factor
                if transmitted >= min_activation:
                    # Reinforce the edge (Hebbian: used connections get stronger)
                    edge.reinforce(amount=0.02)
                    queue.append((edge_id, transmitted, hop + 1))

        return activations

    def get_activated_subgraph(
        self,
        stimulus: str | list[str],
        top_k: int = 10,
        **kwargs,
    ) -> list[tuple[str, float]]:
        """
        Get the top-K most activated nodes from a spreading activation.
        Returns sorted list of (node_id, activation_level).
        """
        activations = self.spreading_activation(stimulus, **kwargs)
        sorted_nodes = sorted(activations.items(), key=lambda x: x[1], reverse=True)
        return sorted_nodes[:top_k]

    def decay_all(self, rate: float = 0.01) -> None:
        """Apply temporal decay to all edges in the graph."""
        now = time.time()
        for node in self.nodes.values():
            dead_edges = []
            for edge_id, edge in node.edges.items():
                edge.decay(rate=rate, now=now)
                if edge.weight <= 0.0:
                    dead_edges.append(edge_id)
            # Prune dead synapses
            for dead in dead_edges:
                del node.edges[dead]

    def stats(self) -> dict:
        """Return basic stats about the graph."""
        total_edges = sum(len(n.edges) for n in self.nodes.values())
        return {
            "nodes": len(self.nodes),
            "edges": total_edges,
            "avg_connections": total_edges / max(len(self.nodes), 1),
        }

    # --- Persistence ---

    def save(self, path: Path) -> None:
        """Serialize the graph to JSON."""
        data = {}
        for node_id, node in self.nodes.items():
            data[node_id] = {
                "created_at": node.created_at,
                "last_activated": node.last_activated,
                "activation_count": node.activation_count,
                "edges": {
                    eid: {
                        "weight": e.weight,
                        "created_at": e.created_at,
                        "last_activated": e.last_activated,
                        "activation_count": e.activation_count,
                    }
                    for eid, e in node.edges.items()
                },
            }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "GliaGraph":
        """Deserialize a graph from JSON."""
        graph = cls()
        if not path.exists():
            return graph
        data = json.loads(path.read_text(encoding="utf-8"))
        for node_id, node_data in data.items():
            node = graph.add_node(node_id)
            node.created_at = node_data["created_at"]
            node.last_activated = node_data["last_activated"]
            node.activation_count = node_data["activation_count"]
            for edge_id, edge_data in node_data["edges"].items():
                edge = Edge(
                    target=edge_id,
                    weight=edge_data["weight"],
                    created_at=edge_data["created_at"],
                    last_activated=edge_data["last_activated"],
                    activation_count=edge_data["activation_count"],
                )
                node.edges[edge_id] = edge
        return graph
