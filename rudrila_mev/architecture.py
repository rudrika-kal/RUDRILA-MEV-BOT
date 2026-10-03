from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Opportunity:
    opportunity_id: str
    strategy: str
    expected_net_wei: int
    payload: object


@dataclass(frozen=True)
class SimulationResult:
    accepted: bool
    expected_net_wei: int
    reason: str
    payload: object


class OpportunityEngine(Protocol):
    def discover(self, state: object) -> list[Opportunity]: ...


class Simulator(Protocol):
    def simulate(self, opportunity: Opportunity) -> SimulationResult: ...


class SubmissionAdapter(Protocol):
    def prepare(self, simulation: SimulationResult) -> object: ...


@dataclass
class RudrilaPipeline:
    engines: list[OpportunityEngine]
    simulator: Simulator

    def discover_and_simulate(self, state: object) -> list[SimulationResult]:
        results: list[SimulationResult] = []
        for engine in self.engines:
            for opportunity in engine.discover(state):
                result = self.simulator.simulate(opportunity)
                if result.accepted:
                    results.append(result)
        return sorted(results, key=lambda x: x.expected_net_wei, reverse=True)
