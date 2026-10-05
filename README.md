# Network Load Balancing and Traffic Optimization System

A software-based Computer Networks project that simulates client requests, distributes traffic across heterogeneous servers, injects server failures/recovery, and compares five server-selection strategies.

## Implemented techniques

1. Round Robin
2. Weighted Round Robin
3. Least Connections
4. Random Selection
5. Multi-Factor Dynamic Server Selection (proposed method)

The proposed method scores available servers using:

- Current load
- Queue length
- Base response latency
- Processing capacity
- Availability

Weights are normalized automatically. The GUI also provides five weight-sensitivity presets.

## Traffic and failure simulation

Traffic modes:

- Normal
- High
- Burst

Each simulation tick represents one second. A workload is generated once and replayed for every algorithm so comparisons use identical arrivals and service requirements.

The GUI supports a scheduled server failure and later recovery. The default demonstration scenario takes S3 offline at tick 55 and recovers it at tick 75.

## Metrics

The system reports:

- Requests generated
- Requests completed
- Dropped requests
- Drop rate
- Average response time
- P95 response time
- Throughput (requests/second)
- Average server utilization
- Average queue length
- Per-server load distribution

## Project structure

```text
NetworkLoadBalancingTrafficOptimizationSystem/
├── app.py                 # Tkinter graphical interface
├── engine.py              # Simulation engine and experiment runner
├── router.py              # Routing facade
├── algorithms.py          # All five load-balancing strategies
├── models.py              # Data models and simulation configuration
├── traffic.py             # Repeatable traffic generator
├── metrics.py             # Result formatting and CSV export
├── visualization.py       # Matplotlib charts embedded in GUI
├── run_demo.py            # Terminal demonstration
├── requirements.txt
├── README.md
└── tests/
    └── test_project.py
```

## How to run

### 1. Create a virtual environment

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Windows:

```powershell
py -m venv .venv
.venv\\Scripts\\activate
```

### 2. Install Python dependencies

```bash
python -m pip install -r requirements.txt
```

On Linux, Tkinter may also need the operating-system package `python3-tk`.

### 3. Start the GUI

```bash
python app.py
```

### 4. Run the terminal demo

```bash
python run_demo.py
```

### 5. Run tests

```bash
python -m unittest discover -s tests -v
```

## GUI workflow

1. Open the **Simulation Dashboard**.
2. Set duration, traffic mode, traffic rate, and random seed.
3. Configure failure and recovery ticks, or clear them to remove the failure scenario.
4. Edit factor weights for Multi-Factor Dynamic Scoring.
5. Open **Server Configuration** to change capacity, queue size, latency, baseline load, and Weighted RR weights.
6. Run **Full Comparison**.
7. Switch between response time, P95, throughput, utilization, queue length, and dropped-request charts.
8. Use **Load Distribution** and **Timeline** plots for the project demonstration.
9. Export results as CSV for tables in your report.
10. Run the **Weight Experiments** tab to study sensitivity to factor weights.

## Interpretation of the proposed method

For each available server, the selector converts the five factors into normalized scores and computes a weighted sum:

`Score = wL*LoadScore + wQ*QueueScore + wR*ResponseScore + wC*CapacityScore + wA*AvailabilityScore`

Higher scores are preferred. Lower current load, shorter queues, lower latency, higher processing capacity, and availability all increase the score.

## Scope and limitation

This implementation is a software simulation for academic evaluation. It models request arrivals, queues, concurrent service slots, latency, and server availability; it does not transmit real network packets or replace an operational production load balancer.

### Variable server-count experiments

The GUI supports 4 to 8 active servers. Select the **Active servers** value on the Simulation Dashboard; a run uses S1 through the selected server number. This allows experiments such as 4, 5, 6, 7, and 8 servers using the same algorithms and workload settings.
