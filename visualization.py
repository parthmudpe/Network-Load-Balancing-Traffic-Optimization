from __future__ import annotations

from collections import defaultdict
from typing import Dict, Iterable, Optional

import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from models import SimulationResult


class VisualizationPanel:
    """Matplotlib-backed charts embedded inside the Tkinter application."""

    def __init__(self, parent):
        self.figure = plt.Figure(figsize=(11, 6.5), dpi=100)
        self.axes = self.figure.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.figure, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

    def clear(self, title: str = ""):
        self.figure.clear()
        self.axes = self.figure.add_subplot(111)
        if title:
            self.axes.set_title(title)
        self.canvas.draw_idle()

    def plot_comparison(self, results: Dict[str, SimulationResult], metric: str):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        names = list(results.keys())

        if metric == "response":
            values = [results[name].average_response_time_ms for name in names]
            ylabel = "Average Response Time (ms)"
        elif metric == "throughput":
            values = [results[name].throughput_rps for name in names]
            ylabel = "Throughput (requests/tick)"
        elif metric == "utilization":
            values = [results[name].utilization_percent for name in names]
            ylabel = "Average Utilization (%)"
        elif metric == "queue":
            values = [results[name].average_queue_length for name in names]
            ylabel = "Average Queue Length"
        elif metric == "dropped":
            values = [results[name].requests_dropped for name in names]
            ylabel = "Dropped Requests"
        else:
            values = [results[name].p95_response_time_ms for name in names]
            ylabel = "P95 Response Time (ms)"

        ax.bar(range(len(names)), values)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels(names, rotation=18, ha="right")
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
        ax.set_title(f"Algorithm Comparison — {ylabel}")
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def plot_load_distribution(self, results: Dict[str, SimulationResult]):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        names = list(results.keys())
        server_ids = sorted({sid for result in results.values() for sid in result.load_distribution})
        x = list(range(len(names)))
        width = 0.8 / max(1, len(server_ids))

        for index, server_id in enumerate(server_ids):
            values = [results[name].load_distribution.get(server_id, 0) for name in names]
            offsets = [pos - 0.4 + width / 2 + index * width for pos in x]
            ax.bar(offsets, values, width=width, label=server_id)

        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=18, ha="right")
        ax.set_ylabel("Requests Assigned")
        ax.set_title("Load Distribution Across Servers")
        ax.legend()
        ax.grid(axis="y", alpha=0.25)
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def plot_timeline(self, result: SimulationResult, value: str = "queue"):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        grouped = defaultdict(lambda: {"tick": [], "value": []})
        for snapshot in result.timeline:
            grouped[snapshot.server_id]["tick"].append(snapshot.tick)
            if value == "utilization":
                grouped[snapshot.server_id]["value"].append(snapshot.utilization * 100)
            elif value == "active":
                grouped[snapshot.server_id]["value"].append(snapshot.active)
            else:
                grouped[snapshot.server_id]["value"].append(snapshot.queue)

        for server_id, series in sorted(grouped.items()):
            ax.plot(series["tick"], series["value"], label=server_id)

        ax.set_xlabel("Simulation Tick")
        ax.set_ylabel({"queue": "Queue Length", "active": "Active Requests", "utilization": "Utilization (%)"}.get(value, value))
        ax.set_title(f"{result.algorithm} — Server State Over Time")
        ax.grid(alpha=0.25)
        ax.legend()
        self.figure.tight_layout()
        self.canvas.draw_idle()
