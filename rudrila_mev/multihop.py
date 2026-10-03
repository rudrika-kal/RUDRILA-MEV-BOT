from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .market_state import InMemoryMarketState, PoolState


@dataclass(frozen=True)
class RouteLeg:
    pool: PoolState
    token_in: str
    token_out: str


@dataclass(frozen=True)
class RouteCandidate:
    legs: tuple[RouteLeg, ...]


@dataclass(frozen=True)
class RouteEvaluation:
    route: RouteCandidate
    amount_in: int
    amount_out: int
    gross_profit: int
    accepted: bool
    reason: str


def discover_cycles(
    state: InMemoryMarketState,
    base_token: str,
    *,
    max_hops: int = 3,
) -> tuple[RouteCandidate, ...]:
    base = base_token.lower()
    found: list[RouteCandidate] = []

    def walk(
        token: str,
        legs: list[RouteLeg],
        used_pools: set[object],
    ) -> None:
        if len(legs) >= max_hops:
            return
        for pool in state.neighbors(token):
            if pool.key in used_pools:
                continue
            a = pool.token0.lower()
            b = pool.token1.lower()
            if token not in (a, b):
                continue
            nxt = b if token == a else a
            leg = RouteLeg(pool, token, nxt)
            new_legs = legs + [leg]
            if nxt == base and len(new_legs) >= 2:
                found.append(RouteCandidate(tuple(new_legs)))
                continue
            if any(
                x.token_in == nxt for x in new_legs[:-1]
            ):
                continue
            walk(
                nxt,
                new_legs,
                used_pools | {pool.key},
            )

    walk(base, [], set())
    unique: dict[
        tuple[str, ...], RouteCandidate
    ] = {}
    for route in found:
        sig = tuple(
            x.pool.key.pool.lower() + ":" + x.token_in
            for x in route.legs
        )
        unique[sig] = route
    return tuple(unique.values())


def evaluate_route(
    route: RouteCandidate,
    amount_in: int,
    quote_leg: Callable[[RouteLeg, int], int],
    *,
    explicit_cost_wei: int = 0,
    safety_buffer_wei: int = 0,
    min_net_profit_wei: int = 1,
) -> RouteEvaluation:
    amount = int(amount_in)
    if amount <= 0:
        raise ValueError("amount_in must be positive")
    for leg in route.legs:
        amount = int(quote_leg(leg, amount))
        if amount <= 0:
            return RouteEvaluation(
                route,
                int(amount_in),
                0,
                -int(amount_in),
                False,
                "BLOCK: route leg has zero output",
            )
    gross = amount - int(amount_in)
    required = (
        int(explicit_cost_wei)
        + int(safety_buffer_wei)
        + int(min_net_profit_wei)
    )
    accepted = gross >= required
    reason = (
        "PASS: multi-hop cycle clears net-profit gate"
        if accepted
        else "BLOCK: route below all-cost profit threshold"
    )
    return RouteEvaluation(
        route,
        int(amount_in),
        amount,
        gross,
        accepted,
        reason,
    )
