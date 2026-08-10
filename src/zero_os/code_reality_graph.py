from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable


@dataclass(frozen=True)
class CodeNode:
    node_id: str
    kind: str
    path: str = ""
    symbol: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class CodeEdge:
    source: str
    target: str
    relation: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class CodeRealityGraph:
    nodes: dict[str, CodeNode] = field(default_factory=dict)
    outgoing: dict[str, list[CodeEdge]] = field(default_factory=dict)

    def add_node(self, node: CodeNode) -> None:
        self.nodes[node.node_id] = node

    def add_edge(self, edge: CodeEdge) -> None:
        self.outgoing.setdefault(edge.source, []).append(edge)

    def reachable(self, starts: Iterable[str], *, allowed_relations: set[str] | None = None) -> set[str]:
        frontier = [item for item in starts if item in self.nodes]
        visited: set[str] = set(frontier)
        while frontier:
            current = frontier.pop()
            for edge in self.outgoing.get(current, []):
                if allowed_relations is not None and edge.relation not in allowed_relations:
                    continue
                if edge.target not in visited:
                    visited.add(edge.target)
                    frontier.append(edge.target)
        return visited

    def paths_to(self, starts: Iterable[str], target: str, *, max_depth: int = 12) -> list[list[str]]:
        if target not in self.nodes:
            return []
        results: list[list[str]] = []
        for start in starts:
            if start not in self.nodes:
                continue
            stack: list[tuple[str, list[str]]] = [(start, [start])]
            while stack:
                current, path = stack.pop()
                if len(path) > max_depth:
                    continue
                if current == target:
                    results.append(path)
                    continue
                for edge in self.outgoing.get(current, []):
                    if edge.target in path:
                        continue
                    stack.append((edge.target, path + [edge.target]))
        return results


def from_records(nodes: Iterable[dict[str, Any]], edges: Iterable[dict[str, Any]]) -> CodeRealityGraph:
    graph = CodeRealityGraph()
    for item in nodes:
        graph.add_node(
            CodeNode(
                node_id=str(item.get("id", "")),
                kind=str(item.get("kind", "unknown")),
                path=str(item.get("path", "")),
                symbol=str(item.get("symbol", "")),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    for item in edges:
        graph.add_edge(
            CodeEdge(
                source=str(item.get("source", "")),
                target=str(item.get("target", "")),
                relation=str(item.get("relation", "calls")),
                metadata=dict(item.get("metadata") or {}),
            )
        )
    return graph
