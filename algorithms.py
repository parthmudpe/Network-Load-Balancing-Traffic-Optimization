from __future__ import annotations

import random
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, List, Optional

from models import ServerState


@dataclass(frozen=True)
class DynamicWeights:
    load: float = 0.30
    queue: float = 0.20
    response: float = 0.20
    capacity: float = 0.15
    availability: float = 0.15

    def normalized(self) -> "DynamicWeights":
        total = self.load + self.queue + self.response + self.capacity + self.availability
        if total <= 0:
            return DynamicWeights(0.2, 0.2, 0.2, 0.2, 0.2)
        return DynamicWeights(
            self.load / total,
            self.queue / total,
            self.response / total,
            self.capacity / total,
            self.availability / total,
        )


class LoadBalancer(ABC):
    name = "Base"

    def __init__(self, seed: int = 42, weights: Optional[DynamicWeights] = None):
        self.seed = seed
        self.rng = random.Random(seed)
        self.weights = (weights or DynamicWeights()).normalized()

    @abstractmethod
    def select_server(self, servers: Dict[str, ServerState], request_id: int) -> Optional[ServerState]:
        raise NotImplementedError

    def reset(self) -> None:
        pass

    @staticmethod
    def available_servers(servers: Dict[str, ServerState]) -> List[ServerState]:
        return [server for server in servers.values() if server.config.available]


class RoundRobinBalancer(LoadBalancer):
    name = "Round Robin"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pointer = 0

    def reset(self) -> None:
        self.pointer = 0

    def select_server(self, servers: Dict[str, ServerState], request_id: int) -> Optional[ServerState]:
        candidates = self.available_servers(servers)
        if not candidates:
            return None
        candidates.sort(key=lambda server: server.config.server_id)
        selected = candidates[self.pointer % len(candidates)]
        self.pointer += 1
        return selected


class WeightedRoundRobinBalancer(LoadBalancer):
    name = "Weighted Round Robin"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.current: Dict[str, int] = {}

    def reset(self) -> None:
        self.current.clear()

    def select_server(self, servers: Dict[str, ServerState], request_id: int) -> Optional[ServerState]:
        candidates = self.available_servers(servers)
        if not candidates:
            return None
        for server in candidates:
            self.current.setdefault(server.config.server_id, 0)
        total = sum(max(1, server.config.algorithm_weight) for server in candidates)
        index = (request_id - 1) % total
        cumulative = 0
        for server in sorted(candidates, key=lambda s: s.config.server_id):
            cumulative += max(1, server.config.algorithm_weight)
            if index < cumulative:
                return server
        return candidates[-1]


class LeastConnectionsBalancer(LoadBalancer):
    name = "Least Connections"

    def select_server(self, servers: Dict[str, ServerState], request_id: int) -> Optional[ServerState]:
        candidates = self.available_servers(servers)
        if not candidates:
            return None
        return min(
            candidates,
            key=lambda server: (
                server.active_count + server.queue_length,
                server.load_ratio,
                server.config.base_latency_ms,
                server.config.server_id,
            ),
        )


class RandomBalancer(LoadBalancer):
    name = "Random Selection"

    def select_server(self, servers: Dict[str, ServerState], request_id: int) -> Optional[ServerState]:
        candidates = self.available_servers(servers)
        if not candidates:
            return None
        candidates.sort(key=lambda server: server.config.server_id)
        return self.rng.choice(candidates)


class MultiFactorDynamicBalancer(LoadBalancer):
    name = "Multi-Factor Dynamic Scoring"

    def _score(self, server: ServerState, max_capacity: float, max_latency: float) -> float:
        if not server.config.available:
            return float("-inf")

        load_score = 1.0 - server.load_ratio
        queue_score = 1.0 - server.queue_utilization
        response_score = 1.0 - min(1.0, server.config.base_latency_ms / max(1.0, max_latency))
        capacity_score = server.config.processing_capacity / max(1.0, max_capacity)
        availability_score = 1.0 if server.config.available else 0.0

        w = self.weights
        return (
            w.load * load_score
            + w.queue * queue_score
            + w.response * response_score
            + w.capacity * capacity_score
            + w.availability * availability_score
        )

    def select_server(self, servers: Dict[str, ServerState], request_id: int) -> Optional[ServerState]:
        candidates = self.available_servers(servers)
        if not candidates:
            return None

        max_capacity = max(server.config.processing_capacity for server in candidates)
        max_latency = max(server.config.base_latency_ms for server in candidates)
        ranked = sorted(
            candidates,
            key=lambda server: (
                self._score(server, max_capacity, max_latency),
                -server.queue_length,
                -server.config.processing_capacity,
                server.config.server_id,
            ),
            reverse=True,
        )
        return ranked[0]


ALGORITHM_CLASSES = {
    "Round Robin": RoundRobinBalancer,
    "Weighted Round Robin": WeightedRoundRobinBalancer,
    "Least Connections": LeastConnectionsBalancer,
    "Random Selection": RandomBalancer,
    "Multi-Factor Dynamic Scoring": MultiFactorDynamicBalancer,
}


def build_balancer(name: str, seed: int = 42, weights: Optional[DynamicWeights] = None) -> LoadBalancer:
    cls = ALGORITHM_CLASSES[name]
    return cls(seed=seed, weights=weights)
