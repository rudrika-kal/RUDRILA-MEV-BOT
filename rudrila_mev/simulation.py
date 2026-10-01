from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TokenSimulation:
    buy_success: bool
    sell_success: bool
    amount_in_wei: int
    buy_received_raw: int
    base_received_back_wei: int
    expected_base_back_wei: int
    buy_tax_bps: int | None = None
    sell_tax_bps: int | None = None
    max_wallet_or_tx_failure: bool = False
    blacklist_or_pause_failure: bool = False
    dynamic_tax_suspected: bool = False
    note: str = ""


@dataclass(frozen=True)
class SimulationDecision:
    accepted: bool
    reason: str


def simulation_guard(
    s: TokenSimulation,
    *,
    max_total_tax_bps: int = 1000,
    max_roundtrip_loss_bps: int = 1500,
) -> SimulationDecision:
    if not s.buy_success:
        return SimulationDecision(False, "REJECT: simulated buy failed")
    if not s.sell_success:
        return SimulationDecision(False, "REJECT: simulated sell failed / possible honeypot")
    if s.max_wallet_or_tx_failure:
        return SimulationDecision(False, "REJECT: max-wallet/max-tx behavior detected")
    if s.blacklist_or_pause_failure:
        return SimulationDecision(False, "REJECT: blacklist/pause/trading restriction detected")
    if s.dynamic_tax_suspected:
        return SimulationDecision(False, "REJECT: dynamic/extreme tax behavior suspected")

    taxes = [x for x in (s.buy_tax_bps, s.sell_tax_bps) if x is not None]
    if taxes and sum(taxes) > max_total_tax_bps:
        return SimulationDecision(False, "REJECT: combined token tax exceeds limit")

    if s.amount_in_wei <= 0 or s.base_received_back_wei < 0:
        return SimulationDecision(False, "REJECT: invalid simulation amounts")
    loss = max(0, s.amount_in_wei - s.base_received_back_wei)
    roundtrip_loss_bps = loss * 10_000 // s.amount_in_wei
    if roundtrip_loss_bps > max_roundtrip_loss_bps:
        return SimulationDecision(False, "REJECT: simulated round-trip loss too high")

    return SimulationDecision(True, "PASS: buy/sell simulation safety")
