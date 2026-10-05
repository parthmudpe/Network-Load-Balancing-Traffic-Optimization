from __future__ import annotations

from algorithms import DynamicWeights
from engine import DEFAULT_SERVERS, SimulationEngine
from models import FailureEvent, SimulationConfig


def main() -> None:
    config = SimulationConfig(
        duration_ticks=120,
        traffic_mode="burst",
        traffic_rate=4.0,
        random_seed=42,
        failure_events=[FailureEvent(55, "S3", False), FailureEvent(75, "S3", True)],
    )
    engine = SimulationEngine(DEFAULT_SERVERS, config)
    results = engine.compare(weights=DynamicWeights())

    headers = ["Algorithm", "Generated", "Completed", "Dropped", "Avg RT ms", "P95 ms", "Throughput", "Util %", "Avg Queue"]
    print(" | ".join(headers))
    print("-" * 145)
    for result in results.values():
        print(
            f"{result.algorithm:30} | {result.requests_generated:9d} | {result.requests_completed:9d} | "
            f"{result.requests_dropped:7d} | {result.average_response_time_ms:9.2f} | {result.p95_response_time_ms:7.2f} | "
            f"{result.throughput_rps:10.3f} | {result.utilization_percent:6.2f} | {result.average_queue_length:9.2f}"
        )


if __name__ == "__main__":
    main()
