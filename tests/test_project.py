from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from algorithms import DynamicWeights, MultiFactorDynamicBalancer
from engine import DEFAULT_SERVERS, SimulationEngine
from models import FailureEvent, ServerConfig, ServerState, SimulationConfig


class ProjectTests(unittest.TestCase):
    def test_all_algorithms_run_and_conserve_workload(self):
        config = SimulationConfig(duration_ticks=40, traffic_mode="normal", traffic_rate=3, random_seed=7)
        engine = SimulationEngine(DEFAULT_SERVERS, config)
        results = engine.compare()
        self.assertEqual(len(results), 5)
        for result in results.values():
            self.assertEqual(result.requests_generated, result.requests_completed + result.requests_dropped)
            self.assertGreaterEqual(result.average_response_time_ms, 0)
            self.assertGreaterEqual(result.p95_response_time_ms, 0)
            self.assertGreaterEqual(result.throughput_rps, 0)
            self.assertGreaterEqual(result.average_queue_length, 0)
            self.assertGreaterEqual(result.utilization_percent, 0)

    def test_same_workload_is_replayed(self):
        config = SimulationConfig(duration_ticks=25, traffic_mode="high", traffic_rate=2, random_seed=11)
        engine = SimulationEngine(DEFAULT_SERVERS, config)
        workload = engine.generate_workload()
        result_rr = engine.run("Round Robin", workload=workload)
        result_random = engine.run("Random Selection", workload=workload)
        self.assertEqual(result_rr.requests_generated, result_random.requests_generated)
        self.assertEqual(
            [(r.request_id, r.arrival_tick, r.service_units) for r in workload],
            [(r.request_id, r.arrival_tick, r.service_units) for r in workload],
        )

    def test_failure_and_recovery(self):
        config = SimulationConfig(
            duration_ticks=20,
            traffic_mode="normal",
            traffic_rate=2,
            random_seed=2,
            failure_events=[FailureEvent(5, "S2", False), FailureEvent(10, "S2", True)],
        )
        engine = SimulationEngine(DEFAULT_SERVERS, config)
        result = engine.run("Multi-Factor Dynamic Scoring")
        s2_states = [snapshot for snapshot in result.timeline if snapshot.server_id == "S2"]
        self.assertFalse(s2_states[5].available)
        self.assertTrue(s2_states[10].available)


    def test_twenty_server_configuration(self):
        self.assertEqual(len(DEFAULT_SERVERS), 20)
        self.assertEqual(DEFAULT_SERVERS[0].server_id, "S1")
        self.assertEqual(DEFAULT_SERVERS[-1].server_id, "S20")
        config = SimulationConfig(duration_ticks=10, traffic_mode="normal", traffic_rate=2, random_seed=3)
        engine = SimulationEngine(DEFAULT_SERVERS[:20], config)
        result = engine.run("Round Robin")
        self.assertEqual(set(result.load_distribution.keys()), {f"S{i}" for i in range(1, 21)})

    def test_dynamic_weights_normalize(self):
        weights = DynamicWeights(2, 1, 1, 0, 0).normalized()
        self.assertAlmostEqual(weights.load, 0.5)
        self.assertAlmostEqual(weights.queue, 0.25)
        self.assertAlmostEqual(weights.response, 0.25)
        self.assertAlmostEqual(sum([
            weights.load, weights.queue, weights.response, weights.capacity, weights.availability
        ]), 1.0)

    def test_dynamic_scoring_prefers_healthier_server(self):
        servers = {
            "S1": ServerState(ServerConfig("S1", "S1", 2, 10, 60, initial_load=0.9)),
            "S2": ServerState(ServerConfig("S2", "S2", 6, 10, 20, initial_load=0.0)),
        }
        balancer = MultiFactorDynamicBalancer(weights=DynamicWeights(), seed=1)
        selected = balancer.select_server(servers, 1)
        self.assertIsNotNone(selected)
        self.assertEqual(selected.config.server_id, "S2")


if __name__ == "__main__":
    unittest.main()
