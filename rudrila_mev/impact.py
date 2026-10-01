from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ImpactDecision:
    accepted: bool
    impact_bps: int
    reason: str


def calculate_price_impact_bps(
    *,
    actual_amount_in: int,
    actual_amount_out: int,
    probe_amount_in: int,
    probe_amount_out: int,
) -> int:
    if min(actual_amount_in, actual_amount_out, probe_amount_in, probe_amount_out) <= 0:
        raise ValueError("quote amounts must be positive")

    # Marginal probe rate approximates the no-impact rate.
    # expected_out = actual_in * probe_out / probe_in
    expected_out = actual_amount_in * probe_amount_out // probe_amount_in
    if expected_out <= 0:
        raise ValueError("invalid expected output")
    if actual_amount_out >= expected_out:
        return 0
    return (expected_out - actual_amount_out) * 10_000 // expected_out


def impact_guard(
    *,
    impact_bps: int,
    min_impact_bps: int,
    max_impact_bps: int,
) -> ImpactDecision:
    if impact_bps < min_impact_bps:
        return ImpactDecision(False, impact_bps, "REJECT: impact below configured bound")
    if impact_bps > max_impact_bps:
        return ImpactDecision(False, impact_bps, "REJECT: price impact too high")
    return ImpactDecision(True, impact_bps, "PASS: price impact within bounds")
