from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from algorithms import DynamicWeights, ALGORITHM_CLASSES
from engine import DEFAULT_SERVERS, SimulationEngine
from metrics import METRIC_HEADERS, result_row, write_load_distribution_csv, write_results_csv
from models import FailureEvent, ServerConfig, SimulationConfig
from visualization import VisualizationPanel


class NetworkLoadBalancingApp(tk.Tk):
    TITLE = "Network Load Balancing and Traffic Optimization System"

    def __init__(self):
        super().__init__()
        self.title(self.TITLE)
        self.geometry("1450x900")
        self.minsize(1180, 760)

        self.result_map = {}
        self.server_rows = []
        self.server_grid = None
        self.server_count_var = tk.StringVar(value="4")
        self.status_var = tk.StringVar(value="Ready")
        self.metric_var = tk.StringVar(value="response")
        self.timeline_algorithm_var = tk.StringVar(value="Multi-Factor Dynamic Scoring")
        self.timeline_value_var = tk.StringVar(value="queue")

        self._build_style()
        self._build_ui()
        self._load_defaults()

    def _build_style(self):
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("Title.TLabel", font=("TkDefaultFont", 18, "bold"))
        style.configure("Heading.TLabel", font=("TkDefaultFont", 11, "bold"))
        style.configure("Metric.TLabel", font=("TkDefaultFont", 10, "bold"))
        style.configure("Treeview", rowheight=28)

    def _build_ui(self):
        header = ttk.Frame(self, padding=(16, 12))
        header.pack(fill="x")
        ttk.Label(header, text=self.TITLE, style="Title.TLabel").pack(anchor="w")
        ttk.Label(header, text="Compare classical load balancing with Multi-Factor Dynamic Server Selection under changing traffic and server conditions.").pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=12, pady=(0, 8))

        self.dashboard_tab = ttk.Frame(notebook, padding=10)
        self.server_tab = ttk.Frame(notebook, padding=10)
        self.weight_tab = ttk.Frame(notebook, padding=10)
        self.help_tab = ttk.Frame(notebook, padding=10)
        notebook.add(self.dashboard_tab, text="Simulation Dashboard")
        notebook.add(self.server_tab, text="Server Configuration")
        notebook.add(self.weight_tab, text="Weight Experiments")
        notebook.add(self.help_tab, text="Methodology / Help")

        self._build_dashboard()
        self._build_servers()
        self._build_weight_experiment()
        self._build_help()

        status = ttk.Label(self, textvariable=self.status_var, relief="sunken", anchor="w", padding=5)
        status.pack(fill="x", padx=12, pady=(0, 8))

    def _build_dashboard(self):
        controls = ttk.LabelFrame(self.dashboard_tab, text="Simulation Controls", padding=10)
        controls.pack(fill="x")

        self.duration_var = tk.StringVar(value="120")
        self.mode_var = tk.StringVar(value="normal")
        self.rate_var = tk.StringVar(value="4")
        self.seed_var = tk.StringVar(value="42")
        self.fail_server_var = tk.StringVar(value="S3")
        self.fail_at_var = tk.StringVar(value="55")
        self.recover_at_var = tk.StringVar(value="75")
        self.load_w_var = tk.StringVar(value="0.30")
        self.queue_w_var = tk.StringVar(value="0.20")
        self.response_w_var = tk.StringVar(value="0.20")
        self.capacity_w_var = tk.StringVar(value="0.15")
        self.availability_w_var = tk.StringVar(value="0.15")

        fields = [
            ("Duration (ticks)", self.duration_var),
            ("Traffic mode", self.mode_var),
            ("Traffic rate", self.rate_var),
            ("Seed", self.seed_var),
            ("Active servers", self.server_count_var),
            ("Failure server", self.fail_server_var),
            ("Fail at tick", self.fail_at_var),
            ("Recover at tick", self.recover_at_var),
        ]
        for index, (label, variable) in enumerate(fields):
            row = index // 4
            col = (index % 4) * 2
            ttk.Label(controls, text=label).grid(row=row, column=col, sticky="w", padx=4, pady=4)
            if label == "Traffic mode":
                widget = ttk.Combobox(controls, textvariable=variable, values=["normal", "high", "burst"], state="readonly", width=13)
            elif label == "Active servers":
                widget = ttk.Combobox(controls, textvariable=variable, values=[str(i) for i in range(1, 21)], state="readonly", width=13)
                widget.bind("<<ComboboxSelected>>", self._on_server_count_changed)
            else:
                widget = ttk.Entry(controls, textvariable=variable, width=14)
            widget.grid(row=row, column=col + 1, sticky="ew", padx=4, pady=4)

        weights_frame = ttk.LabelFrame(self.dashboard_tab, text="Multi-Factor Weights (automatically normalized)", padding=8)
        weights_frame.pack(fill="x", pady=8)
        for index, (label, variable) in enumerate([
            ("Load", self.load_w_var),
            ("Queue", self.queue_w_var),
            ("Response", self.response_w_var),
            ("Capacity", self.capacity_w_var),
            ("Availability", self.availability_w_var),
        ]):
            ttk.Label(weights_frame, text=label).grid(row=0, column=index * 2, sticky="w", padx=3)
            ttk.Entry(weights_frame, textvariable=variable, width=8).grid(row=0, column=index * 2 + 1, padx=(0, 12))

        buttons = ttk.Frame(self.dashboard_tab)
        buttons.pack(fill="x", pady=(2, 8))
        ttk.Button(buttons, text="Run Full Comparison", command=self.run_comparison).pack(side="left", padx=(0, 6))
        ttk.Button(buttons, text="Run Selected Algorithm", command=self.run_selected).pack(side="left", padx=6)
        self.selected_algorithm_var = tk.StringVar(value="Multi-Factor Dynamic Scoring")
        ttk.Combobox(buttons, textvariable=self.selected_algorithm_var, values=list(ALGORITHM_CLASSES.keys()), state="readonly", width=28).pack(side="left", padx=6)
        ttk.Button(buttons, text="Export Results CSV", command=self.export_results).pack(side="right", padx=4)
        ttk.Button(buttons, text="Export Load CSV", command=self.export_load).pack(side="right", padx=4)

        table_frame = ttk.LabelFrame(self.dashboard_tab, text="Performance Results", padding=6)
        table_frame.pack(fill="x", pady=4)
        columns = ["Algorithm", "Generated", "Completed", "Dropped", "Drop %", "Avg RT (ms)", "P95 RT (ms)", "Throughput", "Util %", "Avg Queue"]
        self.results_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=7)
        for column in columns:
            self.results_tree.heading(column, text=column)
            width = 170 if column == "Algorithm" else 95
            self.results_tree.column(column, width=width, anchor="center")
        self.results_tree.pack(side="left", fill="x", expand=True)
        table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.results_tree.yview)
        table_scroll.pack(side="right", fill="y")
        self.results_tree.configure(yscrollcommand=table_scroll.set)

        chart_controls = ttk.Frame(self.dashboard_tab)
        chart_controls.pack(fill="x", pady=(6, 3))
        ttk.Label(chart_controls, text="Comparison chart:").pack(side="left")
        metric_names = {
            "response": "Average Response",
            "p95": "P95 Response",
            "throughput": "Throughput",
            "utilization": "Utilization",
            "queue": "Queue Length",
            "dropped": "Dropped Requests",
        }
        self.metric_combo = ttk.Combobox(chart_controls, textvariable=self.metric_var, values=list(metric_names.keys()), state="readonly", width=18)
        self.metric_combo.pack(side="left", padx=6)
        ttk.Button(chart_controls, text="Load Distribution", command=self.chart_load_distribution).pack(side="left", padx=4)
        ttk.Button(chart_controls, text="Plot Comparison", command=self.chart_comparison).pack(side="left", padx=4)
        ttk.Label(chart_controls, text="Timeline:").pack(side="left", padx=(20, 4))
        ttk.Combobox(chart_controls, textvariable=self.timeline_algorithm_var, values=list(ALGORITHM_CLASSES.keys()), state="readonly", width=28).pack(side="left", padx=4)
        ttk.Combobox(chart_controls, textvariable=self.timeline_value_var, values=["queue", "active", "utilization"], state="readonly", width=14).pack(side="left", padx=4)
        ttk.Button(chart_controls, text="Plot Timeline", command=self.chart_timeline).pack(side="left", padx=4)

        chart_frame = ttk.LabelFrame(self.dashboard_tab, text="Visualization", padding=3)
        chart_frame.pack(fill="both", expand=True, pady=(4, 0))
        self.visualization = VisualizationPanel(chart_frame)

    def _build_servers(self):
        ttk.Label(self.server_tab, text="Edit the server parameters used in every simulation run. The Active servers setting on the dashboard selects S1 through the chosen server number (1–20).", style="Heading.TLabel").pack(anchor="w", pady=(0, 8))
        self.server_grid = ttk.Frame(self.server_tab)
        self.server_grid.pack(fill="x")
        self._render_server_rows()

        note = ttk.LabelFrame(self.server_tab, text="Parameter meaning", padding=10)
        note.pack(fill="x", pady=15)
        ttk.Label(note, text=(
            "Processing capacity = maximum concurrent active requests. Queue capacity = waiting requests allowed. "
            "Base latency contributes to reported response time and dynamic scoring. Initial load creates a baseline load penalty. "
            "Weighted RR weight controls the weighted scheduler only."
        ), wraplength=1200, justify="left").pack(anchor="w")

    def _render_server_rows(self):
        for child in self.server_grid.winfo_children():
            child.destroy()
        self.server_rows = []
        headers = ["ID", "Name", "Processing Capacity", "Queue Capacity", "Base Latency (ms)", "Initial Load (0-1)", "Weighted RR Weight"]
        for col, header in enumerate(headers):
            ttk.Label(self.server_grid, text=header, style="Metric.TLabel").grid(row=0, column=col, padx=5, pady=5, sticky="w")

        for row, config in enumerate(DEFAULT_SERVERS, start=1):
            vars_row = [
                tk.StringVar(value=config.server_id),
                tk.StringVar(value=config.name),
                tk.StringVar(value=str(config.processing_capacity)),
                tk.StringVar(value=str(config.queue_capacity)),
                tk.StringVar(value=str(config.base_latency_ms)),
                tk.StringVar(value=str(config.initial_load)),
                tk.StringVar(value=str(config.algorithm_weight)),
            ]
            self.server_rows.append(vars_row)
            for col, variable in enumerate(vars_row):
                width = 12 if col != 1 else 22
                entry = ttk.Entry(self.server_grid, textvariable=variable, width=width)
                entry.grid(row=row, column=col, padx=5, pady=4, sticky="ew")
                if row > int(self.server_count_var.get()):
                    entry.configure(state="disabled")

    def _on_server_count_changed(self, _event=None):
        try:
            count = int(self.server_count_var.get())
            self.fail_server_var.set("S3" if count >= 3 else "S1")
            self._render_server_rows()
            self.status_var.set(f"Active server count set to {count}: S1–S{count} will be used.")
        except ValueError:
            pass

    def _build_weight_experiment(self):
        ttk.Label(self.weight_tab, text="Sensitivity analysis for the proposed Multi-Factor Dynamic Scoring method.", style="Heading.TLabel").pack(anchor="w")
        ttk.Label(self.weight_tab, text="The five presets below isolate the effect of each decision factor while keeping the same workload and failure events.", wraplength=1100).pack(anchor="w", pady=(4, 10))
        ttk.Button(self.weight_tab, text="Run Weight Sensitivity Experiment", command=self.run_weight_experiment).pack(anchor="w", pady=(0, 10))

        columns = ["Preset", "Load", "Queue", "Response", "Capacity", "Availability", "Avg RT (ms)", "P95 RT (ms)", "Throughput", "Dropped"]
        frame = ttk.Frame(self.weight_tab)
        frame.pack(fill="both", expand=True)
        self.weight_tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
        for column in columns:
            self.weight_tree.heading(column, text=column)
            self.weight_tree.column(column, width=110 if column != "Preset" else 170, anchor="center")
        self.weight_tree.pack(fill="both", expand=True)

    def _build_help(self):
        text = tk.Text(self.help_tab, wrap="word", padx=12, pady=12)
        text.pack(fill="both", expand=True)
        help_text = (
            "PROJECT IMPLEMENTATION\n\n"
            "Algorithms\n"
            "1. Round Robin: rotates requests across currently available servers.\n"
            "2. Weighted Round Robin: assigns a larger share of requests to servers with larger configured weights.\n"
            "3. Least Connections: selects the server with the smallest active-plus-queued request count.\n"
            "4. Random Selection: chooses an available server uniformly at random using the configured seed.\n"
            "5. Multi-Factor Dynamic Scoring: scores servers using load, queue length, response latency, processing capacity, and availability.\n\n"
            "Simulation methodology\n"
            "• A workload is generated once and replayed for every algorithm, making comparisons fair.\n"
            "• Traffic modes are normal, high, and burst.\n"
            "• Server failures can be scheduled at a tick and recovery can be scheduled later.\n"
            "• Active server count can be changed from 1 to 20; a run uses S1 through the selected server number.\n"
            "• Each simulation tick represents one second. Requests have randomized service requirements, while server capacities determine how many can be active at once.\n\n"
            "Reported metrics\n"
            "Average response time, P95 response time, throughput, average utilization, average queue length, dropped requests, and per-server request distribution.\n\n"
        )
        text.insert("1.0", help_text)
        text.configure(state="disabled")

    def _load_defaults(self):
        self.status_var.set("Ready — configure the scenario and click Run Full Comparison.")

    def _read_simulation_inputs(self) -> SimulationConfig:
        duration = max(1, int(self.duration_var.get()))
        rate = max(0.0, float(self.rate_var.get()))
        seed = int(self.seed_var.get())
        mode = self.mode_var.get().strip().lower()
        failure_events = []
        fail_server = self.fail_server_var.get().strip()
        fail_at_text = self.fail_at_var.get().strip()
        recover_at_text = self.recover_at_var.get().strip()

        if fail_server and fail_at_text:
            fail_at = int(fail_at_text)
            if not 0 <= fail_at < duration:
                raise ValueError("Failure tick must be within the simulation duration.")
            failure_events.append(FailureEvent(fail_at, fail_server, False))
            if recover_at_text:
                recover_at = int(recover_at_text)
                if recover_at <= fail_at or recover_at >= duration:
                    raise ValueError("Recovery tick must be after failure and inside the simulation duration.")
                failure_events.append(FailureEvent(recover_at, fail_server, True))

        return SimulationConfig(
            duration_ticks=duration,
            traffic_mode=mode,
            traffic_rate=rate,
            random_seed=seed,
            failure_events=failure_events,
        )

    def _read_servers(self):
        configs = []
        seen = set()
        active_count = int(self.server_count_var.get())
        for vars_row in self.server_rows[:active_count]:
            server_id = vars_row[0].get().strip()
            name = vars_row[1].get().strip()
            capacity = int(vars_row[2].get())
            queue_capacity = int(vars_row[3].get())
            latency = float(vars_row[4].get())
            initial_load = float(vars_row[5].get())
            weight = int(vars_row[6].get())
            if not server_id or server_id in seen:
                raise ValueError("Server IDs must be non-empty and unique.")
            if capacity <= 0 or queue_capacity < 0 or latency < 0:
                raise ValueError("Capacity, queue capacity, and latency must be valid non-negative/positive values.")
            if not 0 <= initial_load <= 1:
                raise ValueError("Initial load must be between 0 and 1.")
            if weight <= 0:
                raise ValueError("Weighted RR weights must be positive integers.")
            seen.add(server_id)
            configs.append(ServerConfig(server_id, name, capacity, queue_capacity, latency, initial_load, True, weight))
        return configs

    def _read_weights(self) -> DynamicWeights:
        return DynamicWeights(
            float(self.load_w_var.get()),
            float(self.queue_w_var.get()),
            float(self.response_w_var.get()),
            float(self.capacity_w_var.get()),
            float(self.availability_w_var.get()),
        ).normalized()

    def _build_engine(self):
        return SimulationEngine(self._read_servers(), self._read_simulation_inputs())

    def _populate_results(self, results):
        self.result_map = results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        for result in results.values():
            row = result_row(result)
            self.results_tree.insert("", "end", values=(
                row[0], row[1], row[2], row[3], f"{row[4]:.2f}", f"{row[5]:.2f}",
                f"{row[6]:.2f}", f"{row[7]:.3f}", f"{row[8]:.2f}", f"{row[9]:.2f}"
            ))
        self.timeline_algorithm_var.set(next(iter(results)) if results else "Multi-Factor Dynamic Scoring")

    def run_comparison(self):
        try:
            engine = self._build_engine()
            weights = self._read_weights()
            self.status_var.set("Running full comparison…")
            self.update_idletasks()
            self._populate_results(engine.compare(weights=weights))
            self.visualization.plot_comparison(self.result_map, self.metric_var.get())
            self.status_var.set("Full comparison completed.")
        except Exception as exc:
            messagebox.showerror("Simulation Error", str(exc))
            self.status_var.set("Simulation failed — check inputs.")

    def run_selected(self):
        try:
            engine = self._build_engine()
            weights = self._read_weights()
            algorithm = self.selected_algorithm_var.get()
            workload = engine.generate_workload()
            result = engine.run(algorithm, workload=workload, weights=weights)
            self._populate_results({algorithm: result})
            self.visualization.plot_timeline(result, self.timeline_value_var.get())
            self.status_var.set(f"Completed: {algorithm}")
        except Exception as exc:
            messagebox.showerror("Simulation Error", str(exc))
            self.status_var.set("Simulation failed — check inputs.")

    def chart_comparison(self):
        if not self.result_map:
            messagebox.showinfo("No results", "Run a comparison first.")
            return
        self.visualization.plot_comparison(self.result_map, self.metric_var.get())

    def chart_load_distribution(self):
        if not self.result_map:
            messagebox.showinfo("No results", "Run a comparison first.")
            return
        self.visualization.plot_load_distribution(self.result_map)

    def chart_timeline(self):
        if not self.result_map:
            messagebox.showinfo("No results", "Run a simulation first.")
            return
        algorithm = self.timeline_algorithm_var.get()
        if algorithm not in self.result_map:
            messagebox.showinfo("No result", f"Run {algorithm} first.")
            return
        self.visualization.plot_timeline(self.result_map[algorithm], self.timeline_value_var.get())

    def run_weight_experiment(self):
        try:
            engine = self._build_engine()
            presets = [
                ("Balanced", DynamicWeights(0.30, 0.20, 0.20, 0.15, 0.15)),
                ("Load-heavy", DynamicWeights(0.60, 0.10, 0.10, 0.10, 0.10)),
                ("Queue-heavy", DynamicWeights(0.10, 0.60, 0.10, 0.10, 0.10)),
                ("Response-heavy", DynamicWeights(0.10, 0.10, 0.60, 0.10, 0.10)),
                ("Capacity-heavy", DynamicWeights(0.10, 0.10, 0.10, 0.60, 0.10)),
            ]
            results = engine.sensitivity_experiment([weights for _, weights in presets])
            for item in self.weight_tree.get_children():
                self.weight_tree.delete(item)
            for (label, weights), result in zip(presets, results):
                w = weights.normalized()
                self.weight_tree.insert("", "end", values=(
                    label, f"{w.load:.2f}", f"{w.queue:.2f}", f"{w.response:.2f}", f"{w.capacity:.2f}", f"{w.availability:.2f}",
                    f"{result.average_response_time_ms:.2f}", f"{result.p95_response_time_ms:.2f}", f"{result.throughput_rps:.3f}", result.requests_dropped,
                ))
            self.status_var.set("Weight sensitivity experiment completed.")
        except Exception as exc:
            messagebox.showerror("Experiment Error", str(exc))

    def export_results(self):
        if not self.result_map:
            messagebox.showinfo("No results", "Run a comparison first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="algorithm_results.csv")
        if path:
            write_results_csv(self.result_map.values(), path)
            self.status_var.set(f"Results exported to {Path(path).name}")

    def export_load(self):
        if not self.result_map:
            messagebox.showinfo("No results", "Run a comparison first.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")], initialfile="load_distribution.csv")
        if path:
            write_load_distribution_csv(self.result_map.values(), path)
            self.status_var.set(f"Load distribution exported to {Path(path).name}")


if __name__ == "__main__":
    app = NetworkLoadBalancingApp()
    app.mainloop()
