from __future__ import annotations

from dataclasses import dataclass

from .risk_guard import ContractRiskDecision


@dataclass(frozen=True)
class PreTradeDecision:
    allowed: bool
    reason: str


def pretrade_gate(
    *,
    contract_risk: ContractRiskDecision,
    liquidity_ok: bool,
    price_impact_ok: bool,
    simulation_ok: bool,
    gas_profit_ok: bool,
) -> PreTradeDecision:
    # Order matters: contract risk is deliberately checked FIRST.
    if not contract_risk.accepted:
        return PreTradeDecision(False, "NO TRADE: contract risk gate blocked token")
    if not liquidity_ok:
        return PreTradeDecision(False, "NO TRADE: liquidity gate failed")
    if not price_impact_ok:
        return PreTradeDecision(False, "NO TRADE: price-impact gate failed")
    if not simulation_ok:
        return PreTradeDecision(False, "NO TRADE: buy/sell simulation gate failed")
    if not gas_profit_ok:
        return PreTradeDecision(False, "NO TRADE: gas/fees/net-profit gate failed")
    return PreTradeDecision(True, "TRADE ALLOWED: every mandatory gate passed")
