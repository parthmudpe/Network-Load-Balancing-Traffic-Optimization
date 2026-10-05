from __future__ import annotations

import random
from typing import List

from models import RequestTemplate, SimulationConfig


class TrafficGenerator:
    """Creates repeatable workload templates for fair algorithm comparisons."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.rng = random.Random(config.random_seed)

    def _request_count(self) -> int:
        mode = self.config.traffic_mode.lower()
        rate = max(0.0, self.config.traffic_rate)

        if mode == "high":
            rate *= 2.0
        elif mode == "burst":
            if self.rng.random() < self.config.burst_probability:
                rate *= max(1.0, self.config.burst_multiplier)
            else:
                rate *= 0.65

        # Knuth Poisson sampler, avoiding third-party dependencies.
        if rate <= 0:
            return 0
        if rate > 30:
            # Normal approximation is stable and fast at high rates.
            return max(0, int(round(self.rng.gauss(rate, rate ** 0.5))))

        limit = 2.718281828459045 ** (-rate)
        product = 1.0
        count = 0
        while product > limit:
            count += 1
            product *= self.rng.random()
        return count - 1

    def generate(self) -> List[RequestTemplate]:
        requests: List[RequestTemplate] = []
        request_id = 1

        for tick in range(self.config.duration_ticks):
            count = self._request_count()
            for _ in range(count):
                units = self.rng.randint(
                    self.config.service_units_min,
                    max(self.config.service_units_min, self.config.service_units_max),
                )
                requests.append(
                    RequestTemplate(
                        request_id=request_id,
                        arrival_tick=tick,
                        service_units=units,
                    )
                )
                request_id += 1

        return requests
