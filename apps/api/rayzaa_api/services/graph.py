from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import networkx as nx


@dataclass(slots=True)
class GraphPressure:
    score: float
    ring_pressure: float
    shared_device_pressure: float
    merchant_pressure: float
    neighbor_pressure: float


class TrustMemoryGraph:
    def __init__(self) -> None:
        self.graph = nx.MultiDiGraph()
        self.account_risk: dict[str, float] = {}
        self.edge_horizon_hours = 72.0
        self.decay_half_life_hours = 24.0

    @staticmethod
    def _node_id(kind: str, value: str) -> str:
        return f"{kind}:{value}"

    def _ensure_node(self, kind: str, value: str, label: str | None = None) -> str:
        node_id = self._node_id(kind, value)
        if node_id not in self.graph:
            self.graph.add_node(node_id, kind=kind, value=value, label=label or value)
        return node_id

    def _recency_weight(self, current_ts: datetime, edge_ts: datetime) -> float:
        age_hours = max((current_ts - edge_ts).total_seconds() / 3600.0, 0.0)
        return math.exp(-age_hours / self.decay_half_life_hours)

    @staticmethod
    def _edge_timestamp(attrs: dict[str, Any]) -> datetime:
        return datetime.fromisoformat(attrs["timestamp"])

    def _recent_transfer_graph(self, current_ts: datetime) -> nx.DiGraph:
        recent_graph = nx.DiGraph()
        for source, target, attrs in self.graph.edges(data=True):
            if attrs.get("kind") != "transfer":
                continue
            edge_ts = self._edge_timestamp(attrs)
            age_hours = max((current_ts - edge_ts).total_seconds() / 3600.0, 0.0)
            if age_hours > self.edge_horizon_hours:
                continue
            weight = self._recency_weight(current_ts, edge_ts)
            previous = recent_graph.get_edge_data(source, target, default={}).get("weight", 0.0)
            recent_graph.add_edge(source, target, weight=max(weight, previous))
        return recent_graph

    def ingest(self, event: dict[str, Any]) -> GraphPressure:
        account = self._ensure_node("account", event["account_id"], event["account_id"])
        counterparty = self._ensure_node("account", event["counterparty_id"], event["counterparty_id"])
        device = self._ensure_node("device", event["device_id"], event["device_id"])
        merchant = self._ensure_node("merchant", event["merchant_id"], event["merchant_id"])
        city = self._ensure_node("geo", event["city"], event["city"])
        ts = event["timestamp"]

        self.graph.add_edge(account, counterparty, kind="transfer", timestamp=ts.isoformat(), amount=event["amount"])
        self.graph.add_edge(account, device, kind="device", timestamp=ts.isoformat())
        self.graph.add_edge(account, merchant, kind="merchant", timestamp=ts.isoformat())
        self.graph.add_edge(account, city, kind="geo", timestamp=ts.isoformat())

        shared_accounts: dict[str, float] = {}
        for source, _, attrs in self.graph.in_edges(device, data=True):
            if attrs.get("kind") != "device":
                continue
            shared_accounts[source] = max(
                shared_accounts.get(source, 0.0),
                self._recency_weight(ts, self._edge_timestamp(attrs)),
            )

        merchant_accounts: dict[str, float] = {}
        for source, _, attrs in self.graph.in_edges(merchant, data=True):
            if attrs.get("kind") != "merchant":
                continue
            merchant_accounts[source] = max(
                merchant_accounts.get(source, 0.0),
                self._recency_weight(ts, self._edge_timestamp(attrs)),
            )

        ring_pressure = 0.0
        recent_graph = self._recent_transfer_graph(ts)
        try:
            if nx.has_path(recent_graph, counterparty, account):
                path = nx.shortest_path(recent_graph, counterparty, account)
                path_weights = []
                for source, target in zip(path[:-1], path[1:]):
                    path_weights.append(float(recent_graph[source][target]["weight"]))
                ring_pressure = 78.0 * min(path_weights or [0.0])
        except nx.NodeNotFound:
            ring_pressure = 0.0

        risky_neighbors = 0.0
        total_neighbor_weight = 0.0
        for _, neighbor, attrs in self.graph.out_edges(account, data=True):
            if attrs.get("kind") != "transfer":
                continue
            weight = self._recency_weight(ts, self._edge_timestamp(attrs))
            total_neighbor_weight += weight
            neighbor_id = neighbor.split(":", 1)[1]
            neighbor_risk = self.account_risk.get(neighbor_id, 0.0)
            risky_neighbors += weight * min(neighbor_risk / 100.0, 1.0)
        neighbor_pressure = (risky_neighbors / total_neighbor_weight) * 100.0 if total_neighbor_weight else 0.0

        shared_device_pressure = max(0.0, (sum(shared_accounts.values()) - 1.0) * 22.0)
        merchant_pressure = max(0.0, (sum(merchant_accounts.values()) - 1.0) * 16.0)
        score = min(
            100.0,
            ring_pressure * 0.45
            + shared_device_pressure * 0.30
            + merchant_pressure * 0.15
            + neighbor_pressure * 0.25,
        )

        return GraphPressure(
            score=min(100.0, score),
            ring_pressure=min(100.0, ring_pressure),
            shared_device_pressure=min(100.0, shared_device_pressure),
            merchant_pressure=min(100.0, merchant_pressure),
            neighbor_pressure=min(100.0, neighbor_pressure),
        )

    def mark_account(self, account_id: str, fused_score: float) -> None:
        self.account_risk[account_id] = fused_score

    def snapshot(self, focus_account_id: str, radius: int = 2, max_nodes: int = 18) -> dict[str, Any]:
        focus = self._node_id("account", focus_account_id)
        if focus not in self.graph:
            return {"nodes": [], "edges": []}

        lengths = nx.single_source_shortest_path_length(self.graph.to_undirected(), focus, cutoff=radius)
        ordered_node_ids = sorted(lengths.keys(), key=lambda node_id: (lengths[node_id], node_id))
        node_ids = ordered_node_ids[:max_nodes]
        subgraph = self.graph.subgraph(node_ids)

        nodes = []
        edges = []
        for node_id, attrs in subgraph.nodes(data=True):
            risk = self.account_risk.get(attrs.get("value", ""), 0.0) if attrs.get("kind") == "account" else 0.0
            nodes.append(
                {
                    "data": {
                        "id": node_id,
                        "label": attrs.get("label", attrs.get("value", node_id)),
                        "kind": attrs.get("kind"),
                        "risk": risk,
                        "focus": node_id == focus,
                    }
                }
            )
        for source, target, key, attrs in subgraph.edges(keys=True, data=True):
            edges.append(
                {
                    "data": {
                        "id": f"{source}-{target}-{key}",
                        "source": source,
                        "target": target,
                        "kind": attrs.get("kind", "link"),
                        "amount": attrs.get("amount", 0.0),
                    }
                }
            )

        return {"nodes": nodes, "edges": edges}
