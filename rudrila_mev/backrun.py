from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BackrunCandidate:
    trigger_hash: str
    trigger_block: int
    observed_block: int
    trigger_index: int
    execution_index: int
    expected_gross_wei: int
    gas_wei: int
    builder_bid_wei: int
    safety_buffer_wei: int
    min_net_profit_wei: int
    user_harm_wei: int = 0


@dataclass(frozen=True)
class BackrunDecision:
    accepted: bool
    expected_net_wei: int
    reasons: tuple[str, ...]


def evaluate_legitimate_backrun(c: BackrunCandidate) -> BackrunDecision:
    reasons: list[str] = []
    if not c.trigger_hash.startswith("0x") or len(c.trigger_hash) != 66:
        reasons.append("BLOCK: invalid trigger hash")
    if c.observed_block < c.trigger_block:
        reasons.append("BLOCK: trigger not yet observed")
    if c.execution_index <= c.trigger_index:
        reasons.append("BLOCK: execution is not strictly after trigger")
    if c.user_harm_wei != 0:
        reasons.append("BLOCK: user-harmful opportunity refused")
    costs = c.gas_wei + c.builder_bid_wei + c.safety_buffer_wei
    net = c.expected_gross_wei - costs
    if net < c.min_net_profit_wei:
        reasons.append("BLOCK: backrun below minimum net profit")
    if not reasons:
        reasons.append("PASS: legitimate post-trigger backrun")
    return BackrunDecision(not any(x.startswith("BLOCK:") for x in reasons), net, tuple(reasons))


@dataclass(frozen=True)
class BackrunRouteQuote:
    route_id: str
    expected_gross_wei: int
    gas_wei: int
    builder_bid_wei: int
    safety_buffer_wei: int
    min_net_profit_wei: int


class LegitimateBackrunEngine:
    def evaluate_routes(
        self,
        *,
        trigger_hash: str,
        trigger_block: int,
        observed_block: int,
        trigger_index: int,
        execution_index: int,
        routes: list[BackrunRouteQuote],
    ) -> tuple[tuple[str, BackrunDecision], ...]:
        out: list[tuple[str, BackrunDecision]] = []
        for route in routes:
            candidate = BackrunCandidate(
                trigger_hash=trigger_hash,
                trigger_block=trigger_block,
                observed_block=observed_block,
                trigger_index=trigger_index,
                execution_index=execution_index,
                expected_gross_wei=route.expected_gross_wei,
                gas_wei=route.gas_wei,
                builder_bid_wei=route.builder_bid_wei,
                safety_buffer_wei=route.safety_buffer_wei,
                min_net_profit_wei=route.min_net_profit_wei,
                user_harm_wei=0,
            )
            decision = evaluate_legitimate_backrun(candidate)
            if decision.accepted:
                out.append((route.route_id, decision))
        return tuple(sorted(out, key=lambda x: x[1].expected_net_wei, reverse=True))
