from __future__ import annotations

from typing import Dict, Optional

from algorithms import DynamicWeights, LoadBalancer, build_balancer
from models import RequestTemplate, ServerState


class Router:
    """Routing facade used by the simulation engine and GUI."""

    def __init__(self, algorithm_name: str, seed: int = 42, weights: Optional[DynamicWeights] = None):
        self.algorithm_name = algorithm_name
        self.balancer: LoadBalancer = build_balancer(algorithm_name, seed=seed, weights=weights)

    def route(self, servers: Dict[str, ServerState], request: RequestTemplate) -> Optional[ServerState]:
        return self.balancer.select_server(servers, request.request_id)

    def reset(self) -> None:
        self.balancer.reset()
