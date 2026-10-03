from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OpportunityRecord:
    strategy: str
    predicted_net_wei: int
    realized_net_wei: int | None
    included: bool
    gas_wei: int
    builder_bid_wei: int


@dataclass(frozen=True)
class StrategyAnalytics:
    count: int
    inclusion_rate_bps: int
    prediction_error_wei: int
    realized_net_wei: int
    avg_gas_wei: int
    avg_builder_bid_wei: int


def summarize(records: list[OpportunityRecord]) -> StrategyAnalytics:
    if not records:
        return StrategyAnalytics(0, 0, 0, 0, 0, 0)
    included = sum(1 for x in records if x.included)
    realized = sum(int(x.realized_net_wei or 0) for x in records)
    errors = [abs(int(x.predicted_net_wei) - int(x.realized_net_wei)) for x in records if x.realized_net_wei is not None]
    return StrategyAnalytics(
        len(records),
        included * 10000 // len(records),
        sum(errors) // len(errors) if errors else 0,
        realized,
        sum(x.gas_wei for x in records) // len(records),
        sum(x.builder_bid_wei for x in records) // len(records),
    )


def bounded_tuning_hint(stats: StrategyAnalytics) -> dict:
    return {
        "raise_safety_buffer": stats.prediction_error_wei > 0,
        "observed_prediction_error_wei": stats.prediction_error_wei,
        "may_lower_safety_limits": False,
        "may_enable_live_trading": False,
    }
