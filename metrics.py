from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List

from models import SimulationResult


METRIC_HEADERS = [
    "Algorithm",
    "Generated",
    "Completed",
    "Dropped",
    "Drop Rate (%)",
    "Avg Response (ms)",
    "P95 Response (ms)",
    "Throughput (req/tick)",
    "Avg Utilization (%)",
    "Avg Queue Length",
]


def result_row(result: SimulationResult) -> List[object]:
    return [
        result.algorithm,
        result.requests_generated,
        result.requests_completed,
        result.requests_dropped,
        round(result.drop_rate * 100, 2),
        round(result.average_response_time_ms, 2),
        round(result.p95_response_time_ms, 2),
        round(result.throughput_rps, 3),
        round(result.utilization_percent, 2),
        round(result.average_queue_length, 2),
    ]


def write_results_csv(results: Iterable[SimulationResult], path: str | Path) -> None:
    path = Path(path)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(METRIC_HEADERS)
        for result in results:
            writer.writerow(result_row(result))


def write_load_distribution_csv(results: Iterable[SimulationResult], path: str | Path) -> None:
    results = list(results)
    server_ids = sorted({sid for result in results for sid in result.load_distribution})
    with Path(path).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["Algorithm", *server_ids])
        for result in results:
            writer.writerow([result.algorithm, *[result.load_distribution.get(sid, 0) for sid in server_ids]])


def summary_text(result: SimulationResult) -> str:
    return (
        f"{result.algorithm}: {result.requests_completed}/{result.requests_generated} completed, "
        f"{result.requests_dropped} dropped, average response {result.average_response_time_ms:.2f} ms, "
        f"throughput {result.throughput_rps:.2f} req/tick."
    )
