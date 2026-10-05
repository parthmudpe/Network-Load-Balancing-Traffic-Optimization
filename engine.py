from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from typing import Dict, Iterable, List, Optional

from algorithms import DynamicWeights, LoadBalancer, build_balancer
from models import (
    ActiveRequest,
    FailureEvent,
    Request,
    RequestTemplate,
    ServerConfig,
    ServerSnapshot,
    ServerState,
    SimulationConfig,
    SimulationResult,
)
from traffic import TrafficGenerator


DEFAULT_SERVERS = [
    ServerConfig("S1", "Server 1", 3, 12, 20.0, algorithm_weight=1),
    ServerConfig("S2", "Server 2", 5, 18, 35.0, algorithm_weight=2),
    ServerConfig("S3", "Server 3", 4, 15, 28.0, algorithm_weight=3),
    ServerConfig("S4", "Server 4", 2, 10, 50.0, algorithm_weight=1),
    ServerConfig("S5", "Server 5", 6, 20, 18.0, algorithm_weight=2),
    ServerConfig("S6", "Server 6", 3, 14, 45.0, algorithm_weight=1),
    ServerConfig("S7", "Server 7", 7, 22, 25.0, algorithm_weight=3),
    ServerConfig("S8", "Server 8", 4, 16, 40.0, algorithm_weight=2),
    ServerConfig("S9", "Server 9", 8, 24, 22.0, algorithm_weight=3),
    ServerConfig("S10", "Server 10", 5, 18, 32.0, algorithm_weight=2),
    ServerConfig("S11", "Server 11", 9, 26, 24.0, algorithm_weight=4),
    ServerConfig("S12", "Server 12", 4, 14, 55.0, algorithm_weight=1),
    ServerConfig("S13", "Server 13", 6, 20, 30.0, algorithm_weight=2),
    ServerConfig("S14", "Server 14", 10, 28, 19.0, algorithm_weight=4),
    ServerConfig("S15", "Server 15", 3, 12, 48.0, algorithm_weight=1),
    ServerConfig("S16", "Server 16", 7, 22, 27.0, algorithm_weight=3),
    ServerConfig("S17", "Server 17", 5, 16, 38.0, algorithm_weight=2),
    ServerConfig("S18", "Server 18", 8, 24, 21.0, algorithm_weight=3),
    ServerConfig("S19", "Server 19", 4, 15, 44.0, algorithm_weight=1),
    ServerConfig("S20", "Server 20", 6, 20, 34.0, algorithm_weight=2),
]


