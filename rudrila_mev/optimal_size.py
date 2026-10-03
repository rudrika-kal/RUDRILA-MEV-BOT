from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class SizeEvaluation:
    amount_in: int
    expected_out: int
    net_profit: int


def solve_optimal_size(
    candidate_sizes: list[int],
    quote: Callable[[int], int],
    total_cost: Callable[[int], int],
    *,
    safety_buffer_wei: int,
    min_net_profit_wei: int,
) -> SizeEvaluation | None:
    best: SizeEvaluation | None = None
    for amount in sorted(set(int(x) for x in candidate_sizes if int(x) > 0)):
        out = int(quote(amount))
        if out <= 0:
            continue
        net = out - amount - int(total_cost(amount)) - safety_buffer_wei
        row = SizeEvaluation(amount, out, net)
        if net >= min_net_profit_wei and (best is None or net > best.net_profit):
            best = row
    return best
