from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FlashLiquidityPlan:
    provider: str
    asset: str
    principal_wei: int
    fee_wei: int
    expected_final_wei: int
    gas_wei: int
    builder_bid_wei: int
    safety_buffer_wei: int
    min_net_profit_wei: int


@dataclass(frozen=True)
class FlashLiquidityDecision:
    accepted: bool
    expected_net_wei: int
    reasons: tuple[str, ...]


def evaluate_flash_liquidity(p: FlashLiquidityPlan) -> FlashLiquidityDecision:
    reasons: list[str] = []
    if p.principal_wei <= 0:
        reasons.append("BLOCK: flash principal must be positive")
    if min(p.fee_wei, p.gas_wei, p.builder_bid_wei, p.safety_buffer_wei) < 0:
        reasons.append("BLOCK: flash costs cannot be negative")
    repay = p.principal_wei + p.fee_wei
    net = p.expected_final_wei - repay - p.gas_wei - p.builder_bid_wei - p.safety_buffer_wei
    if p.expected_final_wei < repay:
        reasons.append("BLOCK: flash principal plus fee cannot be repaid")
    if net < p.min_net_profit_wei:
        reasons.append("BLOCK: flash-liquidity route below minimum net profit")
    if not reasons:
        reasons.append("PASS: flash-liquidity plan repays atomically and clears profit gate")
    return FlashLiquidityDecision(not any(x.startswith("BLOCK:") for x in reasons), net, tuple(reasons))