class SimulationEngine:
    """Discrete-event-style simulator for comparing routing strategies fairly."""

    def __init__(
        self,
        server_configs: Optional[Iterable[ServerConfig]] = None,
        simulation_config: Optional[SimulationConfig] = None,
    ):
        self.server_configs = [config.clone() for config in (server_configs or DEFAULT_SERVERS)]
        self.simulation_config = simulation_config or SimulationConfig()

    def generate_workload(self) -> List[RequestTemplate]:
        return TrafficGenerator(self.simulation_config).generate()

    @staticmethod
    def _index_workload(workload: List[RequestTemplate]) -> Dict[int, List[RequestTemplate]]:
        by_tick: Dict[int, List[RequestTemplate]] = defaultdict(list)
        for item in workload:
            by_tick[item.arrival_tick].append(item)
        return by_tick

    def _new_servers(self) -> Dict[str, ServerState]:
        return {config.server_id: ServerState(config.clone()) for config in self.server_configs}

    @staticmethod
    def _failure_events_by_tick(events: Iterable[FailureEvent]) -> Dict[int, List[FailureEvent]]:
        grouped: Dict[int, List[FailureEvent]] = defaultdict(list)
        for event in events:
            grouped[event.tick].append(event)
        return grouped

    def run(
        self,
        algorithm_name: str,
        workload: Optional[List[RequestTemplate]] = None,
        weights: Optional[DynamicWeights] = None,
    ) -> SimulationResult:
        config = self.simulation_config
        workload = workload if workload is not None else self.generate_workload()
        requests_by_tick = self._index_workload(workload)
        failure_events = self._failure_events_by_tick(config.failure_events)
        servers = self._new_servers()
        balancer: LoadBalancer = build_balancer(algorithm_name, config.random_seed, weights)

        completed_requests: List[Request] = []
        dropped_by_server: Dict[str, int] = defaultdict(int)
        load_distribution: Dict[str, int] = defaultdict(int)
        timeline: List[ServerSnapshot] = []
        total_queue_samples = 0
        total_utilization = 0.0

        for tick in range(config.duration_ticks):
            # Apply availability changes first so incoming traffic observes current state.
            for event in failure_events.get(tick, []):
                if event.server_id in servers:
                    servers[event.server_id].config.available = event.available
                    if not event.available:
                        # Requests already being serviced finish, but no new traffic enters.
                        # Queued requests remain queued until the server recovers.
                        pass

            # Complete service on active requests.
            for server in servers.values():
                newly_completed: List[ActiveRequest] = []
                remaining_active: List[ActiveRequest] = []
                for active_request in server.active:
                    active_request.remaining_units -= 1
                    if active_request.remaining_units <= 0:
                        active_request.request.completion_tick = tick + 1
                        newly_completed.append(active_request)
                    else:
                        remaining_active.append(active_request)

                server.active = remaining_active
                server.completed_count += len(newly_completed)
                completed_requests.extend(item.request for item in newly_completed)

                # Fill free processing slots from the waiting queue.
                if server.config.available:
                    free_slots = max(0, server.config.processing_capacity - server.active_count)
                    while free_slots > 0 and server.queue:
                        request = server.queue.pop(0)
                        request.start_tick = tick
                        server.active.append(ActiveRequest(request, request.service_units))
                        free_slots -= 1

            # Generate and route new traffic.
            for template in requests_by_tick.get(tick, []):
                request = Request(
                    request_id=template.request_id,
                    arrival_tick=template.arrival_tick,
                    service_units=template.service_units,
                )
                server = balancer.select_server(servers, request.request_id)
                if server is None:
                    request.dropped = True
                    dropped_by_server["UNASSIGNED"] += 1
                    continue

                request.assigned_tick = tick
                request.server_id = server.config.server_id
                load_distribution[server.config.server_id] += 1

                if server.active_count < server.config.processing_capacity:
                    request.start_tick = tick
                    server.active.append(ActiveRequest(request, request.service_units))
                elif server.queue_length < server.config.queue_capacity:
                    server.queue.append(request)
                else:
                    request.dropped = True
                    server.dropped_count += 1
                    dropped_by_server[server.config.server_id] += 1

            # Capture state after routing for analysis/visualization.
            for server in servers.values():
                server.busy_ticks += server.active_count
                server.total_queue_samples += server.queue_length
                server.queue_sample_count += 1
                timeline.append(
                    ServerSnapshot(
                        tick=tick,
                        server_id=server.config.server_id,
                        available=server.config.available,
                        active=server.active_count,
                        queue=server.queue_length,
                        utilization=server.utilization,
                        load_ratio=server.load_ratio,
                    )
                )
                total_utilization += server.utilization
                total_queue_samples += server.queue_length

        # Flush a final service window so requests arriving near the end are not silently ignored.
        final_tick = config.duration_ticks
        guard = 0
        while any(server.active or server.queue for server in servers.values()) and guard < 1000:
            guard += 1
            for server in servers.values():
                newly_completed: List[ActiveRequest] = []
                remaining_active: List[ActiveRequest] = []
                for active_request in server.active:
                    active_request.remaining_units -= 1
                    if active_request.remaining_units <= 0:
                        active_request.request.completion_tick = final_tick + 1
                        newly_completed.append(active_request)
                    else:
                        remaining_active.append(active_request)
                server.active = remaining_active
                server.completed_count += len(newly_completed)
                completed_requests.extend(item.request for item in newly_completed)

                if server.config.available:
                    free_slots = max(0, server.config.processing_capacity - server.active_count)
                    while free_slots > 0 and server.queue:
                        request = server.queue.pop(0)
                        request.start_tick = final_tick
                        server.active.append(ActiveRequest(request, request.service_units))
                        free_slots -= 1
            final_tick += 1

        # Requests left active or queued after the final service window cannot complete.
        for server in servers.values():
            for active_request in server.active:
                if not active_request.request.dropped:
                    active_request.request.dropped = True
                    dropped_by_server[server.config.server_id] += 1
            for request in server.queue:
                if not request.dropped:
                    request.dropped = True
                    dropped_by_server[server.config.server_id] += 1

        # De-duplicate in the unlikely case a request was completed and collected more than once.
        unique_completed: Dict[int, Request] = {request.request_id: request for request in completed_requests}
        completed_requests = list(unique_completed.values())
        completed_requests.sort(key=lambda request: request.request_id)

        response_times = [
            (request.system_time * 1000.0) + self._tick_ms(request.server_id)
            for request in completed_requests
            if request.completion_tick is not None
        ]
        response_times.sort()
        avg_response = sum(response_times) / len(response_times) if response_times else 0.0
        p95 = self._percentile(response_times, 0.95)

        total_assigned = sum(load_distribution.values())
        requests_dropped = len(workload) - len(completed_requests)
        # Requests that remain impossible to complete after the final flush count as dropped.
        requests_dropped = max(requests_dropped, 0)

        average_utilization = total_utilization / max(1, config.duration_ticks * len(servers))
        average_queue = total_queue_samples / max(1, config.duration_ticks * len(servers))
        throughput = len(completed_requests) / max(1e-9, config.duration_ticks)

        return SimulationResult(
            algorithm=algorithm_name,
            duration_ticks=config.duration_ticks,
            requests_generated=len(workload),
            requests_completed=len(completed_requests),
            requests_dropped=requests_dropped,
            average_response_time_ms=avg_response,
            p95_response_time_ms=p95,
            throughput_rps=throughput,
            average_utilization=average_utilization,
            average_queue_length=average_queue,
            load_distribution=dict(load_distribution),
            dropped_by_server=dict(dropped_by_server),
            timeline=timeline,
            completed_requests=completed_requests,
        )

    def compare(
        self,
        algorithm_names: Optional[Iterable[str]] = None,
        weights: Optional[DynamicWeights] = None,
    ) -> Dict[str, SimulationResult]:
        names = list(algorithm_names or [
            "Round Robin",
            "Weighted Round Robin",
            "Least Connections",
            "Random Selection",
            "Multi-Factor Dynamic Scoring",
        ])
        workload = self.generate_workload()
        return {name: self.run(name, workload=workload, weights=weights) for name in names}

    def sensitivity_experiment(
        self,
        weight_sets: Iterable[DynamicWeights],
        algorithm_name: str = "Multi-Factor Dynamic Scoring",
    ) -> List[SimulationResult]:
        workload = self.generate_workload()
        return [self.run(algorithm_name, workload=workload, weights=weights) for weights in weight_sets]

    def _tick_ms(self, server_id: Optional[str]) -> float:
        if server_id is None:
            return 1.0
        for config in self.server_configs:
            if config.server_id == server_id:
                return config.base_latency_ms
        return 1.0

    @staticmethod
    def _percentile(values: List[float], percentile: float) -> float:
        if not values:
            return 0.0
        index = min(len(values) - 1, max(0, int(round((len(values) - 1) * percentile))))
        return values[index]
