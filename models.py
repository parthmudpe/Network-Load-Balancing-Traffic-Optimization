from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass(frozen=True)
class RequestTemplate:
    """Algorithm-independent request data used to replay identical workloads."""

    request_id: int
    arrival_tick: int
    service_units: int


@dataclass
class Request:
    request_id: int
    arrival_tick: int
    service_units: int
    assigned_tick: Optional[int] = None
    start_tick: Optional[int] = None
    completion_tick: Optional[int] = None
    server_id: Optional[str] = None
    dropped: bool = False

    @property
    def queue_wait(self) -> int:
        if self.start_tick is None:
            return 0
        return max(0, self.start_tick - self.arrival_tick)

    @property
    def system_time(self) -> int:
        if self.completion_tick is None:
            return 0
        return max(0, self.completion_tick - self.arrival_tick)


@dataclass
class ActiveRequest:
    request: Request
    remaining_units: int


@dataclass
class ServerConfig:
    server_id: str
    name: str
    processing_capacity: int
    queue_capacity: int
    base_latency_ms: float
    initial_load: float = 0.0
    available: bool = True
    algorithm_weight: int = 1

    def clone(self) -> "ServerConfig":
        return ServerConfig(
            server_id=self.server_id,
            name=self.name,
            processing_capacity=self.processing_capacity,
            queue_capacity=self.queue_capacity,
            base_latency_ms=self.base_latency_ms,
            initial_load=self.initial_load,
            available=self.available,
            algorithm_weight=self.algorithm_weight,
        )


@dataclass
class ServerState:
    config: ServerConfig
    queue: List[Request] = field(default_factory=list)
    active: List[ActiveRequest] = field(default_factory=list)
    completed_count: int = 0
    dropped_count: int = 0
    busy_ticks: int = 0
    total_queue_samples: int = 0
    queue_sample_count: int = 0

    def reset(self) -> None:
        self.queue.clear()
        self.active.clear()
        self.completed_count = 0
        self.dropped_count = 0
        self.busy_ticks = 0
        self.total_queue_samples = 0
        self.queue_sample_count = 0

    @property
    def active_count(self) -> int:
        return len(self.active)

    @property
    def queue_length(self) -> int:
        return len(self.queue)

    @property
    def utilization(self) -> float:
        if self.config.processing_capacity <= 0:
            return 0.0
        return min(1.0, self.active_count / self.config.processing_capacity)

    @property
    def queue_utilization(self) -> float:
        if self.config.queue_capacity <= 0:
            return 1.0 if self.queue else 0.0
        return min(1.0, self.queue_length / self.config.queue_capacity)

    @property
    def load_ratio(self) -> float:
        """Composite current load used by the dynamic selector."""
        capacity_component = self.active_count / max(1, self.config.processing_capacity)
        queue_component = self.queue_length / max(1, self.config.queue_capacity)
        current_component = 0.7 * capacity_component + 0.3 * queue_component
        return min(1.0, max(self.config.initial_load, current_component))


@dataclass(frozen=True)
class FailureEvent:
    tick: int
    server_id: str
    available: bool


@dataclass
class SimulationConfig:
    duration_ticks: int = 120
    traffic_mode: str = "normal"
    traffic_rate: float = 4.0
    burst_probability: float = 0.06
    burst_multiplier: float = 4.0
    service_units_min: int = 1
    service_units_max: int = 4
    random_seed: int = 42
    failure_events: List[FailureEvent] = field(default_factory=list)


@dataclass
class ServerSnapshot:
    tick: int
    server_id: str
    available: bool
    active: int
    queue: int
    utilization: float
    load_ratio: float


@dataclass
class SimulationResult:
    algorithm: str
    duration_ticks: int
    requests_generated: int
    requests_completed: int
    requests_dropped: int
    average_response_time_ms: float
    p95_response_time_ms: float
    throughput_rps: float
    average_utilization: float
    average_queue_length: float
    load_distribution: Dict[str, int]
    dropped_by_server: Dict[str, int]
    timeline: List[ServerSnapshot] = field(default_factory=list)
    completed_requests: List[Request] = field(default_factory=list)

    @property
    def drop_rate(self) -> float:
        if self.requests_generated == 0:
            return 0.0
        return self.requests_dropped / self.requests_generated

    @property
    def utilization_percent(self) -> float:
        return self.average_utilization * 100.0

    @property
    def total_handled(self) -> int:
        return self.requests_completed + self.requests_dropped
