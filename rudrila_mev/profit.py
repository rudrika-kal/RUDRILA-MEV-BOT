from __future__ import annotations

from dataclasses import dataclass


BPS = 10_000


def floor_bps(value: int, haircut_bps: int) -> int:
    if value < 0:
        raise ValueError("value cannot be negative")
    if not 0 <= haircut_bps <= BPS:
        raise ValueError("invalid haircut_bps")
    return value * (BPS - haircut_bps) // BPS


def add_bps(value: int, add_bps_value: int) -> int:
    if value < 0 or add_bps_value < 0:
        raise ValueError("values cannot be negative")
    return (value * (BPS + add_bps_value) + (BPS - 1)) // BPS


@dataclass(frozen=True)
class GasQuote:
    gas_units: int
    buffered_gas_units: int
    base_fee_per_gas: int
    priority_fee_per_gas: int
    max_fee_per_gas: int
    worst_case_gas_cost_wei: int
    source: str


@dataclass(frozen=True)
class ProfitDecision:
    accepted: bool
    amount_in_wei: int
    expected_final_wei: int
    floor_final_wei: int
    expected_gross_profit_wei: int
    floor_gross_profit_wei: int
    gas_cost_wei: int
    extra_safety_buffer_wei: int
    desired_net_profit_wei: int
    required_gross_profit_wei: int
    floor_net_after_all_costs_wei: int
    reason: str


def evaluate_profit(
    *,
    amount_in_wei: int,
    expected_final_wei: int,
    floor_final_wei: int,
    gas_cost_wei: int,
    extra_safety_buffer_wei: int,
    desired_net_profit_wei: int,
) -> ProfitDecision:
    expected_gross = expected_final_wei - amount_in_wei
    floor_gross = floor_final_wei - amount_in_wei
    required_gross = gas_cost_wei + extra_safety_buffer_wei + desired_net_profit_wei
    floor_net = floor_gross - gas_cost_wei - extra_safety_buffer_wei
    accepted = floor_gross >= required_gross

    if floor_gross <= 0:
        reason = "REJECT: worst-case route is not profitable before gas"
    elif floor_gross < gas_cost_wei:
        reason = "REJECT: worst-case gross profit does not cover gas"
    elif floor_gross < gas_cost_wei + extra_safety_buffer_wei:
        reason = "REJECT: profit does not cover gas + safety buffer"
    elif not accepted:
        reason = "REJECT: net profit is below configured minimum"
    else:
        reason = "ACCEPT: worst-case output covers gas, safety buffer and minimum net profit"

    return ProfitDecision(
        accepted=accepted,
        amount_in_wei=amount_in_wei,
        expected_final_wei=expected_final_wei,
        floor_final_wei=floor_final_wei,
        expected_gross_profit_wei=expected_gross,
        floor_gross_profit_wei=floor_gross,
        gas_cost_wei=gas_cost_wei,
        extra_safety_buffer_wei=extra_safety_buffer_wei,
        desired_net_profit_wei=desired_net_profit_wei,
        required_gross_profit_wei=required_gross,
        floor_net_after_all_costs_wei=floor_net,
        reason=reason,
    )
