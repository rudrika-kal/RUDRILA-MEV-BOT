from __future__ import annotations

from dataclasses import dataclass
from math import sqrt


@dataclass(frozen=True)
class InclusionHistory:
    attempts: int
    included: int


@dataclass(frozen=True)
class InclusionDecision:
    accepted: bool
    conservative_probability_bps: int
    expected_value_wei: int


def wilson_lower_bps(history: InclusionHistory, z: float = 1.96) -> int:
    n = int(history.attempts)
    k = int(history.included)
    if n <= 0 or k < 0 or k > n:
        return 0
    p = k / n
    den = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0, min(10000, int(10000 * (centre - margin) / den)))


def evaluate_inclusion_ev(
    history: InclusionHistory,
    *,
    net_if_included_wei: int,
    noninclusion_cost_wei: int = 0,
    min_expected_value_wei: int = 1,
) -> InclusionDecision:
    p = wilson_lower_bps(history)
    ev = (net_if_included_wei * p - noninclusion_cost_wei * (10000 - p)) // 10000
    return InclusionDecision(ev >= min_expected_value_wei, p, ev)
