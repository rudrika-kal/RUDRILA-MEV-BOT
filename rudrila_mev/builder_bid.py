from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BidQuote:
    bid_wei: int
    expected_value_wei: int
    inclusion_probability_bps: int


def optimize_builder_bid(
    candidate_bids_wei: list[int],
    inclusion_probability_bps: list[int],
    *,
    gross_profit_wei: int,
    gas_wei: int,
    other_cost_wei: int,
    safety_buffer_wei: int,
    min_net_profit_wei: int,
) -> BidQuote | None:
    if len(candidate_bids_wei) != len(inclusion_probability_bps):
        raise ValueError("bid and probability arrays must match")
    max_bid = gross_profit_wei - gas_wei - other_cost_wei - safety_buffer_wei - min_net_profit_wei
    best: BidQuote | None = None
    for bid, prob in zip(candidate_bids_wei, inclusion_probability_bps):
        bid, prob = int(bid), int(prob)
        if bid < 0 or bid > max_bid or not 0 <= prob <= 10000:
            continue
        realized = gross_profit_wei - gas_wei - other_cost_wei - safety_buffer_wei - bid
        ev = realized * prob // 10000
        row = BidQuote(bid, ev, prob)
        if best is None or row.expected_value_wei > best.expected_value_wei:
            best = row
    return best
